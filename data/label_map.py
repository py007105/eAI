"""Explicit mapping from workbook fault labels to EternalAI runtime names.

`supported` means the live system (app + evaluator + executor) can produce and act
on that fault. Unsupported labels are still useful as training negatives for "other
fault" and for abstention tests; they are never silently renamed.
"""
LABEL_MAP = {
    # workbook label : (runtime name,        supported at runtime)
    "normal":        ("healthy",             True),
    "app_error":     ("error_spike",         True),
    "slow_service":  ("latency_spike",       True),
    "crash":         ("down",                True),
    "memory_leak":   ("memory_leak",         True),
    "disk_filling":  ("disk_fill",           True),
    "bad_deploy":    ("bad_deploy",          True),
    "cpu_runaway":   ("cpu_saturation",      False),
    "overload":      ("traffic_overload",    False),
    "network_delay": ("network_delay",       False),
    "db_slowdown":   ("dependency_slowdown", False),
    "logic_bug":     ("unseen_fault",        False),  # never trained on; abstention test
}

# Columns that carry the answer or are defined using the known injection window.
# They must never be classifier inputs.
LEAKY_COLUMNS = [
    "role", "is_root", "fault_type", "fault_type_at_service", "category", "source_fault",
    "mapping_quality", "label_quality", "in_scope",
    "n_fault_points",        # count of points inside the injected window
    "anomaly_score",         # produced by another model fitted with labels in view
    "is_deepest_anomalous",  # derived from anomaly flags across the case
]
ID_COLUMNS = ["case_id", "source", "system", "run_group", "service", "sampling_s"]
