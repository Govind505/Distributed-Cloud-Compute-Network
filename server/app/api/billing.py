import uuid
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.models.ledger import CreditLedger, UserCreditBalance
from app.services.billing import BillingService
from app.services.market import spot_market_service
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/billing", tags=["Billing & Virtual Ledger"])
billing_service = BillingService()


class ArbitrageCalcRequest(BaseModel):
    preset_key: str = Field(default="hetzner_dedicated")
    utilization_percent: float = Field(default=65.0, ge=10.0, le=100.0)
    overcommit_ratio: float = Field(default=2.5, ge=1.0, le=8.0)
    custom_cost_usd: float | None = None
    custom_cores: int | None = None
    custom_gpus: int | None = None


class TopUpRequest(BaseModel):
    amount: float = Field(default=500.0, ge=10.0, le=50000.0)


@router.get("/balance")
async def get_balance(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve current compute credit balance, total spent, and yield earnings."""
    role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    balance_rec = await billing_service.get_or_create_balance(current_user.id, role_val, db)
    return {
        "user_id": str(current_user.id),
        "email": current_user.email,
        "role": role_val,
        "balance": balance_rec.balance,
        "total_consumed": balance_rec.total_consumed,
        "total_earned": balance_rec.total_earned,
        "currency": "DCCN Credits",
        "updated_at": balance_rec.updated_at.isoformat() if balance_rec.updated_at else None,
    }


@router.get("/ledger")
async def get_ledger_history(
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch user's transaction ledger history."""
    query = (
        select(CreditLedger)
        .where(CreditLedger.user_id == current_user.id)
        .order_by(CreditLedger.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    entries = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "job_id": str(e.job_id) if e.job_id else None,
            "transaction_type": e.transaction_type,
            "amount": e.amount,
            "balance_after": e.balance_after,
            "description": e.description,
            "created_at": e.created_at.isoformat(),
        }
        for e in entries
    ]


@router.post("/topup")
async def topup_credits(
    req: TopUpRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Top up compute credits."""
    new_balance = await billing_service.top_up(current_user.id, req.amount, db)
    return {
        "success": True,
        "added": req.amount,
        "new_balance": new_balance,
        "currency": "DCCN Credits",
    }


@router.get("/pricing")
async def get_pricing_schedule():
    """Retrieve dynamic cluster pricing schedule."""
    return {
        "currency": "DCCN Credits",
        "rates": {
            "vcpu_core_per_hour": 10.0,
            "gpu_accelerator_per_hour": 50.0,
            "ram_gb_per_hour": 2.0,
            "micro_tier_vcpu_per_hour": 2.5,
            "minimum_job_fee": 2.5,
            "minimum_micro_job_fee": 0.5,
        },
        "fractional_slicing": {
            "min_cpu_cores": 0.1,
            "min_ram_mb": 64,
            "overcommit_ratio": 2.5,
        },
        "provider_yield_share": "85%",
        "network_governance_fee": "15%",
    }


@router.get("/arbitrage/presets")
async def get_arbitrage_presets():
    """Retrieve pre-configured cloud instance benchmark presets for provider arbitrage."""
    return spot_market_service.CLOUD_PRESETS


@router.post("/arbitrage/calculate")
async def calculate_arbitrage_roi(
    req: ArbitrageCalcRequest,
):
    """Calculate projected monthly revenues, cloud costs, and net ROI margin."""
    return spot_market_service.calculate_cloud_arbitrage_roi(
        preset_key=req.preset_key,
        utilization_percent=req.utilization_percent,
        overcommit_ratio=req.overcommit_ratio,
        custom_cost_usd=req.custom_cost_usd,
        custom_cores=req.custom_cores,
        custom_gpus=req.custom_gpus,
    )
