"""
Distributed Cloud Compute Network (DCCN)
Local Demonstration Platform & Server Launcher

Usage:
    python run.py
"""
import os
import sys
import time
import subprocess
import threading
import webbrowser

# Resolve paths
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(ROOT_DIR, "server")

if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)


def kill_stale_port_8000():
    """Ensure port 8000 is clean by terminating any old background listener."""
    if sys.platform == "win32":
        try:
            output = subprocess.check_output(
                'netstat -ano | findstr :8000', shell=True, stderr=subprocess.DEVNULL
            ).decode()
            pids = set()
            for line in output.strip().splitlines():
                parts = line.split()
                if len(parts) >= 5 and "LISTENING" in line:
                    pids.add(parts[-1])
            current_pid = str(os.getpid())
            for pid in pids:
                if pid and pid != current_pid:
                    subprocess.call(
                        f"taskkill /F /PID {pid}",
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            if pids:
                time.sleep(0.5)
        except Exception:
            pass


def open_browser_delayed(url: str, delay: float = 1.5):
    """Launch the browser after the server has initialized."""
    def _open():
        time.sleep(delay)
        webbrowser.open(url)
    t = threading.Thread(target=_open, daemon=True)
    t.start()


def main():
    print("=" * 65)
    print("  Distributed Cloud Compute Network (DCCN)")
    print("  Enterprise Dynamic Resource Allocation Platform")
    print("=" * 65)
    print()
    print("[1/3] Preparing port 8000 ...")
    kill_stale_port_8000()
    print("      Port 8000 is ready.")
    print()
    print("[2/3] Initializing automated cluster environment...")
    print("      Database schema, accounts, and nodes will load on startup.")
    print()
    print("[3/3] Opening browser at http://localhost:8000/login ...")
    open_browser_delayed("http://localhost:8000/login", delay=1.5)

    print()
    print("=" * 65)
    print("  DCCN Control Plane is LIVE on http://localhost:8000")
    print("=" * 65)
    print("  Available Dedicated Consoles:")
    print("    * Portal Gateway / Switcher:  http://localhost:8000/login")
    print("    * Compute Client Portal:      http://localhost:8000/client")
    print("    * Compute Provider Portal:    http://localhost:8000/provider")
    print("    * Administrator Console:      http://localhost:8000/admin")
    print("    * Operations Dashboard:       http://localhost:8000/dashboard")
    print("    * Swagger API Documentation:  http://localhost:8000/docs")
    print("=" * 65)
    print("  Credentials:")
    print("    - Compute Client:    client@dccn.network   / client123")
    print("    - Compute Provider:  provider@dccn.network / provider123")
    print("    - Administrator:     admin@dccn.network    / admin123")
    print("=" * 65)
    print("  Press Ctrl+C to stop the server.\n")

    os.chdir(SERVER_DIR)
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")


if __name__ == "__main__":
    main()
