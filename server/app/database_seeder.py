import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from app.database import engine, Base, AsyncSessionLocal
from app.models.user import User, UserRole, UserStatus
from app.models.node import ComputeNode, NodeStatus, ResourceSnapshot
from app.models.job import Job, JobState, JobRequirement
from app.utils.auth import hash_password
from app.scheduler.scheduler import SchedulerService


async def auto_init_and_seed_db():
    """Automatically ensure database tables exist and are populated with demo cluster data."""
    # 1. Create tables if they do not exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Check if cluster has already been seeded
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.email == "admin@dccn.network"))
        existing_admin = res.scalar_one_or_none()
        if existing_admin:
            # Already seeded
            return

        print("[DCCN] First run detected: Seeding enterprise cluster demo data...")

        # Create Enterprise Demo Users
        admin_user = User(
            email="admin@dccn.network",
            username="admin",
            password_hash=hash_password("admin123"),
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        provider_user = User(
            email="provider@dccn.network",
            username="provider",
            password_hash=hash_password("provider123"),
            role=UserRole.COMPUTE_PROVIDER,
            status=UserStatus.ACTIVE,
        )
        client_user = User(
            email="client@dccn.network",
            username="client",
            password_hash=hash_password("client123"),
            role=UserRole.COMPUTE_USER,
            status=UserStatus.ACTIVE,
        )

        db.add_all([admin_user, provider_user, client_user])
        await db.flush()

        # Create Heterogeneous Compute Nodes
        node_1 = ComputeNode(
            provider_id=provider_user.id,
            name="Compute-Node-01",
            hostname="worker-01.dccn.local",
            cpu_cores=8,
            ram_total_mb=16384,
            disk_total_mb=512000,
            status=NodeStatus.ONLINE,
            last_seen=datetime.now(timezone.utc),
        )
        node_2 = ComputeNode(
            provider_id=provider_user.id,
            name="Compute-Node-02",
            hostname="worker-02.dccn.local",
            cpu_cores=4,
            ram_total_mb=8192,
            disk_total_mb=256000,
            status=NodeStatus.ONLINE,
            last_seen=datetime.now(timezone.utc),
        )
        node_3 = ComputeNode(
            provider_id=provider_user.id,
            name="GPU-Cluster-01",
            hostname="gpu-host-01.dccn.local",
            cpu_cores=16,
            ram_total_mb=32768,
            disk_total_mb=1024000,
            gpu_model="NVIDIA RTX 3080",
            gpu_count=1,
            gpu_vram_mb=10240,
            status=NodeStatus.ONLINE,
            last_seen=datetime.now(timezone.utc),
        )
        node_4 = ComputeNode(
            provider_id=provider_user.id,
            name="GPU-Cluster-02",
            hostname="gpu-host-02.dccn.local",
            cpu_cores=12,
            ram_total_mb=24576,
            disk_total_mb=512000,
            gpu_model="NVIDIA Tesla T4",
            gpu_count=2,
            gpu_vram_mb=16384,
            status=NodeStatus.ONLINE,
            last_seen=datetime.now(timezone.utc),
        )

        db.add_all([node_1, node_2, node_3, node_4])
        await db.flush()

        # Create Resource Snapshots (Live Telemetry)
        now = datetime.now(timezone.utc)
        snapshots = [
            ResourceSnapshot(
                node_id=node_1.id,
                cpu_usage_percent=25.0,
                ram_free_mb=12000,
                disk_free_mb=400000,
                active_containers=0,
                sampled_at=now,
            ),
            ResourceSnapshot(
                node_id=node_2.id,
                cpu_usage_percent=60.0,
                ram_free_mb=4000,
                disk_free_mb=200000,
                active_containers=1,
                sampled_at=now,
            ),
            ResourceSnapshot(
                node_id=node_3.id,
                cpu_usage_percent=15.0,
                ram_free_mb=28000,
                disk_free_mb=900000,
                gpu_utilization_percent=10.0,
                gpu_vram_free_mb=9000,
                active_containers=0,
                sampled_at=now,
            ),
            ResourceSnapshot(
                node_id=node_4.id,
                cpu_usage_percent=40.0,
                ram_free_mb=18000,
                disk_free_mb=400000,
                gpu_utilization_percent=30.0,
                gpu_vram_free_mb=14000,
                active_containers=1,
                sampled_at=now,
            ),
        ]
        db.add_all(snapshots)

        # Create Benchmark Workloads
        job_1 = Job(
            owner_id=client_user.id,
            name="Matrix Multiplication Benchmark",
            image_name="python:3.11-slim",
            command="python -c 'import numpy; a=numpy.random.rand(1000,1000); b=a@a; print(b.shape)'",
            priority=5,
            timeout_seconds=600,
            state=JobState.QUEUED,
        )
        job_2 = Job(
            owner_id=client_user.id,
            name="Image Classification Inference",
            image_name="pytorch/pytorch:latest",
            command="python classify.py --model resnet50 --input /data/images",
            priority=7,
            timeout_seconds=1800,
            state=JobState.QUEUED,
        )
        job_3 = Job(
            owner_id=client_user.id,
            name="Data Compression Test",
            image_name="ubuntu:22.04",
            command="gzip -9 /data/large_file.dat",
            priority=3,
            timeout_seconds=300,
            state=JobState.QUEUED,
        )

        db.add_all([job_1, job_2, job_3])
        await db.flush()

        req_1 = JobRequirement(
            job_id=job_1.id,
            cpu_cores=2.0,
            ram_mb=2048,
            disk_mb=500,
            gpu_count=0,
            gpu_vram_mb=0,
        )
        req_2 = JobRequirement(
            job_id=job_2.id,
            cpu_cores=4.0,
            ram_mb=8192,
            disk_mb=2048,
            gpu_count=1,
            gpu_vram_mb=4096,
        )
        req_3 = JobRequirement(
            job_id=job_3.id,
            cpu_cores=1.0,
            ram_mb=512,
            disk_mb=1024,
            gpu_count=0,
            gpu_vram_mb=0,
        )

        db.add_all([req_1, req_2, req_3])
        await db.commit()

        # Schedule benchmark jobs using the 7-Factor Weighted Engine
        scheduler = SchedulerService()
        for jid in [job_1.id, job_2.id, job_3.id]:
            try:
                await scheduler.schedule_job(jid, db)
            except Exception as e:
                print(f"[DCCN] Scheduler init warning for job {jid}: {e}")

        print("[DCCN] Cluster demo data seeded successfully: 3 users, 4 nodes, 3 workloads scheduled.")
