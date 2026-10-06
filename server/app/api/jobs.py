import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.user import User
from app.models.job import Job, JobState, JobRequirement
from app.schemas.job import JobCreate, JobResponse
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_data: JobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a new compute job."""
    job = Job(
        owner_id=current_user.id,
        name=job_data.name,
        image_name=job_data.image_name,
        command=job_data.command,
        priority=job_data.priority,
        timeout_seconds=job_data.timeout_seconds,
        state=JobState.QUEUED,
    )
    db.add(job)
    await db.flush()  # Get the job ID

    requirements = JobRequirement(
        job_id=job.id,
        cpu_cores=job_data.requirements.cpu_cores,
        ram_mb=job_data.requirements.ram_mb,
        disk_mb=job_data.requirements.disk_mb,
        gpu_count=job_data.requirements.gpu_count,
        gpu_vram_mb=job_data.requirements.gpu_vram_mb,
    )
    db.add(requirements)
    await db.commit()

    # Reload with relationships
    result = await db.execute(
        select(Job)
        .options(selectinload(Job.requirements), selectinload(Job.allocations))
        .where(Job.id == job.id)
    )
    return result.scalar_one()


@router.get("/", response_model=list[JobResponse])
async def list_jobs(
    state: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List jobs. Regular users see their own jobs; admins see all."""
    query = select(Job).options(selectinload(Job.requirements), selectinload(Job.allocations))
    if current_user.role.value != "admin":
        query = query.where(Job.owner_id == current_user.id)
    if state:
        try:
            js = JobState(state)
            query = query.where(Job.state == js)
        except ValueError:
            pass
    result = await db.execute(query.order_by(Job.created_at.desc()))
    return result.scalars().all()


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific job by ID."""
    result = await db.execute(
        select(Job)
        .options(selectinload(Job.requirements), selectinload(Job.allocations))
        .where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if current_user.role.value != "admin" and job.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return job


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a job."""
    result = await db.execute(
        select(Job)
        .options(selectinload(Job.requirements), selectinload(Job.allocations))
        .where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if current_user.role.value != "admin" and job.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if job.state in (JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED):
        raise HTTPException(status_code=400, detail="Job is already in terminal state")
    job.state = JobState.CANCELLED
    await db.commit()
    await db.refresh(job)
    return job
