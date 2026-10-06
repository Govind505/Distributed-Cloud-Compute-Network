"""Agent configuration."""
import os

# Control plane server URL
SERVER_URL = os.getenv("DCCN_SERVER_URL", "http://localhost:8000")
API_PREFIX = os.getenv("DCCN_API_PREFIX", "/api/v1")

# Agent credentials (set via env or command line)
AGENT_EMAIL = os.getenv("DCCN_AGENT_EMAIL", "")
AGENT_PASSWORD = os.getenv("DCCN_AGENT_PASSWORD", "")

# Telemetry intervals
HEARTBEAT_INTERVAL = int(os.getenv("DCCN_HEARTBEAT_INTERVAL", "10"))
TELEMETRY_INTERVAL = int(os.getenv("DCCN_TELEMETRY_INTERVAL", "5"))
