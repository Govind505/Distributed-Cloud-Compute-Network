import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Enum, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class JobState(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SCHEDULING = "scheduling"
    ALLOCATED = "allocated"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    image_name: Mapped[str] = mapped_column(String(500), nullable=False)
    image_digest: Mapped[str | None] = mapped_column(String(200), nullable=True)
    command: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[JobState] = mapped_column(Enum(JobState), default=JobState.PENDING, nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    owner = relationship("User", back_populates="jobs")
    requirements = relationship("JobRequirement", back_populates="job", uselist=False, lazy="joined")
    allocations = relationship("Allocation", back_populates="job", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Job {self.name} ({self.state.value})>"


class JobRequirement(Base):
    __tablename__ = "job_requirements"

    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"), primary_key=True)
    cpu_cores: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    ram_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=512)
    disk_mb: Mapped[int] = mapped_column(Integer, default=0)
    gpu_count: Mapped[int] = mapped_column(Integer, default=0)
    gpu_vram_mb: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    job = relationship("Job", back_populates="requirements")

    def __repr__(self) -> str:
        return f"<JobRequirement job={self.job_id} cpu={self.cpu_cores} ram={self.ram_mb}>"
