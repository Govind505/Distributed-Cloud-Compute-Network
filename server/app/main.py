import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db, AsyncSessionLocal
from app.database_seeder import auto_init_and_seed_db
from app.services.watchdog import WatchdogService
from app.utils.dependencies import require_admin
from app.api import auth, nodes, jobs, admin, scheduler

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
