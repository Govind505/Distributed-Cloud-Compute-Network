import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Enum, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class AllocationState(str, enum.Enum):
    RESERVED = "reserved"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Allocation(Base):
    __tablename__ = "allocations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compute_nodes.id"), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    score_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[AllocationState] = mapped_column(Enum(AllocationState), default=AllocationState.RESERVED, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    job = relationship("Job", back_populates="allocations")
    node = relationship("ComputeNode", back_populates="allocations")
    executions = relationship("Execution", back_populates="allocation", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Allocation job={self.job_id} node={self.node_id} score={self.score}>"


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    allocation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("allocations.id"), nullable=False, index=True)
    container_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    logs: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    allocation = relationship("Allocation", back_populates="executions")

    def __repr__(self) -> str:
        return f"<Execution alloc={self.allocation_id} exit={self.exit_code}>"
