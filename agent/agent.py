"""DCCN Node Agent - registers with the control plane and sends periodic heartbeats.

Usage:
    # Register and run with real system telemetry:
    python agent.py --name "Compute-Node-01" --email provider@dccn.network --password secret123

    # Register with simulated data (for demo/testing):
    python agent.py --name "Sim-Node-01" --email provider@dccn.network --password secret123 --simulate

    # Simulate multiple nodes at once:
    python agent.py --email provider@dccn.network --password secret123 --simulate --count 3
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
        print(f"[ERROR] Login failed: {resp.text}")
        sys.exit(1)
    token = resp.json()["access_token"]
    print(f"[OK] Logged in as {email}")
    return token


async def register_node(
    client: httpx.AsyncClient,
    token: str,
    name: str,
    simulated: bool = False,
    with_gpu: bool = False,
) -> str:
    """Register a compute node and return its ID."""
    info = get_system_info() if not simulated else {
        "hostname": f"{name}.local",
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
        print(f"[ERROR] Node registration failed: {resp.text}")
        sys.exit(1)
    node_id = resp.json()["id"]
    print(f"[OK] Node '{name}' registered with ID: {node_id}")
    return node_id


async def send_heartbeat(
    client: httpx.AsyncClient,
    token: str,
    node_id: str,
    simulated: bool = False,
):
    """Send a single heartbeat with telemetry data."""
    telemetry = get_telemetry(simulated=simulated)
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = await client.post(
            f"{BASE_URL}/nodes/{node_id}/heartbeat",
            json=telemetry,
            headers=headers,
        )
        if resp.status_code == 200:
            print(f"  [HEARTBEAT] Node {node_id[:8]}... CPU: {telemetry['cpu_usage_percent']}% | RAM free: {telemetry['ram_free_mb']}MB | Containers: {telemetry['active_containers']}")
        else:
            print(f"  [WARN] Heartbeat failed: {resp.status_code} {resp.text}")
    except httpx.ConnectError:
        print(f"  [WARN] Cannot reach server at {SERVER_URL}")


async def heartbeat_loop(
    client: httpx.AsyncClient,
    token: str,
    node_id: str,
    name: str,
    simulated: bool = False,
    interval: int = HEARTBEAT_INTERVAL,
):
    """Continuously send heartbeats."""
    print(f"[AGENT] Starting heartbeat loop for '{name}' (every {interval}s)")
    while True:
        await send_heartbeat(client, token, node_id, simulated)
        await asyncio.sleep(interval)


async def run_single_agent(email: str, password: str, name: str, simulated: bool, with_gpu: bool):
    """Run a single agent instance."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        token = await login(client, email, password)
        node_id = await register_node(client, token, name, simulated, with_gpu)
        await heartbeat_loop(client, token, node_id, name, simulated)


async def run_multiple_agents(email: str, password: str, count: int):
    """Run multiple simulated agent instances."""
    agents = []
    names = [
        (f"Sim-CPU-Node-{i+1}", False) if i < count // 2
        else (f"Sim-GPU-Node-{i+1}", True)
        for i in range(count)
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        token = await login(client, email, password)
        node_ids = []
        for name, with_gpu in names:
            nid = await register_node(client, token, name, simulated=True, with_gpu=with_gpu)
            node_ids.append((nid, name, with_gpu))

        print(f"\n[AGENT] Running {count} simulated nodes. Press Ctrl+C to stop.\n")
        tasks = [
            heartbeat_loop(client, token, nid, name, simulated=True)
            for nid, name, _ in node_ids
        ]
        await asyncio.gather(*tasks)


def main():
    parser = argparse.ArgumentParser(description="DCCN Node Agent")
    parser.add_argument("--name", default="Agent-Node-01", help="Node display name")
    parser.add_argument("--email", required=True, help="Provider account email")
    parser.add_argument("--password", required=True, help="Provider account password")
    parser.add_argument("--simulate", action="store_true", help="Use simulated telemetry")
    parser.add_argument("--gpu", action="store_true", help="Simulate GPU hardware")
    parser.add_argument("--count", type=int, default=0, help="Run N simulated nodes (overrides --name)")
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
        print("\n[AGENT] Shutting down.")


if __name__ == "__main__":
    main()
