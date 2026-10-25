import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User, UserRole
from app.models.job import Job
from app.scheduler import SchedulerService
from app.utils.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])
scheduler_service = SchedulerService()


@router.post("/schedule/{job_id}")
async def schedule_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger 7-factor scheduling for a specific job (Owner Client or Admin only)."""
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if current_user.role != UserRole.ADMIN and job.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only schedule workloads you own",
        )

    result = await scheduler_service.schedule_job(job_id, db)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/schedule-all")
async def schedule_all(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Schedule all queued jobs in the cluster (Administrator only)."""
    results = await scheduler_service.schedule_all_queued(db)
    return {
        "scheduled": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if not r.get("success")),
        "results": results,
    }
