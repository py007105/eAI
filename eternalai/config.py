"""Static configuration: service topology, endpoints, policy limits. Env overrides only."""
import os

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
WEB_URL = os.getenv("WEB_URL", "http://localhost:8080")
COMPOSE_PROJECT = os.getenv("COMPOSE_PROJECT", "eai")
MODE = os.getenv("ETERNALAI_MODE", "ask-first")  # watch-only | ask-first | autopilot
APPROVAL_TOKEN = os.getenv("ETERNALAI_APPROVAL_TOKEN", "change-me")
STEP_S = 2

# Caller -> callees. Used by root-cause ranking; it is the app's real call graph.
TOPOLOGY = {"web": ["orders", "inventory"], "orders": ["inventory", "payments"],
            "inventory": [], "payments": []}
SERVICES = list(TOPOLOGY)
CALLERS = {s: [c for c, cs in TOPOLOGY.items() if s in cs] for s in SERVICES}

# Policy limits (deterministic).
COOLDOWN_S = 90            # min seconds between actions on the same service
MAX_ACTIONS_PER_SERVICE = 2  # then circuit breaker opens and we escalate
APPROVED_TEMP_PATH = "/tmp/eai-scratch"
OBSERVATION_S = 20         # how long checkout must stay healthy before "recovered"
