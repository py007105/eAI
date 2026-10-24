"""Pre-registered offline evaluation of the z-score detector vs fixed thresholds on SMD (Server Machine Dataset).

    python models/eval_smd.py [--smd data/raw/smd] [--out docs/results/smd_detector_eval.md]

Protocol: docs/SMD_EVAL.md (version 1), committed before any SMD file was downloaded. This script implements it and
nothing else: no parameter here may be changed after looking at results. It reads only the SMD directory (checked
against MANIFEST.json), processes one machine at a time, and writes one Markdown report. It imports (never copies)
eternalai.zscore_detector and the scoring helpers of models/eval_nab.py. Offline evaluation on public data; not live
verified.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "models"))
import eval_nab as nab  # noqa: E402
from eternalai.zscore_detector import (BASELINE_WINDOW, STREAK_NEEDED, WARMUP_POINTS, Z_LIMIT,  # noqa: E402
                                       SignalConfig)

SMD_COMMIT = "7fb0e0acf89ea49908896bcc9f9e80fcfff6baf4"
MACHINES = ([f"machine-1-{i}" for i in range(1, 9)] + [f"machine-2-{i}" for i in range(1, 10)]
            + [f"machine-3-{i}" for i in range(1, 12)])
FOLDERS = ("train", "test", "test_label", "interpretation_label")
N_METRICS = 38
FLOOR_MIN = 0.01
FT_MARGIN_REL, FT_MARGIN_ABS = 0.1, 0.01
FT_STREAK = 3
PRIME_ROWS = BASELINE_WINDOW
DETECTORS = ["Z", "Z-k2", "FT", "FT-3"]
PLAN_EVENTS = 327
T0 = pd.Timestamp("2000-01-01")          # row index -> timestamp, 1 row = 1 minute (only for the NAB helpers)


# ------------------------------------------------------------------ protocol pieces (docs/SMD_EVAL.md)
def label_runs(labels) -> list[tuple[int, int]]:
    """Maximal runs of consecutive 1s, as (start, end) row indices, both inclusive."""
    runs, start = [], None
    for i, v in enumerate(labels):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(labels) - 1))
    return runs


def parse_interpretation(text: str) -> list[tuple[int, int, frozenset]]:
    """Lines 'start-end:m1,m2,...' -> (start, end, {metric numbers, 1-based}). Blank lines are skipped."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        rng, mets = line.split(":", 1)
        a, b = rng.split("-", 1)
        out.append((int(a), int(b), frozenset(int(m) for m in mets.split(",") if m.strip())))
    return out


def train_params(train: np.ndarray) -> list[dict]:
    """Per-metric parameters from the train matrix only (rows x metrics)."""
    params = []
    for j in range(train.shape[1]):
        v = train[:, j]
        v = v[np.isfinite(v)]
        s = nab.robust_scale(v)
        floor = max(s, FLOOR_MIN)
        m = float(v.max())
        params.append({"s": s, "floor": floor, "min_gap": 3 * floor, "M": m,
                       "T": m + max(FT_MARGIN_REL * abs(m), FT_MARGIN_ABS)})
    return params


def as_values(col: np.ndarray) -> list:
    return [float(x) if np.isfinite(x) else None for x in col]


def z_metric_flags(train: np.ndarray, test: np.ndarray, params: list[dict]) -> np.ndarray:
    """test rows x metrics: ZResult.anomalous, after priming each metric with its last PRIME_ROWS train rows."""
    out = np.zeros(test.shape, dtype=bool)
    for j, p in enumerate(params):
        cfg = SignalConfig(floor=p["floor"], min_gap=p["min_gap"], direction="upper")
        tail = as_values(train[-PRIME_ROWS:, j])
        flags = nab.zscore_flags(tail + as_values(test[:, j]), cfg)
        out[:, j] = flags[len(tail):]
    return out


