import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.user import User, UserRole
from app.models.node import ComputeNode, NodeStatus
from app.models.job import Job, JobState
from app.models.allocation import Allocation
from app.models.audit import AuditLog
from app.schemas.user import UserResponse
from app.utils.dependencies import require_admin

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all users (admin only)."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: uuid.UUID,
    role: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Change a user's role (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        user.role = UserRole(role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {[r.value for r in UserRole]}")
    await db.commit()
    return {"message": f"User role updated to {role}"}


@router.get("/dashboard")
async def admin_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get admin dashboard stats."""
    # Count users
    user_count = await db.scalar(select(func.count()).select_from(User))
    
    # Count nodes by status
    nodes_online = await db.scalar(
        select(func.count()).select_from(ComputeNode).where(ComputeNode.status == NodeStatus.ONLINE)
    )
    nodes_total = await db.scalar(select(func.count()).select_from(ComputeNode))
    nodes_pending = await db.scalar(
        select(func.count()).select_from(ComputeNode).where(ComputeNode.status == NodeStatus.PENDING_APPROVAL)
    )

    # Count jobs by state
    jobs_queued = await db.scalar(
        select(func.count()).select_from(Job).where(Job.state == JobState.QUEUED)
    )
    jobs_running = await db.scalar(
        select(func.count()).select_from(Job).where(Job.state == JobState.RUNNING)
    )
    jobs_completed = await db.scalar(
        select(func.count()).select_from(Job).where(Job.state == JobState.COMPLETED)
    )
    jobs_failed = await db.scalar(
        select(func.count()).select_from(Job).where(Job.state == JobState.FAILED)
    )
    jobs_total = await db.scalar(select(func.count()).select_from(Job))

    return {
        "users": {"total": user_count},
        "nodes": {
            "total": nodes_total,
            "online": nodes_online,
            "pending_approval": nodes_pending,
        },
        "jobs": {
            "total": jobs_total,
            "queued": jobs_queued,
            "running": jobs_running,
            "completed": jobs_completed,
            "failed": jobs_failed,
        },
    }


@router.get("/audit")
async def list_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get recent audit logs (admin only)."""
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "actor_id": str(log.actor_id) if log.actor_id else None,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "outcome": log.outcome,
            "details": log.details,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
