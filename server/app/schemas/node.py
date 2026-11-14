import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class NodeRegister(BaseModel):
    name: str = Field(..., max_length=200)
    hostname: str = Field(..., max_length=255)
    ip_address: str | None = None
    cpu_cores: int = Field(..., ge=1)
    ram_total_mb: int = Field(..., ge=256)
    disk_total_mb: int = Field(..., ge=1024)
    gpu_model: str | None = None
    gpu_count: int = Field(default=0, ge=0)
    gpu_vram_mb: int | None = None
    cloud_provider: str = Field(default="bare_metal", max_length=50)
    region: str = Field(default="global", max_length=50)
    overcommit_ratio: float = Field(default=2.5, ge=1.0, le=8.0)
    cost_per_hour_usd: float = Field(default=0.0, ge=0.0)
    labels: dict | None = None


class NodeResponse(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    name: str
    hostname: str
    ip_address: str | None
    status: str
    cpu_cores: int
    ram_total_mb: int
    disk_total_mb: int
    gpu_model: str | None
    gpu_count: int
    gpu_vram_mb: int | None
    cloud_provider: str
    region: str
    overcommit_ratio: float
    cost_per_hour_usd: float
    labels: dict | None
    last_seen: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NodeUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    labels: dict | None = None


class HeartbeatRequest(BaseModel):
    cpu_usage_percent: float = Field(..., ge=0, le=100)
    ram_free_mb: int = Field(..., ge=0)
    disk_free_mb: int = Field(..., ge=0)
    gpu_utilization_percent: float | None = None
    gpu_vram_free_mb: int | None = None
    active_containers: int = Field(default=0, ge=0)


class SnapshotResponse(BaseModel):
    id: uuid.UUID
    node_id: uuid.UUID
    cpu_usage_percent: float
    ram_free_mb: int
    disk_free_mb: int
    gpu_utilization_percent: float | None
    gpu_vram_free_mb: int | None
    rtt_ms: float
    active_containers: int
    sampled_at: datetime

    model_config = {"from_attributes": True}