def ft_metric_flags(test: np.ndarray, params: list[dict], streak: int) -> np.ndarray:
    out = np.zeros(test.shape, dtype=bool)
    for j, p in enumerate(params):
        out[:, j] = nab.ft_flags(as_values(test[:, j]), p["T"], streak)
    return out


def machine_alarm(metric_flags: np.ndarray, k: int) -> list[bool]:
    """Alarm at a row if at least k metrics flag."""
    return [bool(x) for x in (metric_flags.sum(axis=1) >= k)]


def rows_to_ts(n: int) -> list:
    return list(pd.date_range(T0, periods=n, freq="min"))


def score_rows(flags: list[bool], events: list[tuple[int, int]]) -> dict:
    """NAB event scoring (models/eval_nab.score) on row indices; every test row is scored; delays are in rows."""
    ts = rows_to_ts(len(flags))
    windows = [(ts[a], ts[b]) for a, b in events]
    r = nab.score(ts, flags, 0, windows)
    r["events"] = r.pop("evaluable")
    return r


def explanation(flags: list[bool], metric_flags: np.ndarray, events, interp) -> dict:
    """Pre-registered explanation score (docs/SMD_EVAL.md §3.1)."""
    starts = nab.alarm_event_starts(flags, 0)
    hits = with_list = without_list = 0
    for a, b in events:
        first = next((s for s in starts if a <= s <= b), None)
        if first is None:
            continue
        mets = set().union(*[m for s, e, m in interp if s <= b and e >= a]) if interp else set()
        if not mets:
            without_list += 1
            continue
        with_list += 1
        alarming = {j + 1 for j in np.flatnonzero(metric_flags[first])}
        hits += bool(alarming & mets)
    return {"hits": hits, "with_list": with_list, "without_list": without_list}


def evaluate_machine(train: np.ndarray, test: np.ndarray, labels, interp) -> dict:
    if train.shape[1] != N_METRICS or test.shape[1] != N_METRICS:
        raise SystemExit(f"expected {N_METRICS} columns, got train {train.shape[1]} / test {test.shape[1]}")
    if len(labels) != len(test):
        raise SystemExit(f"test_label has {len(labels)} rows, test has {len(test)}")
    events = label_runs(labels)
    params = train_params(train)
    zf = z_metric_flags(train, test, params)
    mf = {"Z": zf, "Z-k2": zf, "FT": ft_metric_flags(test, params, 1), "FT-3": ft_metric_flags(test, params, FT_STREAK)}
    kk = {"Z": 1, "Z-k2": 2, "FT": 1, "FT-3": 1}
    scores, expl = {}, {}
    for det in DETECTORS:
        flags = machine_alarm(mf[det], kk[det])
        scores[det] = score_rows(flags, events)
        expl[det] = explanation(flags, mf[det], events, interp)
    lone = sum(1 for s, e, _ in interp if not any(s <= b and e >= a for a, b in events))
    return {"train_rows": len(train), "test_rows": len(test),
            "missing": int((~np.isfinite(train)).sum() + (~np.isfinite(test)).sum()),
            "floor_raised": sum(p["s"] < FLOOR_MIN for p in params), "events": len(events),
            "interp_lines": len(interp), "interp_lone": lone, "scores": scores, "expl": expl}


# ------------------------------------------------------------------ data
def check_inputs(smd: Path) -> dict:
    mpath = smd / "MANIFEST.json"
    if not mpath.exists():
        raise SystemExit(f"missing {mpath}; run data/download_smd.py --commit {SMD_COMMIT}")
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    if manifest.get("commit") != SMD_COMMIT:
        raise SystemExit(f"MANIFEST commit {manifest.get('commit')} != pre-registered {SMD_COMMIT}")
    listed = {f["path"]: f["sha256"] for f in manifest["files"]}
    hashes = {}
    for rel in [f"{d}/{m}.txt" for m in MACHINES for d in FOLDERS]:
        p = smd / rel
        if not p.exists():
            raise SystemExit(f"missing input {p}")
        h = nab.sha256(p)
        if listed.get(rel) != h:
            raise SystemExit(f"SHA256 of {rel} differs from MANIFEST.json")
        hashes[rel] = h
    return hashes


