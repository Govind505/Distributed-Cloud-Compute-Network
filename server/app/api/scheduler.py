import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.job import ScheduleResponse
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
    """Trigger scheduling for a specific job."""
    result = await scheduler_service.schedule_job(job_id, db)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/schedule-all")
async def schedule_all(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Schedule all queued jobs (admin only)."""
    results = await scheduler_service.schedule_all_queued(db)
    return {
        "scheduled": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if not r.get("success")),
        "results": results,
    }
