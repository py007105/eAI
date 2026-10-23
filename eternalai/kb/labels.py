"""The two label vocabularies and how they meet.

The live classifier speaks six fault labels; the plan and the knowledge base speak the plan's taxonomy (plan §5.1).
Only these pairs are mapped; every other plan type has no live equivalent (the live classifier cannot output it).
"""
LIVE_TO_PLAN = {
    "down": "crash",
    "memory_leak": "memory_leak",
    "disk_fill": "disk_filling",
    "bad_deploy": "bad_deploy",
    "error_spike": "app_error",       # an error burst without a deploy (plan §5.1 "app_error")
    "latency_spike": "slow_service",
}
PLAN_TO_LIVE = {v: k for k, v in LIVE_TO_PLAN.items()}

# knowledge-base fix id -> runbook this repository can execute (eternalai/executor.py). Everything else is "suggest only".
# restart_with_helper needs a second replica (a Kubernetes rolling restart); the Docker executor cannot do it.
FIX_TO_RUNBOOK = {
    "restart_in_place": "restart_service",
    "rollback_deploy": "rollback_release",
    "disk_cleanup": "clear_temp_path",
}
