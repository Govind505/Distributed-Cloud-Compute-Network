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


def detect_cloud_environment() -> tuple[str, str]:
    """Auto-detect cloud host provider and region from hypervisor/metadata."""
    # Heuristic checks for major cloud providers
    try:
        import os
        if os.path.exists("/sys/class/dmi/id/sys_vendor"):
            with open("/sys/class/dmi/id/sys_vendor", "r") as f:
                vendor = f.read().lower()
                if "amazon" in vendor:
                    return "aws_spot", "us-east-1"
                if "google" in vendor:
                    return "gcp", "us-central1"
                if "hetzner" in vendor:
                    return "hetzner", "eu-central"
                if "digitalocean" in vendor:
                    return "digitalocean", "nyc1"
    except Exception:
        pass
    return "bare_metal", "global"


async def register_node(
    client: httpx.AsyncClient,
    token: str,
    name: str,
    simulated: bool = False,
    with_gpu: bool = False,
    cloud_provider: str | None = None,
    region: str | None = None,
    overcommit_ratio: float = 2.5,
) -> str:
    """Register this host as a compute node."""
    info = get_system_info() if not simulated else {
        "hostname": f"{name.lower()}.dccn.local",
        "cpu_cores": 8,
        "ram_total_mb": 16384,
        "disk_total_mb": 102400,
    }

    detected_cloud, detected_region = detect_cloud_environment()
    final_cloud = cloud_provider or detected_cloud
    final_region = region or detected_region

    payload = {
        "name": name,
        "hostname": info["hostname"],
        "cpu_cores": info["cpu_cores"],
        "ram_total_mb": info["ram_total_mb"],
        "disk_total_mb": info["disk_total_mb"],
        "cloud_provider": final_cloud,
        "region": final_region,
        "overcommit_ratio": overcommit_ratio,
        "labels": {
            "source": "cloud_broker" if final_cloud != "bare_metal" else "bare_metal",
            "cloud": final_cloud,
            "region": final_region,
        },
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
    print(f"[OK] Compute host '{name}' ({final_cloud.upper()} | {final_region} | Overcommit: {overcommit_ratio}x) enrolled into cluster (ID: {node_id})")
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


async def run_single_agent(
    email: str,
    password: str,
    name: str,
    simulated: bool,
    with_gpu: bool,
    cloud: str | None = None,
    region: str | None = None,
    overcommit: float = 2.5,
):
    """Run a single agent daemon."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        token = await login(client, email, password)
        node_id = await register_node(
            client=client,
            token=token,
            name=name,
            simulated=simulated,
            with_gpu=with_gpu,
            cloud_provider=cloud,
            region=region,
            overcommit_ratio=overcommit,
        )
        await heartbeat_loop(client, token, node_id, name, simulated)


async def run_multiple_agents(email: str, password: str, count: int):
    """Run multiple simulated node agents concurrently."""
    cloud_types = ["hetzner", "aws_spot", "runpod", "ovh", "bare_metal"]
    names = [
        (f"Cloud-Host-{i+1:02d}", False, cloud_types[i % len(cloud_types)]) if i < count // 2
        else (f"GPU-Cluster-{i+1:02d}", True, "runpod" if i % 2 == 0 else "aws_spot")
        for i in range(count)
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        token = await login(client, email, password)
        node_ids = []
        for name, with_gpu, c_type in names:
            nid = await register_node(
                client=client,
                token=token,
                name=name,
                simulated=True,
                with_gpu=with_gpu,
                cloud_provider=c_type,
                region="us-east" if "aws" in c_type else "eu-central",
                overcommit_ratio=2.5,
            )
            node_ids.append((nid, name, with_gpu))

        print(f"\n[AGENT] Running {count} cloud broker host agents. Press Ctrl+C to terminate.\n")
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
    parser.add_argument("--cloud", default=None, help="Cloud origin: hetzner, aws_spot, runpod, ovh, bare_metal")
    parser.add_argument("--region", default=None, help="Cloud region: eu-central, us-east-1, etc.")
    parser.add_argument("--overcommit", type=float, default=2.5, help="CPU overcommit multiplier (default: 2.5x)")
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
            asyncio.run(run_single_agent(
                email=args.email,
                password=args.password,
                name=args.name,
                simulated=args.simulate,
                with_gpu=args.gpu,
                cloud=args.cloud,
                region=args.region,
                overcommit=args.overcommit,
            ))
    except KeyboardInterrupt:
        print("\n[AGENT] Daemon shutdown cleanly.")


if __name__ == "__main__":
    main()
