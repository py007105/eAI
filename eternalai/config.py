"""Static configuration: service topology, endpoints, policy limits. Env overrides only."""
import os

try:  # keys and settings come from the environment or a git-ignored .env; never from code
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv is optional; the environment alone also works
    pass

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
SCRATCH_LIMIT_BYTES = int(os.getenv("SCRATCH_LIMIT_MB", "300")) * 1024 * 1024  # mirrors the app's disk-full threshold
PREDICT_HORIZON_S = 90     # act on a forecast when earliest exhaustion is closer than this
OBSERVATION_S = 20        # how long checkout must stay healthy before "recovered"
DEPLOY_GRACE_S = 15.0     # ignore anomalies this long after a release change (a normal rolling release restarts the service)
# v2: a proposal that nobody approves must not stop detection forever. After this long a pending approval (or a watch-only
# observation) is escalated with its evidence preserved, and the incident is closed.
APPROVAL_TTL_S = float(os.getenv("ETERNALAI_APPROVAL_TTL_S", "120"))
# Safety controls. Kill switch: when on, nothing is executed (autopilot or approved); it can also be switched at run time
# with POST /killswitch. Protected services: proposals for them are only recorded (observe_only), in every mode.
def env_flag(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def env_list(value: str | None) -> set:
    return {s.strip() for s in (value or "").split(",") if s.strip()}


KILL_SWITCH = env_flag(os.getenv("ETERNALAI_KILL_SWITCH"))
PROTECTED_SERVICES = env_list(os.getenv("ETERNALAI_PROTECTED_SERVICES"))
