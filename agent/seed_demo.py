"""Seed the database with demo data for the mid-evaluation presentation.

Usage:
    python seed_demo.py

This script:
1. Creates 3 users (admin, provider, compute_user)
2. Registers 4 compute nodes (2 CPU-only, 2 with GPU)
3. Submits 3 sample jobs
4. Sends some initial heartbeats so the scheduler has data
5. Triggers scheduling for the jobs
"""
import asyncio
import httpx
import time

SERVER = "http://localhost:8000/api/v1"

# Enterprise Demo users
USERS = [
    {"email": "admin@dccn.network", "username": "admin", "password": "admin123", "role": "admin"},
    {"email": "provider@dccn.network", "username": "provider", "password": "provider123", "role": "compute_provider"},
    {"email": "client@dccn.network", "username": "client", "password": "client123", "role": "compute_user"},
]

# Distributed compute nodes
NODES = [
    {"name": "Compute-Node-01", "hostname": "worker-01.dccn.local", "cpu_cores": 8, "ram_total_mb": 16384, "disk_total_mb": 512000},
    {"name": "Compute-Node-02", "hostname": "worker-02.dccn.local", "cpu_cores": 4, "ram_total_mb": 8192, "disk_total_mb": 256000},
    {"name": "GPU-Cluster-01", "hostname": "gpu-host-01.dccn.local", "cpu_cores": 16, "ram_total_mb": 32768, "disk_total_mb": 1024000, "gpu_model": "NVIDIA RTX 3080", "gpu_count": 1, "gpu_vram_mb": 10240},
    {"name": "GPU-Cluster-02", "hostname": "gpu-host-02.dccn.local", "cpu_cores": 12, "ram_total_mb": 24576, "disk_total_mb": 512000, "gpu_model": "NVIDIA Tesla T4", "gpu_count": 2, "gpu_vram_mb": 16384},
]

# Demo heartbeats (telemetry)
HEARTBEATS = [
    {"cpu_usage_percent": 25.0, "ram_free_mb": 12000, "disk_free_mb": 400000, "active_containers": 0},
    {"cpu_usage_percent": 60.0, "ram_free_mb": 4000, "disk_free_mb": 200000, "active_containers": 1},
    {"cpu_usage_percent": 15.0, "ram_free_mb": 28000, "disk_free_mb": 900000, "gpu_utilization_percent": 10.0, "gpu_vram_free_mb": 9000, "active_containers": 0},
    {"cpu_usage_percent": 40.0, "ram_free_mb": 18000, "disk_free_mb": 400000, "gpu_utilization_percent": 30.0, "gpu_vram_free_mb": 14000, "active_containers": 1},
]

# Demo jobs
JOBS = [
    {
        "name": "Matrix Multiplication Benchmark",
        "image_name": "python:3.11-slim",
        "command": "python -c 'import numpy; a=numpy.random.rand(1000,1000); b=a@a; print(b.shape)'",
        "priority": 5,
        "timeout_seconds": 600,
        "requirements": {"cpu_cores": 2.0, "ram_mb": 2048, "disk_mb": 500, "gpu_count": 0, "gpu_vram_mb": 0},
    },
    {
        "name": "Image Classification Inference",
        "image_name": "pytorch/pytorch:latest",
        "command": "python classify.py --model resnet50 --input /data/images",
        "priority": 7,
        "timeout_seconds": 1800,
        "requirements": {"cpu_cores": 4.0, "ram_mb": 8192, "disk_mb": 2048, "gpu_count": 1, "gpu_vram_mb": 4096},
    },
    {
        "name": "Data Compression Test",
        "image_name": "ubuntu:22.04",
        "command": "gzip -9 /data/large_file.dat",
        "priority": 3,
        "timeout_seconds": 300,
        "requirements": {"cpu_cores": 1.0, "ram_mb": 512, "disk_mb": 1024, "gpu_count": 0, "gpu_vram_mb": 0},
    },
]


