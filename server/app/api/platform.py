"""
Platform Improvisations Router:
Exposes enterprise-grade REST endpoints for the 5 advanced architectural subsystems:
1. Raft HA Distributed Consensus Multi-Leader Controller
2. Verifiable Computing & Cryptographic Result Proofs
3. Dynamic Spot Market & VCG 2nd-Price Auctions
4. OpenTelemetry Distributed Tracing & Waterfall Spans
5. eBPF & cgroup v2 Hard Kernel-Level Isolation Sandboxing
"""
import uuid
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.job import Job
from app.models.node import ResourceSnapshot
from app.utils.dependencies import get_current_user, require_admin
from app.services.consensus import consensus_service
from app.services.verification import verification_service
from app.services.market import spot_market_service
from app.services.tracing import tracing_service
from app.services.isolation import isolation_service

router = APIRouter(prefix="/platform", tags=["Platform Improvisations"])


class SpotBidRequest(BaseModel):
    max_bid: float = Field(..., gt=0, description="Maximum willingness to pay per compute hour")
    cpu_cores: float = Field(default=1.0, ge=0.1, description="vCPU cores requested")
    gpu_count: int = Field(default=0, ge=0, description="Discrete GPUs requested")


class RedundantVerificationRequest(BaseModel):
    job_id: str = Field(..., description="Target Job UUID")
    sample_output: str = Field(..., description="Secondary witness node output log")


# ==========================================
# 1. Raft High-Availability Consensus
# ==========================================

@router.get("/consensus/status")
async def get_consensus_status(
    current_user: User = Depends(get_current_user),
):
    """Retrieve current Raft cluster consensus state, leader ID, term, and quorum status."""
    return consensus_service.get_consensus_status()


@router.post("/consensus/failover")
async def trigger_consensus_failover(
    current_user: User = Depends(require_admin),
):
    """Trigger simulated leader step-down and standby failover election (Admin only)."""
    return await consensus_service.step_down_or_failover()


@router.get("/consensus/logs")
async def get_consensus_logs(
    current_user: User = Depends(get_current_user),
):
    """Inspect replicated consensus state machine commit logs."""
    return {
        "node_id": consensus_service.node_id,
        "term": consensus_service.current_term,
        "commit_index": consensus_service.commit_index,
        "log_entries": consensus_service.log_entries[-50:],
    }


# ==========================================
# 2. Verifiable Computing & Attestation
# ==========================================

@router.get("/verification/proofs")
async def list_verification_proofs(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """List recent cryptographic attestation proofs across executed workloads."""
    return verification_service.list_proofs(limit=limit)


@router.get("/verification/{job_id}")
async def get_job_verification_proof(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """Retrieve SHA-256 cryptographic attestation proof for a specific completed job."""
    proof = verification_service.get_proof(job_id)
    if not proof:
        raise HTTPException(status_code=404, detail="Cryptographic proof not found for job")
    return proof


@router.post("/verification/sample-check")
async def verify_sample_consistency(
    req: RedundantVerificationRequest,
    current_user: User = Depends(require_admin),
):
    """Execute redundant multi-node cross-sampling and verify checksum consensus."""
    return verification_service.verify_redundant_sample(req.job_id, req.sample_output)


# ==========================================
# 3. Dynamic Spot Market & VCG Auctions
# ==========================================

@router.get("/market/spot-rates")
async def get_market_spot_rates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Calculate real-time spot market pricing based on current cluster utilization."""
    snaps_res = await db.execute(
        select(ResourceSnapshot).order_by(ResourceSnapshot.sampled_at.desc()).limit(20)
    )
    snaps = snaps_res.scalars().all()
    avg_cpu = sum(s.cpu_usage_percent for s in snaps) / len(snaps) if snaps else 25.0
    return spot_market_service.calculate_spot_rate(avg_cpu)


@router.post("/market/bid")
async def submit_spot_auction_bid(
    bid: SpotBidRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Evaluate spot bid against live market clearing threshold using Vickrey 2nd-price clearing."""
    snaps_res = await db.execute(
        select(ResourceSnapshot).order_by(ResourceSnapshot.sampled_at.desc()).limit(20)
    )
    snaps = snaps_res.scalars().all()
    avg_cpu = sum(s.cpu_usage_percent for s in snaps) / len(snaps) if snaps else 25.0
    return spot_market_service.evaluate_spot_bid(
        max_bid=bid.max_bid,
        cores=bid.cpu_cores,
        gpus=bid.gpu_count,
        cluster_load=avg_cpu,
    )


# ==========================================
# 4. OpenTelemetry Distributed Tracing
# ==========================================

@router.get("/tracing")
async def list_recent_traces(
    current_user: User = Depends(get_current_user),
):
    """Retrieve list of OpenTelemetry traces instrumenting workload lifecycle."""
    traces = list(tracing_service.traces.values())
    traces.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return [
        {
            "trace_id": t["trace_id"],
            "job_id": t["job_id"],
            "job_name": t["job_name"],
            "span_count": len(t["spans"]),
            "total_duration_ms": t["total_duration_ms"],
            "created_at": t.get("created_at"),
        }
        for t in traces[:30]
    ]


@router.get("/tracing/{job_id}")
async def get_job_trace(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """Retrieve full microsecond OpenTelemetry span waterfall DAG for a job."""
    trace = tracing_service.get_trace(job_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found for this workload")
    return trace


# ==========================================
# 5. eBPF & cgroup v2 Kernel Isolation
# ==========================================

@router.get("/isolation/status")
async def get_kernel_isolation_status(
    current_user: User = Depends(get_current_user),
):
    """Inspect cgroup v2 controllers, seccomp filters, and eBPF network hooks."""
    return isolation_service.get_isolation_status()


@router.get("/isolation/sandbox/{container_id}")
async def get_sandbox_parameters(
    container_id: str,
    current_user: User = Depends(get_current_user),
):
    """Retrieve sandbox parameters and isolation rules for an active or past container."""
    sandbox = isolation_service.inspect_sandbox(container_id)
    if not sandbox:
        raise HTTPException(status_code=404, detail="Container sandbox profile not found")
    return sandbox
