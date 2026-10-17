"""How long the evaluator waits before injecting, so one run cannot leak into the next."""

NORMAL_SETTLE_S = 45     # let rate windows refill with healthy data
DEPLOY_SETTLE_S = 200    # longer than the 3-minute "recent deploy" signal in the feature pipeline


def settle_seconds(restore_changed_release: bool, previous_run_left_release_change: bool) -> int:
    """A release change (deploy or rollback) shows up in EternalAI's `deploys_3m` signal for 3 minutes.
    Injecting sooner would make the next run look deploy-related (regression: run order leaking into labels)."""
    return DEPLOY_SETTLE_S if (restore_changed_release or previous_run_left_release_change) else NORMAL_SETTLE_S