async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("=" * 60)
        print("  DCCN Demo Data Seeder")
        print("=" * 60)

        # Step 0: Check server connectivity
        server_ready = False
        for _ in range(10):
            try:
                res = await client.get("http://localhost:8000/health")
                if res.status_code == 200:
                    server_ready = True
                    break
            except Exception:
                await asyncio.sleep(1)

        if not server_ready:
            print("\n[ERROR] Could not connect to DCCN server at http://localhost:8000.")
            print("[INFO] Please start the server first by running run_demo.bat or:")
            print("       cd server && python -m uvicorn app.main:app --port 8000\n")
            return

        # Step 1: Register users
        print("\n--- Step 1: Registering users ---")
        tokens = {}
        for user in USERS:
            resp = await client.post(f"{SERVER}/auth/register", json=user)
            if resp.status_code == 201:
                print(f"  [OK] Created user: {user['username']} ({user['role']})")
            else:
                try:
                    err_msg = resp.json().get('detail', resp.text)
                except Exception:
                    err_msg = resp.text[:120]
                print(f"  [SKIP] {user['username']}: {err_msg}")

            # Login to get token
            resp = await client.post(f"{SERVER}/auth/login", json={"email": user["email"], "password": user["password"]})
            if resp.status_code == 200:
                tokens[user["role"]] = resp.json()["access_token"]

        if "compute_provider" not in tokens:
            print("[FATAL] Could not log in as provider")
            return

        # Step 2: Register nodes
        print("\n--- Step 2: Registering compute nodes ---")
        provider_headers = {"Authorization": f"Bearer {tokens['compute_provider']}"}
        admin_headers = {"Authorization": f"Bearer {tokens['admin']}"}
        node_ids = []

        for node in NODES:
            resp = await client.post(f"{SERVER}/nodes/register", json=node, headers=provider_headers)
            if resp.status_code == 201:
                nid = resp.json()["id"]
                node_ids.append(nid)
                print(f"  [OK] Registered node: {node['name']} -> {nid[:8]}...")
            else:
                print(f"  [SKIP] {node['name']}: {resp.json().get('detail', resp.text)}")

        # Step 3: Approve nodes (admin)
        print("\n--- Step 3: Approving nodes ---")
        for nid in node_ids:
            resp = await client.post(f"{SERVER}/nodes/{nid}/approve", headers=admin_headers)
            if resp.status_code == 200:
                print(f"  [OK] Approved node {nid[:8]}...")
            else:
                print(f"  [WARN] Could not approve {nid[:8]}...: {resp.text}")

        # Step 4: Send heartbeats
        print("\n--- Step 4: Sending heartbeats ---")
        for i, nid in enumerate(node_ids):
            hb = HEARTBEATS[i % len(HEARTBEATS)]
            resp = await client.post(f"{SERVER}/nodes/{nid}/heartbeat", json=hb, headers=provider_headers)
            if resp.status_code == 200:
                print(f"  [OK] Heartbeat sent for node {nid[:8]}...")
            else:
                print(f"  [WARN] Heartbeat failed for {nid[:8]}...: {resp.text}")

        # Step 5: Submit jobs
        print("\n--- Step 5: Submitting jobs ---")
        client_headers = {"Authorization": f"Bearer {tokens.get('compute_user', tokens['admin'])}"}
        job_ids = []

        for job in JOBS:
            resp = await client.post(f"{SERVER}/jobs/", json=job, headers=client_headers)
            if resp.status_code == 201:
                jid = resp.json()["id"]
                job_ids.append(jid)
                print(f"  [OK] Submitted job: {job['name']} -> {jid[:8]}...")
            else:
                print(f"  [FAIL] {job['name']}: {resp.json().get('detail', resp.text)}")

        # Step 6: Schedule jobs
        print("\n--- Step 6: Scheduling jobs ---")
        for jid in job_ids:
            resp = await client.post(f"{SERVER}/scheduler/schedule/{jid}", headers=client_headers)
            if resp.status_code == 200:
                data = resp.json()
                print(f"  [OK] Job {jid[:8]}... -> Node '{data.get('node_name', '?')}' (score: {data.get('score', '?')})")
                if data.get("score_breakdown"):
                    bd = data["score_breakdown"]
                    print(f"        Breakdown: CPU={bd.get('cpu',0):.2f} MEM={bd.get('memory',0):.2f} GPU={bd.get('gpu',0):.2f} LOAD={bd.get('load',0):.2f} NET={bd.get('network',0):.2f} REL={bd.get('reliability',0):.2f} PACK={bd.get('packing',0):.2f}")
            else:
                print(f"  [FAIL] Could not schedule {jid[:8]}...: {resp.json().get('detail', resp.text)}")

        # Step 7: Show dashboard
        print("\n--- Step 7: Dashboard ---")
        resp = await client.get(f"{SERVER}/admin/dashboard", headers=admin_headers)
        if resp.status_code == 200:
            dash = resp.json()
            print(f"  Users:  {dash['users']['total']}")
            print(f"  Nodes:  {dash['nodes']['total']} total, {dash['nodes']['online']} online")
            print(f"  Jobs:   {dash['jobs']['total']} total, {dash['jobs']['queued']} queued, {dash['jobs']['completed']} completed")

        print("\n" + "=" * 60)
        print("  Demo data seeded successfully!")
        print("  Admin login: admin@dccn.network / admin123")
        print("  Client login: client@dccn.network / client123")
        print("  Provider login: provider@dccn.network / provider123")
        print("  API docs: http://localhost:8000/docs")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
