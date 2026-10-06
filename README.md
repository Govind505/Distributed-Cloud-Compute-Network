# Distributed Cloud Compute Network (DCCN)

A distributed cloud compute network for dynamic resource allocation — pools idle heterogeneous workstation and cluster resources into an elastic compute network.

## Quick Start

### 1. Start Infrastructure
```bash
docker-compose up -d
```

### 2. Install Server Dependencies
```bash
cd server
pip install -r requirements.txt
```

### 3. Initialize Database
```bash
cd server
python init_db.py
```

### 4. Run the Server
```bash
cd server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Seed Demo Data
```bash
cd agent
python seed_demo.py
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
