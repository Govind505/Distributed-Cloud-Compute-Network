import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class JobRequirementCreate(BaseModel):
    cpu_cores: float = Field(default=1.0, ge=0.1)
    ram_mb: int = Field(default=512, ge=64)
    disk_mb: int = Field(default=0, ge=0)
    gpu_count: int = Field(default=0, ge=0)
    gpu_vram_mb: int = Field(default=0, ge=0)


class JobCreate(BaseModel):
    name: str = Field(..., max_length=200)
    image_name: str = Field(..., max_length=500)
    command: str | None = None
    priority: int = Field(default=5, ge=1, le=10)
    timeout_seconds: int = Field(default=3600, ge=60, le=86400)
    requirements: JobRequirementCreate = Field(default_factory=JobRequirementCreate)


class JobRequirementResponse(BaseModel):
    cpu_cores: float
    ram_mb: int
    disk_mb: int
    gpu_count: int
    gpu_vram_mb: int

    model_config = {"from_attributes": True}


class ExecutionResponse(BaseModel):
    id: uuid.UUID
    allocation_id: uuid.UUID
    container_id: str | None
    exit_code: int | None
    started_at: datetime | None
    finished_at: datetime | None
    logs: str | None

    model_config = {"from_attributes": True}


class AllocationResponse(BaseModel):
    id: uuid.UUID
    node_id: uuid.UUID
    score: float
    score_breakdown: dict | None
    attempt: int
    state: str
    created_at: datetime
    executions: list[ExecutionResponse] = []

    model_config = {"from_attributes": True}


class JobResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    image_name: str
    command: str | None
    state: str
    priority: int
    timeout_seconds: int
    created_at: datetime
    updated_at: datetime
    requirements: JobRequirementResponse | None = None
    allocations: list[AllocationResponse] = []

    model_config = {"from_attributes": True}


class JobLogResponse(BaseModel):
    job_id: uuid.UUID
    job_name: str
    state: str
    node_name: str | None
    container_id: str | None
    exit_code: int | None
    logs: str | None


class ScheduleResponse(BaseModel):
    job_id: uuid.UUID
    node_id: uuid.UUID | None
    score: float | None
    score_breakdown: dict | None
    message: str
