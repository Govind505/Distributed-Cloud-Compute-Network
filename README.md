# Distributed Cloud Compute Network (DCCN)

A distributed cloud compute network for dynamic resource allocation — pools idle heterogeneous workstation and cluster resources into an elastic compute network.

## Quick Start

### 1-Click Launch (Recommended)
Double-click **`run_demo.bat`** (Windows) or run:
```bash
python run.py
```
This automatically verifies port 8000, initializes the database schema, seeds the cluster with 4 compute nodes and 3 enterprise accounts, boots the FastAPI control server, and opens **`http://localhost:8000/login`** in your browser.

### Manual Execution
```bash
cd server
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 6. Access Dedicated Portals
- **Portal Gateway (Role Selector)**: http://localhost:8000/login
- **Compute Client Portal**: http://localhost:8000/client
- **Compute Provider Portal**: http://localhost:8000/provider
- **Administrator Console**: http://localhost:8000/admin
- **Unified Operations Dashboard**: http://localhost:8000/dashboard
- **Interactive API Documentation**: http://localhost:8000/docs

### Demo Credentials
- **Compute Client**: `client@dccn.network` / `client123`
- **Compute Provider**: `provider@dccn.network` / `provider123`
- **Administrator**: `admin@dccn.network` / `admin123`

## Team
- Govind Choudhary (500123445)
- Neetesh Bisht (500124582)
- Yash Khanna (500119667)

## Tech Stack
- **Backend**: Python, FastAPI, SQLAlchemy, PostgreSQL, Redis
- **Frontend**: React, Vite
- **Agent**: Python, psutil
- **Infrastructure**: Docker, Docker Compose
