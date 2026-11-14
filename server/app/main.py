import os
import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.config import get_settings
from app.database import get_db, AsyncSessionLocal
from app.database_seeder import auto_init_and_seed_db
from app.models.node import ComputeNode, NodeStatus, ResourceSnapshot
from app.models.job import Job, JobState
from app.services.watchdog import WatchdogService
from app.utils.dependencies import require_admin
from app.api import auth, nodes, jobs, admin, scheduler, billing, platform

settings = get_settings()
watchdog_service = WatchdogService()


async def run_periodic_watchdog():
    """Background task checking node heartbeat status every 30 seconds."""
    while True:
        try:
            await asyncio.sleep(30)
            async with AsyncSessionLocal() as db:
                await watchdog_service.check_nodes_health(db)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[DCCN Watchdog Error] {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await auto_init_and_seed_db()
    except Exception as e:
        print(f"[DCCN Startup Error] {e}")

    watchdog_task = asyncio.create_task(run_periodic_watchdog())
    yield
    watchdog_task.cancel()
    try:
        await watchdog_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="A distributed cloud compute network for dynamic resource allocation and heterogeneous cluster orchestration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(nodes.router, prefix=settings.API_V1_PREFIX)
app.include_router(jobs.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin.router, prefix=settings.API_V1_PREFIX)
app.include_router(scheduler.router, prefix=settings.API_V1_PREFIX)
app.include_router(billing.router, prefix=settings.API_V1_PREFIX)
app.include_router(platform.router, prefix=settings.API_V1_PREFIX)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
@app.get("/login")
async def login_page():
    login_file = os.path.join(STATIC_DIR, "login.html")
    if os.path.exists(login_file):
        return FileResponse(login_file)
    return {"status": "ok"}


@app.get("/client")
async def client_page():
    client_file = os.path.join(STATIC_DIR, "client.html")
    if os.path.exists(client_file):
        return FileResponse(client_file)
    return {"status": "ok"}


@app.get("/provider")
async def provider_page():
    prov_file = os.path.join(STATIC_DIR, "provider.html")
    if os.path.exists(prov_file):
        return FileResponse(prov_file)
    return {"status": "ok"}


@app.get("/admin")
async def admin_page():
    admin_file = os.path.join(STATIC_DIR, "admin.html")
    if os.path.exists(admin_file):
        return FileResponse(admin_file)
    return {"status": "ok"}


@app.get("/dashboard")
async def dashboard():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {
        "name": settings.PROJECT_NAME,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    """High-frequency real-time WebSocket channel streaming cluster state and telemetry."""
    await websocket.accept()
    try:
        while True:
            async with AsyncSessionLocal() as db:
                nodes_res = await db.execute(select(ComputeNode))
                all_nodes = nodes_res.scalars().all()
                online_count = sum(1 for n in all_nodes if n.status == NodeStatus.ONLINE)
                total_nodes = len(all_nodes)
                total_cores = sum(n.cpu_cores for n in all_nodes)
                total_ram_mb = sum(n.ram_total_mb for n in all_nodes)
                total_gpus = sum(n.gpu_count for n in all_nodes)
                total_vram_mb = sum(n.gpu_vram_mb or 0 for n in all_nodes)

                snaps_res = await db.execute(
                    select(ResourceSnapshot).order_by(ResourceSnapshot.sampled_at.desc()).limit(20)
                )
                snaps = snaps_res.scalars().all()
                avg_cpu = round(sum(s.cpu_usage_percent for s in snaps) / len(snaps), 1) if snaps else 20.0
                total_active_containers = sum(s.active_containers for s in snaps) if snaps else 0

                jobs_res = await db.execute(select(Job))
                jobs = jobs_res.scalars().all()
                queued_jobs = sum(1 for j in jobs if j.state == JobState.QUEUED)
                running_jobs = sum(1 for j in jobs if j.state == JobState.RUNNING)
                completed_jobs = sum(1 for j in jobs if j.state == JobState.COMPLETED)
                failed_jobs = sum(1 for j in jobs if j.state == JobState.FAILED)

                data = {
                    "type": "telemetry_stream",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "nodes": {
                        "total": total_nodes,
                        "online": online_count,
                        "offline": total_nodes - online_count,
                    },
                    "hardware": {
                        "total_cores": total_cores,
                        "total_ram_gb": round(total_ram_mb / 1024.0, 1),
                        "total_gpus": total_gpus,
                        "total_vram_gb": round(total_vram_mb / 1024.0, 1),
                    },
                    "cluster_load": {
                        "avg_cpu_percent": avg_cpu,
                        "active_containers": total_active_containers,
                    },
                    "jobs": {
                        "total": len(jobs),
                        "queued": queued_jobs,
                        "running": running_jobs,
                        "completed": completed_jobs,
                        "failed": failed_jobs,
                    }
                }
            await websocket.send_json(data)
            await asyncio.sleep(1.5)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WebSocket Telemetry Notice] {e}")


@app.post(f"{settings.API_V1_PREFIX}/system/watchdog-check")
async def trigger_watchdog_check(
    db: AsyncSession = Depends(get_db),
    _admin = Depends(require_admin),
):
    """Manually trigger node heartbeat check and failover eviction (Admin only)."""
    return await watchdog_service.check_nodes_health(db)


@app.get("/api")
async def api_info():
    return {
        "name": settings.PROJECT_NAME,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
