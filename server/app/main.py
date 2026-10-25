from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.api import auth, nodes, jobs, admin, scheduler

settings = get_settings()

from contextlib import asynccontextmanager
from app.database_seeder import auto_init_and_seed_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await auto_init_and_seed_db()
    except Exception as e:
        print(f"[DCCN Startup Error] {e}")
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="A distributed compute network for dynamic resource allocation",
    version="0.1.0",
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

import os
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/api")
async def api_info():
    return {
        "name": settings.PROJECT_NAME,
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
