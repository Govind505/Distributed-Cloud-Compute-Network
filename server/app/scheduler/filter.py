"""Filter stage: Remove nodes that cannot satisfy job requirements."""
from datetime import datetime, timezone, timedelta
from app.models.node import ComputeNode, NodeStatus, ResourceSnapshot
from app.models.job import JobRequirement


# Node is considered stale if no snapshot in last 30 seconds
STALE_THRESHOLD_SECONDS = 30


def is_node_eligible(
    node: ComputeNode,
    snapshot: ResourceSnapshot | None,
    requirements: JobRequirement,
    reserved_resources: dict,
) -> tuple[bool, str]:
    """Check if a node can satisfy the job requirements.
    
    Args:
        node: The compute node to check
        snapshot: Latest resource snapshot for the node
        requirements: Job resource requirements
        reserved_resources: Dict of {node_id: {cpu, ram, disk, gpu}} already reserved
    
    Returns:
        Tuple of (is_eligible, reason)
    """
    # Check node status
    if node.status != NodeStatus.ONLINE:
        return False, f"Node status is {node.status.value}, not online"

    # Check if snapshot exists and is fresh
    if snapshot is None:
        return False, "No resource snapshot available"

    now = datetime.now(timezone.utc)
    snapshot_age = (now - snapshot.sampled_at.replace(tzinfo=timezone.utc)).total_seconds()
    if snapshot_age > STALE_THRESHOLD_SECONDS:
        return False, f"Snapshot is stale ({snapshot_age:.0f}s old)"

    # Get already reserved resources for this node
    node_id_str = str(node.id)
    reserved = reserved_resources.get(node_id_str, {"cpu": 0, "ram": 0, "disk": 0, "gpu": 0})

    # Check CPU: free_cpu = total_cores * (1 - usage/100) - reserved
    free_cpu = node.cpu_cores * (1 - snapshot.cpu_usage_percent / 100) - reserved["cpu"]
    if free_cpu < requirements.cpu_cores:
        return False, f"Insufficient CPU: {free_cpu:.1f} free < {requirements.cpu_cores} required"

    # Check RAM
    free_ram = snapshot.ram_free_mb - reserved["ram"]
    if free_ram < requirements.ram_mb:
        return False, f"Insufficient RAM: {free_ram}MB free < {requirements.ram_mb}MB required"

    # Check Disk
    free_disk = snapshot.disk_free_mb - reserved["disk"]
    if free_disk < requirements.disk_mb:
        return False, f"Insufficient disk: {free_disk}MB free < {requirements.disk_mb}MB required"

    # Check GPU
    if requirements.gpu_count > 0:
        available_gpus = node.gpu_count - reserved["gpu"]
        if available_gpus < requirements.gpu_count:
            return False, f"Insufficient GPUs: {available_gpus} free < {requirements.gpu_count} required"
        if requirements.gpu_vram_mb > 0 and node.gpu_vram_mb is not None:
            free_vram = (snapshot.gpu_vram_free_mb or 0)
            if free_vram < requirements.gpu_vram_mb:
                return False, f"Insufficient VRAM: {free_vram}MB < {requirements.gpu_vram_mb}MB required"

    return True, "Eligible"


def filter_nodes(
    nodes: list[ComputeNode],
    snapshots: dict,  # {node_id: ResourceSnapshot}
    requirements: JobRequirement,
    reserved_resources: dict,
) -> list[tuple[ComputeNode, ResourceSnapshot, str]]:
    """Filter out nodes that cannot satisfy requirements.
    
    Returns list of (node, snapshot, reason) tuples for eligible nodes.
    """
    eligible = []
    for node in nodes:
        snapshot = snapshots.get(str(node.id))
        is_eligible, reason = is_node_eligible(node, snapshot, requirements, reserved_resources)
        if is_eligible:
            eligible.append((node, snapshot, reason))
    return eligible