def read_matrix(path: Path) -> np.ndarray:
    return pd.read_csv(path, header=None, dtype=float).to_numpy()


def load_machine(smd: Path, m: str):
    train = read_matrix(smd / "train" / f"{m}.txt")
    test = read_matrix(smd / "test" / f"{m}.txt")
    labels = [int(float(x)) for x in (smd / "test_label" / f"{m}.txt").read_text(encoding="utf-8").split()]
    interp = parse_interpretation((smd / "interpretation_label" / f"{m}.txt").read_text(encoding="utf-8"))
    return train, test, labels, interp


# ------------------------------------------------------------------ report
def summarise(rows: list[dict]) -> dict:
    keys = ["events", "detected", "alarm_events", "true_events", "false_events", "outside_days"]
    tot = {k: sum(r[k] for r in rows) for k in keys}
    tot["delays_min"] = [d for r in rows for d in r["delays_min"]]
    return tot


def derived(t: dict) -> dict:
    d = nab.derived({**t, "evaluable": t["events"]})
    return d


def render(results: dict, hashes: dict) -> str:
    fmt, delay_text = nab.fmt, nab.delay_text
    L = ["# SMD detector evaluation: results (pre-registration version 1)", "",
         "**Offline evaluation on public data; not live verified.** Generated by `models/eval_smd.py`; every number "
         "below comes from that script. Protocol: `docs/SMD_EVAL.md` (version 1), committed before any SMD file was "
         "downloaded.", "",
         f"- SMD source: OmniAnomaly `ServerMachineDataset`, commit `{SMD_COMMIT}` (MIT licence)",
         f"- EternalAI commit of the script: `{nab.git_head()}`",
         f"- Z-score constants: z limit {Z_LIMIT}, streak {STREAK_NEEDED}, warm-up {WARMUP_POINTS}, baseline window "
         f"{BASELINE_WINDOW}; per metric floor = max(robust scale of train, {FLOOR_MIN}), min_gap = 3 × floor, "
         f"direction upper; each metric primed with its last {PRIME_ROWS} train rows",
         f"- `Z`: machine alarms if ≥ 1 of {N_METRICS} metrics is anomalous; `Z-k2`: ≥ 2 metrics",
         f"- Fixed threshold per metric: T = train max + max({FT_MARGIN_REL} × |train max|, {FT_MARGIN_ABS}); `FT` "
         f"alarms on 1 row, `FT-3` needs {FT_STREAK} rows in a row; machine alarms if ≥ 1 metric",
         "- Events: anomaly event = maximal run of 1s in `test_label`; consecutive alarm rows form one alarm event; an "
         "anomaly event is detected if an alarm event starts inside it; an alarm event starting outside every anomaly "
         "event is a false alarm; **no point adjustment**",
         "- Delay: first alarm-event start inside the event minus the event start, in rows (1 row = 1 minute)", ""]

    tot_events = sum(results[m]["events"] for m in MACHINES)
    L += ["## Totals (28 machines pooled)", "",
          "| detector | detected / events | recall | alarm events | true alarm events | false alarm events "
          "| precision | false alarms per day | delay, min: median (range) |", "|---|---|---|---|---|---|---|---|---|"]
    for det in DETECTORS:
        t = summarise([results[m]["scores"][det] for m in MACHINES])
        dv = derived(t)
        L.append(f"| {det} | {t['detected']} / {t['events']} | {fmt(dv['recall'])} | {t['alarm_events']} | "
                 f"{t['true_events']} | {t['false_events']} | {fmt(dv['precision'])} | {fmt(dv['per_day'])} | "
                 f"{delay_text(dv)} |")
    L.append("")

    L += ["## Event count vs the plan", "",
          f"- Anomaly events (maximal runs of 1s in `test_label`, 28 machines): **{tot_events}**",
          f"- Plan (§10.2 row D, and the owner's workbook): {PLAN_EVENTS} SMD events; difference "
          f"{tot_events - PLAN_EVENTS:+d}" + (" (the counts agree)" if tot_events == PLAN_EVENTS else ""), ""]

    lines = sum(results[m]["interp_lines"] for m in MACHINES)
    lone = sum(results[m]["interp_lone"] for m in MACHINES)
    L += ["## Explanation score (pre-registered, secondary)", "",
          "Share of detected events where at least one metric alarming at the first alarm inside the event is in that "
          "event's `interpretation_label` metric list.", "",
          "| detector | hits / detected events with a list | explanation score | detected events without a list |",
          "|---|---|---|---|"]
    for det in DETECTORS:
        e = {k: sum(results[m]["expl"][det][k] for m in MACHINES) for k in ("hits", "with_list", "without_list")}
        L.append(f"| {det} | {e['hits']} / {e['with_list']} | {fmt(nab.ratio(e['hits'], e['with_list']))} | "
                 f"{e['without_list']} |")
    L += ["", f"Index-convention check: {lines} interpretation lines; {lone} of them overlap no anomaly event.", ""]

    L += ["## Per machine", ""]
    for det in DETECTORS:
        L += [f"### {det}", "",
              "| machine | detected / events | true events | false events | outside days | false alarms per day "
              "| precision | delay, min: median (range) |", "|---|---|---|---|---|---|---|---|"]
        for m in MACHINES:
            r = results[m]["scores"][det]
            dv = derived(r)
            L.append(f"| `{m}` | {r['detected']} / {r['events']} | {r['true_events']} | {r['false_events']} | "
                     f"{r['outside_days']:.2f} | {fmt(dv['per_day'])} | {fmt(dv['precision'])} | {delay_text(dv)} |")
        L.append("")

    L += ["## Per-machine data facts", "",
          "| machine | train rows | test rows | missing values | anomaly events | metrics with floor raised to "
          f"{FLOOR_MIN} | interpretation lines |", "|---|---|---|---|---|---|---|"]
    for m in MACHINES:
        r = results[m]
        L.append(f"| `{m}` | {r['train_rows']} | {r['test_rows']} | {r['missing']} | {r['events']} | "
                 f"{r['floor_raised']} | {r['interp_lines']} |")
    L.append("")

    L += ["## Input files (SHA256)", "", "| file | SHA256 |", "|---|---|"]
    L += [f"| `{rel}` | `{h}` |" for rel, h in hashes.items()]
    L += ["", "## Limitations", "",
          "- Offline evaluation on public data; not live verified. EternalAI's live loop was not run, and its live "
          "detector (isolation forest + per-service persistence) is not what is scored here.",
          "- SMD is anonymised and normalised: no metric can be named, so the plan's \"CPU > 90%\" cannot be applied; "
          "`FT` is a train-derived stand-in.",
          "- With 38 metrics and \"at least 1 metric\", false alarms add up across metrics; `Z-k2` is reported for that "
          "reason.",
          "- The `upper` rules cannot catch drops.",
          "- The z-score constants were set for a 2-second loop; SMD has one row per minute.", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smd", default=str(ROOT / "data" / "raw" / "smd"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "results" / "smd_detector_eval.md"))
    a = ap.parse_args(argv)
    smd = Path(a.smd)
    hashes = check_inputs(smd)
    results = {}
    for m in MACHINES:                       # one machine at a time
        results[m] = evaluate_machine(*load_machine(smd, m))
        print(f"{m}: {results[m]['events']} events", flush=True)
    Path(a.out).write_text(render(results, hashes), encoding="utf-8", newline="\n")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
