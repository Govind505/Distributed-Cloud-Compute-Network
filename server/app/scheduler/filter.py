"""Filter stage: Remove nodes that cannot satisfy job requirements."""
from datetime import datetime, timezone
from app.models.node import ComputeNode, NodeStatus, ResourceSnapshot
from app.models.job import JobRequirement


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
    # Check node status - must be ONLINE
    if node.status != NodeStatus.ONLINE:
        return False, f"Node status is {node.status.value}, not online"

    # Use latest telemetry snapshot if available, or fall back to node hardware specs
    if snapshot is not None:
        cpu_usage = snapshot.cpu_usage_percent
        ram_free = snapshot.ram_free_mb
        disk_free = snapshot.disk_free_mb
        gpu_vram_free = snapshot.gpu_vram_free_mb or (node.gpu_vram_mb or 0)
    else:
        cpu_usage = 10.0
        ram_free = int(node.ram_total_mb * 0.8)
        disk_free = int(node.disk_total_mb * 0.8)
        gpu_vram_free = int((node.gpu_vram_mb or 0) * 0.8)

    # Get already reserved resources for this node
    node_id_str = str(node.id)
    reserved = reserved_resources.get(node_id_str, {"cpu": 0, "ram": 0, "disk": 0, "gpu": 0})

    # 1. Check CPU with Fractional Overcommit Slicing
    overcommit = getattr(node, "overcommit_ratio", 2.5) or 2.5
    effective_cores = node.cpu_cores * overcommit
    free_cpu = effective_cores * (1.0 - (cpu_usage / 100.0)) - reserved["cpu"]
    if free_cpu < requirements.cpu_cores:
        return False, f"Insufficient CPU: {free_cpu:.2f} free < {requirements.cpu_cores} required (Overcommit: {overcommit}x)"

    # 2. Check RAM
    free_ram = ram_free - reserved["ram"]
    if free_ram < requirements.ram_mb:
        return False, f"Insufficient RAM: {free_ram}MB free < {requirements.ram_mb}MB required"

    # 3. Check Disk
    free_disk = disk_free - reserved["disk"]
    if free_disk < requirements.disk_mb:
        return False, f"Insufficient disk: {free_disk}MB free < {requirements.disk_mb}MB required"

    # 4. Check GPU
    if requirements.gpu_count > 0:
        available_gpus = node.gpu_count - reserved["gpu"]
        if available_gpus < requirements.gpu_count:
            return False, f"Insufficient GPUs: {available_gpus} free < {requirements.gpu_count} required"
        if requirements.gpu_vram_mb > 0 and (node.gpu_vram_mb or 0) > 0:
            if gpu_vram_free < requirements.gpu_vram_mb:
                return False, f"Insufficient VRAM: {gpu_vram_free}MB < {requirements.gpu_vram_mb}MB required"

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
