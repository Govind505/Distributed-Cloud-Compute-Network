"""
Compute Credit & Virtual Accounting Ledger Service
Calculates compute consumption costs, executes credit deductions for clients,
and routes staking yields/rewards to compute providers.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.ledger import CreditLedger, UserCreditBalance
from app.models.job import Job
from app.models.node import ComputeNode


class BillingService:
    """Manages virtual ledger balances and workload credit settlements."""

    DEFAULT_INITIAL_BALANCES = {
        "compute_user": 1000.0,
        "compute_provider": 250.0,
        "admin": 5000.0,
    }

    async def get_or_create_balance(self, user_id: uuid.UUID, role: str, db: AsyncSession) -> UserCreditBalance:
        """Fetch or initialize credit balance for a user."""
        res = await db.execute(select(UserCreditBalance).where(UserCreditBalance.user_id == user_id))
        balance_record = res.scalar_one_or_none()
        if not balance_record:
            initial = self.DEFAULT_INITIAL_BALANCES.get(role, 500.0)
            balance_record = UserCreditBalance(
                user_id=user_id,
                balance=initial,
                total_consumed=0.0,
                total_earned=0.0,
            )
            db.add(balance_record)
            
            # Initial grant ledger entry
            ledger_entry = CreditLedger(
                user_id=user_id,
                transaction_type="grant",
                amount=initial,
                balance_after=initial,
                description="Initial enterprise compute credit grant",
            )
            db.add(ledger_entry)
            await db.commit()
            await db.refresh(balance_record)
        return balance_record

    async def settle_workload_execution(
        self,
        job: Job,
        node: ComputeNode,
        duration_seconds: float,
        db: AsyncSession,
    ) -> dict:
        """Deduct credits from client and disburse yield to provider."""
        req = job.requirements
        cores = req.cpu_cores if req else 1.0
        gpus = req.gpu_count if req else 0
        ram_gb = (req.ram_mb if req else 512) / 1024.0

        # Base hourly rate: 10 credits/vCPU-hr, 50 credits/GPU-hr, 2 credits/GB-RAM-hr
        hourly_rate = (cores * 10.0) + (gpus * 50.0) + (ram_gb * 2.0)
        
        # Micro-tier sub-core scaling (0.25 vCPU minimum is 0.5 credits; standard 1.0+ core is 2.5)
        min_charge = 0.5 if cores < 1.0 else 2.5
        effective_duration = max(duration_seconds, 12.0)
        cost = max(min_charge, round((hourly_rate * (effective_duration / 3600.0)) * 50, 2))
        provider_yield = round(cost * 0.85, 2)  # 85% yield to provider, 15% network maintenance fee

        # 1. Deduct from client
        client_balance = await self.get_or_create_balance(job.owner_id, "compute_user", db)
        client_balance.balance = max(0.0, round(client_balance.balance - cost, 2))
        client_balance.total_consumed = round(client_balance.total_consumed + cost, 2)

        client_ledger = CreditLedger(
            user_id=job.owner_id,
            job_id=job.id,
            transaction_type="debit",
            amount=cost,
            balance_after=client_balance.balance,
            description=f"Execution fee: '{job.name}' ({cores} vCPU, {gpus} GPU, {effective_duration:.1f}s)",
        )
        db.add(client_ledger)

        # 2. Credit to provider
        provider_balance = await self.get_or_create_balance(node.provider_id, "compute_provider", db)
        provider_balance.balance = round(provider_balance.balance + provider_yield, 2)
        provider_balance.total_earned = round(provider_balance.total_earned + provider_yield, 2)

        provider_ledger = CreditLedger(
            user_id=node.provider_id,
            job_id=job.id,
            transaction_type="credit",
            amount=provider_yield,
            balance_after=provider_balance.balance,
            description=f"Host yield reward: '{job.name}' executed on node '{node.name}'",
        )
        db.add(provider_ledger)

        await db.commit()

        return {
            "cost": cost,
            "provider_yield": provider_yield,
            "client_remaining": client_balance.balance,
            "provider_total_balance": provider_balance.balance,
        }

    async def top_up(self, user_id: uuid.UUID, amount: float, db: AsyncSession) -> float:
        """Add credits to a user balance."""
        res = await db.execute(select(UserCreditBalance).where(UserCreditBalance.user_id == user_id))
        rec = res.scalar_one_or_none()
        if not rec:
            rec = await self.get_or_create_balance(user_id, "compute_user", db)
        
        rec.balance = round(rec.balance + amount, 2)
        ledger = CreditLedger(
            user_id=user_id,
            transaction_type="topup",
            amount=amount,
            balance_after=rec.balance,
            description=f"Account top-up: +{amount:.2f} DCCN Compute Credits",
        )
        db.add(ledger)
        await db.commit()
        await db.refresh(rec)
        return rec.balance
