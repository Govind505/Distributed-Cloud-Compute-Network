"""Ranker stage: Score eligible nodes using a weighted multi-factor formula.

Score(i,j) = 0.22*C + 0.18*M + 0.25*G + 0.12*L + 0.08*N + 0.10*R + 0.05*P

C = normalized free CPU
M = normalized free memory
G = GPU suitability (0 if no GPU needed, else match quality)
L = inverse current utilization (lower load = higher score)
N = inverse network latency
R = reliability score (based on uptime/heartbeats)
P = packing efficiency (leave useful resources for future jobs)
"""
from datetime import datetime, timezone
from app.models.node import ComputeNode, ResourceSnapshot
from app.models.job import JobRequirement


# Scoring weights from the synopsis
WEIGHTS = {
    "cpu": 0.22,       # C - free CPU
    "memory": 0.18,    # M - free memory
    "gpu": 0.25,       # G - GPU suitability
    "load": 0.12,      # L - inverse utilization
    "network": 0.08,   # N - inverse network latency
    "reliability": 0.10,  # R - reliability
    "packing": 0.05,   # P - packing efficiency
}


def _normalize(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp value to [0, 1] range."""
    if max_val <= min_val:
        return 0.0
    return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))


def score_node(
    node: ComputeNode,
    snapshot: ResourceSnapshot,
    requirements: JobRequirement,
    reserved_resources: dict,
    max_rtt: float = 100.0,
) -> tuple[float, dict]:
    """Calculate a composite score for a node-job pair.
    
    Args:
        node: The compute node
        snapshot: Latest resource snapshot
        requirements: Job requirements
        reserved_resources: Already reserved resources on this node
        max_rtt: Maximum RTT in the cluster for normalization
    
    Returns:
        Tuple of (total_score, score_breakdown)
    """
    node_id_str = str(node.id)
    reserved = reserved_resources.get(node_id_str, {"cpu": 0, "ram": 0, "disk": 0, "gpu": 0})

    # C - Normalized free CPU (higher free = better)
    free_cpu = node.cpu_cores * (1 - snapshot.cpu_usage_percent / 100) - reserved["cpu"]
    cpu_score = _normalize(free_cpu / max(node.cpu_cores, 1))

    # M - Normalized free memory
    free_ram = snapshot.ram_free_mb - reserved["ram"]
    mem_score = _normalize(free_ram / max(node.ram_total_mb, 1))

    # G - GPU suitability
    if requirements.gpu_count == 0:
        # Non-GPU job: prefer nodes WITHOUT GPUs (save GPUs for GPU jobs)
        gpu_score = 1.0 if node.gpu_count == 0 else 0.5
    else:
        available_gpus = node.gpu_count - reserved["gpu"]
        if available_gpus >= requirements.gpu_count:
            # Score based on fit (don't waste a 24GB card on a 4GB request)
            if node.gpu_vram_mb and requirements.gpu_vram_mb > 0:
                vram_ratio = requirements.gpu_vram_mb / node.gpu_vram_mb
                gpu_score = 1.0 - abs(0.7 - vram_ratio)  # Best when using ~70% VRAM
            else:
                gpu_score = 0.8  # Has GPU, unknown VRAM match
        else:
            gpu_score = 0.0

    # L - Inverse utilization (lower CPU usage = higher score)
    load_score = 1.0 - (snapshot.cpu_usage_percent / 100.0)

    # N - Inverse network latency
    if max_rtt > 0:
        network_score = 1.0 - _normalize(snapshot.rtt_ms, 0, max_rtt)
    else:
        network_score = 1.0

    # R - Reliability (simplified: based on node being online and recent heartbeat)
    now = datetime.now(timezone.utc)
    if node.last_seen:
        last_seen_utc = node.last_seen.replace(tzinfo=timezone.utc) if node.last_seen.tzinfo is None else node.last_seen
        seconds_since_seen = (now - last_seen_utc).total_seconds()
        reliability_score = _normalize(1.0 - (seconds_since_seen / 60.0))  # Full score if seen <60s ago
    else:
        reliability_score = 0.5  # Unknown reliability

    # P - Packing efficiency (leave useful residual resources)
    residual_cpu = (free_cpu - requirements.cpu_cores) / max(node.cpu_cores, 1)
    residual_ram = (free_ram - requirements.ram_mb) / max(node.ram_total_mb, 1)
    # Good packing: use resources but leave enough for at least another small job
    packing_score = _normalize(min(residual_cpu, residual_ram), 0, 0.5) if residual_cpu > 0 and residual_ram > 0 else 0.0

    # Calculate weighted total
    breakdown = {
        "cpu": round(cpu_score, 4),
        "memory": round(mem_score, 4),
        "gpu": round(gpu_score, 4),
        "load": round(load_score, 4),
        "network": round(network_score, 4),
        "reliability": round(reliability_score, 4),
        "packing": round(packing_score, 4),
    }

    total = sum(WEIGHTS[k] * breakdown[k] for k in WEIGHTS)
    breakdown["total"] = round(total, 4)
    breakdown["weights"] = WEIGHTS

    return total, breakdown


def rank_nodes(
    eligible: list[tuple[ComputeNode, ResourceSnapshot, str]],
    requirements: JobRequirement,
    reserved_resources: dict,
) -> list[tuple[ComputeNode, float, dict]]:
    """Rank eligible nodes by composite score.
    
    Returns list of (node, score, breakdown) sorted by score descending.
    """
    # Find max RTT for normalization
    max_rtt = max((snap.rtt_ms for _, snap, _ in eligible), default=1.0)
    if max_rtt == 0:
        max_rtt = 1.0

    scored = []
    for node, snapshot, _ in eligible:
        score, breakdown = score_node(
            node, snapshot, requirements, reserved_resources, max_rtt
        )
        scored.append((node, score, breakdown))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
