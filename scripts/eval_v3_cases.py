"""The registered case list of evaluation v3 (docs/EVALUATION_V3_PLAN.md) and checks for resuming an execution.

The rule is the runner's (scripts/run_benchmark.py with --reps 5 --seed0 600): seed = 600 + 10*repetition + index of the
scenario in models/collect_runs.py SCENARIOS; within a repetition the order is random.Random(100 + rep).shuffle.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

SCENARIOS = ["crash", "latency", "error_spike", "memory_leak", "disk_fill", "bad_deploy", "cpu_burn", "traffic_surge",
             "good_deploy"]   # models/collect_runs.py; the order fixes the seeds
SEED0, REPS = 600, 5


def _order(rep, scenarios):
    order = list(enumerate(scenarios))
    random.Random(100 + rep).shuffle(order)
    return order


def planned_cases() -> list[tuple[str, str, int]]:
    """All 50 cases in the order the runner executes them: block V3-A (autopilot, 45), then V3-B (no_action, 5)."""
    out = []
    for arm, scens in (("eternalai_autopilot", SCENARIOS), ("no_action", ["memory_leak"])):
        for rep in range(REPS):
            for _i, scen in _order(rep, scens):
                out.append((arm, scen, SEED0 + rep * 10 + SCENARIOS.index(scen)))
    return out


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def key(r: dict) -> tuple[str, str, int]:
    return (r["arm"], r["scenario"], r["seed"])


def missing_cases(done_rows: list[dict]) -> list[tuple[str, str, int]]:
    done = {key(r) for r in done_rows}
    return [c for c in planned_cases() if c not in done]


def check_resume(original: list[dict], combined: list[dict]) -> dict:
    """A resumed raw file must start with the original rows unchanged, and every added row must be a case that was
    missing, at most once. Returns the verdict and the lists, so the report can show both parts separately."""
    n = len(original)
    planned = set(planned_cases())
    prefix_same = combined[:n] == original
    added = combined[n:]
    added_keys = [key(r) for r in added]
    missing_before = set(missing_cases(original))
    dup = sorted({k for k in added_keys if added_keys.count(k) > 1})
    not_missing = sorted({k for k in added_keys if k not in missing_before})
    unplanned = sorted({k for k in added_keys if k not in planned})
    still_missing = [c for c in missing_cases(combined)]
    return {"original_rows_unchanged": prefix_same, "original": n, "added": len(added), "duplicates": dup,
            "added_but_not_missing": not_missing, "unplanned": unplanned, "still_missing": still_missing,
            "valid": prefix_same and not dup and not not_missing and not unplanned}
