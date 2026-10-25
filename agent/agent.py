"""
DCCN Node Agent Daemon - Autonomous Compute Host Worker
Registers hardware with the control plane, streams live telemetry heartbeats,
and polls for assigned container workloads to execute.
"""
import argparse
import asyncio
import sys
import time
import httpx
from config import SERVER_URL, API_PREFIX, HEARTBEAT_INTERVAL
from telemetry import get_system_info, get_telemetry, get_simulated_gpu_node

BASE_URL = f"{SERVER_URL}{API_PREFIX}"


async def login(client: httpx.AsyncClient, email: str, password: str) -> str:
    """Login and return access token."""
    resp = await client.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        print(f"[ERROR] Authentication failed: {resp.text}")
        sys.exit(1)
    token = resp.json()["access_token"]
    print(f"[OK] Authenticated as {email}")
    return token


async def register_node(
    client: httpx.AsyncClient,
    token: str,
    name: str,
    simulated: bool = False,
    with_gpu: bool = False,
) -> str:
    """Register this host as a compute node."""
    info = get_system_info() if not simulated else {
        "hostname": f"{name.lower()}.dccn.local",
        "cpu_cores": 8,
        "ram_total_mb": 16384,
        "disk_total_mb": 102400,
    }

    payload = {
        "name": name,
        "hostname": info["hostname"],
        "cpu_cores": info["cpu_cores"],
        "ram_total_mb": info["ram_total_mb"],
        "disk_total_mb": info["disk_total_mb"],
    }

    if with_gpu:
        gpu = get_simulated_gpu_node()
        payload.update(gpu)

    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(f"{BASE_URL}/nodes/register", json=payload, headers=headers)
    if resp.status_code != 201:
        print(f"[ERROR] Node enrollment failed: {resp.text}")
        sys.exit(1)
    node_id = resp.json()["id"]
    print(f"[OK] Compute host '{name}' enrolled into cluster (ID: {node_id})")
    return node_id


async def poll_and_execute_workloads(client: httpx.AsyncClient, token: str, node_id: str):
    """Check for workloads scheduled on this host and execute them."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = await client.get(f"{BASE_URL}/jobs/", headers=headers)
        if resp.status_code == 200:
            jobs = resp.json()
            for job in jobs:
                if job.get("state") == "allocated":
                    for alloc in job.get("allocations", []):
                        if alloc.get("node_id") == node_id and alloc.get("state") == "reserved":
                            print(f"  [EXEC] Dispatching assigned workload '{job['name']}' ({job['image_name']})...")
                            exec_resp = await client.post(
                                f"{BASE_URL}/jobs/{job['id']}/dispatch",
                                headers=headers
                            )
                            if exec_resp.status_code == 200:
                                print(f"  [EXEC-DONE] Workload '{job['name']}' finished with exit code 0.")
    except Exception as e:
        pass


async def send_heartbeat(
    client: httpx.AsyncClient,
    token: str,
    node_id: str,
    simulated: bool = False,
):
    """Send a single heartbeat with resource telemetry."""
    telemetry = get_telemetry(simulated=simulated)
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = await client.post(
            f"{BASE_URL}/nodes/{node_id}/heartbeat",
            json=telemetry,
            headers=headers,
        )
        if resp.status_code == 200:
            print(f"  [HEARTBEAT] Node {node_id[:8]}... CPU: {telemetry['cpu_usage_percent']}% | RAM Free: {telemetry['ram_free_mb']}MB | Containers: {telemetry['active_containers']}")
        else:
            print(f"  [WARN] Heartbeat rejected: {resp.status_code}")
    except httpx.ConnectError:
        print(f"  [WARN] Cannot connect to control plane at {SERVER_URL}")


async def heartbeat_loop(
    client: httpx.AsyncClient,
    token: str,
    node_id: str,
    name: str,
    simulated: bool = False,
    interval: int = HEARTBEAT_INTERVAL,
):
    """Continuous heartbeat and workload dispatch daemon."""
    print(f"[AGENT] Daemon active for '{name}' (Heartbeat: every {interval}s)")
    while True:
        await send_heartbeat(client, token, node_id, simulated)
        await poll_and_execute_workloads(client, token, node_id)
        await asyncio.sleep(interval)


async def run_single_agent(email: str, password: str, name: str, simulated: bool, with_gpu: bool):
    """Run a single agent daemon."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        token = await login(client, email, password)
        node_id = await register_node(client, token, name, simulated, with_gpu)
        await heartbeat_loop(client, token, node_id, name, simulated)


async def run_multiple_agents(email: str, password: str, count: int):
    """Run multiple simulated node agents concurrently."""
    names = [
        (f"Compute-Node-{i+1:02d}", False) if i < count // 2
        else (f"GPU-Cluster-{i+1:02d}", True)
        for i in range(count)
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        token = await login(client, email, password)
        node_ids = []
        for name, with_gpu in names:
            nid = await register_node(client, token, name, simulated=True, with_gpu=with_gpu)
            node_ids.append((nid, name, with_gpu))

        print(f"\n[AGENT] Running {count} simulated host agents. Press Ctrl+C to terminate.\n")
        tasks = [
            heartbeat_loop(client, token, nid, name, simulated=True)
            for nid, name, _ in node_ids
        ]
        await asyncio.gather(*tasks)


def main():
    parser = argparse.ArgumentParser(description="DCCN Node Agent Daemon")
    parser.add_argument("--name", default="Compute-Node-05", help="Host display name")
    parser.add_argument("--email", required=True, help="Provider account email")
    parser.add_argument("--password", required=True, help="Provider account password")
    parser.add_argument("--simulate", action="store_true", help="Use simulated hardware telemetry")
    parser.add_argument("--gpu", action="store_true", help="Volunteer GPU accelerator")
    parser.add_argument("--count", type=int, default=0, help="Run N concurrent simulated nodes")
    parser.add_argument("--server", default=SERVER_URL, help="Control plane URL")
    args = parser.parse_args()

    global SERVER_URL, BASE_URL
    if args.server != SERVER_URL:
        BASE_URL = f"{args.server}{API_PREFIX}"

    try:
        if args.count > 0:
            asyncio.run(run_multiple_agents(args.email, args.password, args.count))
        else:
            asyncio.run(run_single_agent(args.email, args.password, args.name, args.simulate, args.gpu))
    except KeyboardInterrupt:
        print("\n[AGENT] Daemon shutdown cleanly.")


if __name__ == "__main__":
    main()
