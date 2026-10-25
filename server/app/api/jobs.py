import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.user import User, UserRole
from app.models.job import Job, JobState, JobRequirement
from app.models.allocation import Allocation, AllocationState, Execution
from app.models.node import ComputeNode
from app.schemas.job import JobCreate, JobResponse, JobLogResponse
from app.utils.dependencies import get_current_user, require_client, require_admin
from app.services.executor import ExecutionService

router = APIRouter(prefix="/jobs", tags=["Jobs"])
execution_service = ExecutionService()


@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_data: JobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_client),
):
    """Submit a new compute job (Client or Admin only)."""
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
    await db.flush()

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

    # Automatically attempt scheduling upon submission
    from app.scheduler.scheduler import SchedulerService
    sched = SchedulerService()
    try:
        await sched.schedule_job(job.id, db)
    except Exception:
        pass

    result = await db.execute(
        select(Job)
        .options(
            selectinload(Job.requirements),
            selectinload(Job.allocations).selectinload(Allocation.executions),
        )
        .where(Job.id == job.id)
    )
    return result.scalar_one()


@router.get("/", response_model=list[JobResponse])
async def list_jobs(
    state: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List jobs filtered by RBAC:
    - Admin: All cluster jobs.
    - Client: Own submitted jobs.
    - Provider: Workloads allocated to nodes owned by this provider.
    """
    query = select(Job).options(
        selectinload(Job.requirements),
        selectinload(Job.allocations).selectinload(Allocation.executions),
    )

    if current_user.role == UserRole.ADMIN:
        pass  # sees everything
    elif current_user.role == UserRole.COMPUTE_USER:
        query = query.where(Job.owner_id == current_user.id)
    elif current_user.role == UserRole.COMPUTE_PROVIDER:
        # Filter jobs where allocation node belongs to this provider
        node_ids_subquery = select(ComputeNode.id).where(ComputeNode.provider_id == current_user.id)
        job_ids_subquery = select(Allocation.job_id).where(Allocation.node_id.in_(node_ids_subquery))
        query = query.where(Job.id.in_(job_ids_subquery))

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
    """Get a specific job by ID with authorization checks."""
    result = await db.execute(
        select(Job)
        .options(
            selectinload(Job.requirements),
            selectinload(Job.allocations).selectinload(Allocation.executions),
        )
        .where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    is_admin = current_user.role == UserRole.ADMIN
    is_owner = job.owner_id == current_user.id

    if not (is_admin or is_owner):
        # Allow provider if allocated to their node
        if current_user.role == UserRole.COMPUTE_PROVIDER:
            node_ids_result = await db.execute(
                select(ComputeNode.id).where(ComputeNode.provider_id == current_user.id)
            )
            provider_nodes = set(node_ids_result.scalars().all())
            has_alloc = any(a.node_id in provider_nodes for a in job.allocations)
            if not has_alloc:
                raise HTTPException(status_code=403, detail="Access denied")
        else:
            raise HTTPException(status_code=403, detail="Access denied")

    return job


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a job (Owner Client or Admin only)."""
    result = await db.execute(
        select(Job)
        .options(
            selectinload(Job.requirements),
            selectinload(Job.allocations).selectinload(Allocation.executions),
        )
        .where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if current_user.role != UserRole.ADMIN and job.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if job.state in (JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED):
        raise HTTPException(status_code=400, detail="Job is already in terminal state")

    job.state = JobState.CANCELLED
    for alloc in job.allocations:
        if alloc.state in (AllocationState.RESERVED, AllocationState.DISPATCHED, AllocationState.RUNNING):
            alloc.state = AllocationState.CANCELLED

    await db.commit()
    await db.refresh(job)
    return job


@router.post("/{job_id}/dispatch")
async def dispatch_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dispatch and execute an allocated job immediately."""
    result = await db.execute(
        select(Job)
        .options(selectinload(Job.allocations))
        .where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    is_admin = current_user.role == UserRole.ADMIN
    is_owner = job.owner_id == current_user.id
    if not (is_admin or is_owner):
        raise HTTPException(status_code=403, detail="Access denied to dispatch this workload")

    if not job.allocations:
        # Try to schedule first
        from app.scheduler.scheduler import SchedulerService
        sched = SchedulerService()
        res = await sched.schedule_job(job.id, db)
        if not res.get("success"):
            raise HTTPException(status_code=400, detail=f"Cannot dispatch: {res.get('message')}")
        await db.refresh(job)

    # Find the active allocation
    target_alloc = None
    for a in job.allocations:
        if a.state in (AllocationState.RESERVED, AllocationState.DISPATCHED):
            target_alloc = a
            break

    if not target_alloc and job.allocations:
        target_alloc = job.allocations[-1]

    if not target_alloc:
        raise HTTPException(status_code=400, detail="No valid allocation found for execution")

    exec_res = await execution_service.execute_allocation(target_alloc.id, db)
    return exec_res


@router.post("/dispatch-all")
async def dispatch_all_jobs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Execute all reserved workload allocations across the cluster (Admin only)."""
    results = await execution_service.dispatch_all_allocated(db)
    return {
        "dispatched_count": len(results),
        "executions": results,
    }


@router.get("/{job_id}/logs", response_model=JobLogResponse)
async def get_job_logs(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve standard execution terminal logs for a workload."""
    result = await db.execute(
        select(Job)
        .options(
            selectinload(Job.allocations)
            .selectinload(Allocation.executions),
            selectinload(Job.allocations)
            .selectinload(Allocation.node),
        )
        .where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    is_admin = current_user.role == UserRole.ADMIN
    is_owner = job.owner_id == current_user.id
    if not (is_admin or is_owner):
        raise HTTPException(status_code=403, detail="Access denied")

    node_name = None
    container_id = None
    exit_code = None
    logs = "No execution logs recorded yet. Workload is waiting in queue or scheduling."

    if job.allocations:
        latest_alloc = job.allocations[-1]
        if latest_alloc.node:
            node_name = latest_alloc.node.name
        if latest_alloc.executions:
            latest_exec = latest_alloc.executions[-1]
            container_id = latest_exec.container_id
            exit_code = latest_exec.exit_code
            logs = latest_exec.logs or "Execution running..."

    return JobLogResponse(
        job_id=job.id,
        job_name=job.name,
        state=job.state.value,
        node_name=node_name,
        container_id=container_id,
        exit_code=exit_code,
        logs=logs,
    )
