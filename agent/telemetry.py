"""Telemetry collection - generates simulated or real system metrics."""
import random
import platform
import time

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def get_system_info() -> dict:
    """Get static system hardware information."""
    if HAS_PSUTIL:
        return {
            "hostname": platform.node(),
            "cpu_cores": psutil.cpu_count(logical=True),
            "ram_total_mb": psutil.virtual_memory().total // (1024 * 1024),
            "disk_total_mb": psutil.disk_usage('/').total // (1024 * 1024) if platform.system() != 'Windows' else psutil.disk_usage('C:\\').total // (1024 * 1024),
        }
    else:
        # Simulated values
        return {
            "hostname": platform.node() or "sim-node-01",
            "cpu_cores": random.choice([4, 8, 12, 16]),
            "ram_total_mb": random.choice([4096, 8192, 16384, 32768]),
            "disk_total_mb": random.choice([51200, 102400, 204800]),
        }


def get_telemetry(simulated: bool = False) -> dict:
    """Collect current resource utilization metrics."""
    if not simulated and HAS_PSUTIL:
        mem = psutil.virtual_memory()
        if platform.system() == 'Windows':
            disk = psutil.disk_usage('C:\\')
        else:
            disk = psutil.disk_usage('/')
        return {
            "cpu_usage_percent": psutil.cpu_percent(interval=1),
            "ram_free_mb": mem.available // (1024 * 1024),
            "disk_free_mb": disk.free // (1024 * 1024),
            "gpu_utilization_percent": None,  # No GPU monitoring in basic agent
            "gpu_vram_free_mb": None,
            "active_containers": 0,
        }
    else:
        # Simulated telemetry with some realistic variance
        return {
            "cpu_usage_percent": round(random.uniform(5.0, 75.0), 1),
            "ram_free_mb": random.randint(1024, 12288),
            "disk_free_mb": random.randint(10240, 102400),
            "gpu_utilization_percent": round(random.uniform(0, 60.0), 1) if random.random() > 0.5 else None,
            "gpu_vram_free_mb": random.randint(2048, 8192) if random.random() > 0.5 else None,
            "active_containers": random.randint(0, 3),
        }


def get_simulated_gpu_node() -> dict:
    """Get simulated GPU hardware specs."""
    gpus = [
        {"gpu_model": "NVIDIA RTX 3060", "gpu_count": 1, "gpu_vram_mb": 12288},
        {"gpu_model": "NVIDIA RTX 3080", "gpu_count": 1, "gpu_vram_mb": 10240},
        {"gpu_model": "NVIDIA RTX 4090", "gpu_count": 1, "gpu_vram_mb": 24576},
        {"gpu_model": "NVIDIA Tesla T4", "gpu_count": 2, "gpu_vram_mb": 16384},
    ]
    return random.choice(gpus)
