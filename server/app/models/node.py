import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Enum, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class NodeStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    SUSPECT = "suspect"
    DRAINED = "drained"
    PENDING_APPROVAL = "pending_approval"


class ComputeNode(Base):
    __tablename__ = "compute_nodes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    status: Mapped[NodeStatus] = mapped_column(Enum(NodeStatus), default=NodeStatus.PENDING_APPROVAL, nullable=False)
    labels: Mapped[dict | None] = mapped_column(JSON, default=dict)

    # Hardware specs
    cpu_cores: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ram_total_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=1024)
    disk_total_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=10240)
    gpu_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    gpu_count: Mapped[int] = mapped_column(Integer, default=0)
    gpu_vram_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)

    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    provider = relationship("User", back_populates="nodes")
    snapshots = relationship("ResourceSnapshot", back_populates="node", lazy="dynamic")
    allocations = relationship("Allocation", back_populates="node", lazy="selectin")

    def __repr__(self) -> str:
        return f"<ComputeNode {self.name} ({self.status.value})>"


class ResourceSnapshot(Base):
    __tablename__ = "resource_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compute_nodes.id"), nullable=False, index=True)
    cpu_usage_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ram_free_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    disk_free_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    gpu_utilization_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    gpu_vram_free_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rtt_ms: Mapped[float] = mapped_column(Float, default=0.0)
    active_containers: Mapped[int] = mapped_column(Integer, default=0)
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    node = relationship("ComputeNode", back_populates="snapshots")

    def __repr__(self) -> str:
        return f"<ResourceSnapshot node={self.node_id} at={self.sampled_at}>"
