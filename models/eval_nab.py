"""Pre-registered offline evaluation of the z-score detector vs fixed thresholds on NAB realAWSCloudwatch.

    python models/eval_nab.py [--nab data/raw/nab] [--out docs/results/nab_detector_eval.md]

Protocol: docs/NAB_EVAL.md (version 1), committed before the data was downloaded. This script implements it and nothing
else: no parameter here may be changed after looking at results. It reads only the NAB directory (checked against
MANIFEST.json) and writes one Markdown report. Offline evaluation on public data; not live verified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from eternalai.zscore_detector import (BASELINE_WINDOW, STREAK_NEEDED, WARMUP_POINTS, Z_LIMIT,  # noqa: E402
                                       SignalConfig, ZScoreDetector)

NAB_COMMIT = "ea702d75cc2258d9d7dd35ca8e5e2539d71f3140"
SERIES = [
    "ec2_cpu_utilization_24ae8d", "ec2_cpu_utilization_53ea38", "ec2_cpu_utilization_5f5533",
    "ec2_cpu_utilization_77c1ca", "ec2_cpu_utilization_825cc2", "ec2_cpu_utilization_ac20cd",
    "ec2_cpu_utilization_c6585a", "ec2_cpu_utilization_fe7f93", "ec2_disk_write_bytes_1ef3de",
    "ec2_disk_write_bytes_c0d644", "ec2_network_in_257a54", "ec2_network_in_5abac7", "elb_request_count_8c0756",
    "grok_asg_anomaly", "iio_us-east-1_i-a2eb1cd9_NetworkIn", "rds_cpu_utilization_cc0c53",
    "rds_cpu_utilization_e47b3b",
]
LABELS = "labels/combined_windows.json"
CPU_THRESHOLD = 90.0
FT_STREAK = 3
DETECTORS = ["Z-up", "Z-two", "FT", "FT-3"]
PLAN_SERIES, PLAN_EVENTS = 20, 327


# ------------------------------------------------------------------ protocol pieces (docs/NAB_EVAL.md)
def series_path(name: str) -> str:
    return f"data/realAWSCloudwatch/{name}.csv"


def is_cpu(name: str) -> bool:
    return "cpu_utilization" in name


def probation_len(n: int) -> int:
    """NAB getProbationPeriod with 15%: min(floor(0.15 n), 750)."""
    return int(min(math.floor(0.15 * n), 0.15 * 5000))


def robust_scale(v) -> float:
    v = np.asarray([x for x in v if x is not None and np.isfinite(x)], dtype=float)
    med = float(np.median(v))
    s = 1.4826 * float(np.median(np.abs(v - med)))
    if s == 0:
        s = float(np.std(v))
    if s == 0:
        s = 1e-6 * max(1.0, abs(med))
    return s


def zscore_config(v, direction: str) -> SignalConfig:
    s = robust_scale(v)
    return SignalConfig(floor=s, min_gap=3 * s, direction=direction)


def ft_threshold(v, cpu: bool) -> float:
    if cpu:
        return CPU_THRESHOLD
    v = np.asarray([x for x in v if x is not None and np.isfinite(x)], dtype=float)
    q50, q99 = np.percentile(v, 50), np.percentile(v, 99)
    return float(q99 + (q99 - q50))


def zscore_flags(values, cfg: SignalConfig) -> list[bool]:
    d = ZScoreDetector(default=cfg)
    return [d.update("s", v).anomalous for v in values]


def ft_flags(values, threshold: float, streak: int = 1) -> list[bool]:
    out, run = [], 0
    for v in values:
        hot = v is not None and np.isfinite(v) and v > threshold
        run = run + 1 if hot else 0
        out.append(run >= streak)
    return out


def alarm_event_starts(flags, first_scored: int) -> list[int]:
    """Row indices where an alarm event starts: maximal runs of alarm points on consecutive scored rows."""
    starts, prev = [], False
    for i in range(first_scored, len(flags)):
        if flags[i] and not prev:
            starts.append(i)
        prev = bool(flags[i])
    return starts


def score(ts, flags, first_scored: int, windows) -> dict:
    """Event-level scoring of one detector on one series; no point-adjustment. ts: list of pd.Timestamp."""
    t0 = ts[first_scored]
    evaluable = [(s, e) for s, e in windows if s >= t0]
    excluded = [(s, e) for s, e in windows if s < t0]
    inside = lambda t, ws: next(((s, e) for s, e in ws if s <= t <= e), None)
    starts = [ts[i] for i in alarm_event_starts(flags, first_scored)]
    true_ev = false_ev = excl_ev = 0
    first_in = {}
    for t in starts:
        w = inside(t, evaluable)
        if w is not None:
            true_ev += 1
            first_in[w] = min(first_in.get(w, t), t)
        elif inside(t, excluded) is not None:
            excl_ev += 1
        else:
            false_ev += 1
    delays = [(first_in[w] - w[0]).total_seconds() / 60 for w in evaluable if w in first_in]
    step = pd.Series(ts).diff().median()
    outside_rows = sum(1 for t in ts[first_scored:] if inside(t, windows) is None)
    outside_days = outside_rows * step.total_seconds() / 86400 if len(ts) > 1 else 0.0
    return {"evaluable": len(evaluable), "excluded": len(excluded), "detected": len(delays),
            "alarm_events": len(starts), "true_events": true_ev, "false_events": false_ev, "excluded_events": excl_ev,
            "outside_days": outside_days, "delays_min": delays}


def ratio(a, b):
    return a / b if b else None


def summarise(rows: list[dict]) -> dict:
    keys = ["evaluable", "excluded", "detected", "alarm_events", "true_events", "false_events", "excluded_events",
            "outside_days"]
    tot = {k: sum(r[k] for r in rows) for k in keys}
    tot["delays_min"] = [d for r in rows for d in r["delays_min"]]
    return tot


def derived(r: dict) -> dict:
    d = r["delays_min"]
    return {"recall": ratio(r["detected"], r["evaluable"]),
            "precision": ratio(r["true_events"], r["true_events"] + r["false_events"]),
            "per_day": ratio(r["false_events"], r["outside_days"]),
            "delay_med": float(np.median(d)) if d else None,
            "delay_min": min(d) if d else None, "delay_max": max(d) if d else None}


# ------------------------------------------------------------------ data
def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_inputs(nab: Path) -> dict:
    mpath = nab / "MANIFEST.json"
    if not mpath.exists():
        raise SystemExit(f"missing {mpath}; run data/download_nab.py --commit {NAB_COMMIT}")
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    if manifest.get("commit") != NAB_COMMIT:
        raise SystemExit(f"MANIFEST commit {manifest.get('commit')} != pre-registered {NAB_COMMIT}")
    listed = {f["path"]: f["sha256"] for f in manifest["files"]}
    hashes = {}
    for rel in [series_path(s) for s in SERIES] + [LABELS]:
        p = nab / rel
        if not p.exists():
            raise SystemExit(f"missing input {p}")
        h = sha256(p)
        if listed.get(rel) != h:
            raise SystemExit(f"SHA256 of {rel} differs from MANIFEST.json")
        hashes[rel] = h
    return hashes


def load_series(nab: Path, name: str):
    df = pd.read_csv(nab / series_path(name))
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp", kind="stable").reset_index(drop=True)
    vals = pd.to_numeric(df["value"], errors="coerce").astype(float)
    values = [float(v) if np.isfinite(v) else None for v in vals]
    return list(df["timestamp"]), values


def load_windows(nab: Path) -> dict:
    raw = json.loads((nab / LABELS).read_text(encoding="utf-8"))
    return {s: [(pd.Timestamp(a), pd.Timestamp(b)) for a, b in raw[f"realAWSCloudwatch/{s}.csv"]] for s in SERIES}


def evaluate_series(ts, values, windows, cpu: bool) -> dict:
    n = len(values)
    p = probation_len(n)
    prob = [v for v in values[:p] if v is not None]
    cfg_up, cfg_two = zscore_config(prob, "upper"), zscore_config(prob, "two_sided")
    thr = ft_threshold(prob, cpu)
    flags = {"Z-up": zscore_flags(values, cfg_up), "Z-two": zscore_flags(values, cfg_two),
             "FT": ft_flags(values, thr, 1), "FT-3": ft_flags(values, thr, FT_STREAK)}
    step = pd.Series(ts).diff().median()
    return {"n": n, "P": p, "step_min": step.total_seconds() / 60, "floor": cfg_up.floor, "min_gap": cfg_up.min_gap,
            "T": thr, "missing": sum(v is None for v in values), "windows": len(windows),
            "scores": {k: score(ts, f, p, windows) for k, f in flags.items()}}


# ------------------------------------------------------------------ report
def fmt(x, nd=3):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def fnum(x):
    if x is None:
        return "n/a"
    return f"{x:.4g}"


def delay_text(dv):
    if dv["delay_med"] is None:
        return "n/a"
    return f"{dv['delay_med']:.0f} ({dv['delay_min']:.0f}–{dv['delay_max']:.0f})"


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return "unknown"


def render(results: dict, hashes: dict) -> str:
    L = []
    L += ["# NAB detector evaluation: results (pre-registration version 1)", "",
          "**Offline evaluation on public data; not live verified.** Generated by `models/eval_nab.py`; every number "
          "below comes from that script. Protocol: `docs/NAB_EVAL.md` (version 1), committed before the data was "
          "downloaded.", "",
          f"- NAB commit: `{NAB_COMMIT}`",
          f"- EternalAI commit of the script: `{git_head()}`",
          f"- Z-score constants: z limit {Z_LIMIT}, streak {STREAK_NEEDED}, warm-up {WARMUP_POINTS}, baseline window "
          f"{BASELINE_WINDOW}; per-series floor = robust scale of the probationary values, min_gap = 3 × floor",
          f"- Fixed threshold: CPU series `value > {CPU_THRESHOLD:g}`; other series `q99 + (q99 − q50)` of the "
          f"probationary values; `FT` alarms on 1 row, `FT-3` needs {FT_STREAK} rows in a row",
          "- Events: consecutive alarm rows merge into one alarm event; a window is detected if an alarm event starts "
          "inside it; an event starting outside every window is a false alarm; **no point-adjustment**",
          "- Delay: first alarm-event start inside the window minus the window start, in minutes; median (min–max)", ""]

    groups = {"all 17 series": SERIES, "CPU series": [s for s in SERIES if is_cpu(s)],
              "other series": [s for s in SERIES if not is_cpu(s)]}
    L += ["## Totals", "",
          "| group | detector | detected / evaluable | recall | true alarm events | false alarm events | precision "
          "| false alarms per day | delay, min: median (range) |", "|---|---|---|---|---|---|---|---|---|"]
    for g, names in groups.items():
        for det in DETECTORS:
            t = summarise([results[s]["scores"][det] for s in names])
            dv = derived(t)
            L.append(f"| {g} ({len(names)}) | {det} | {t['detected']} / {t['evaluable']} | {fmt(dv['recall'])} | "
                     f"{t['true_events']} | {t['false_events']} | {fmt(dv['precision'])} | {fmt(dv['per_day'])} | "
                     f"{delay_text(dv)} |")
    L.append("")

    ev = sum(results[s]["scores"]["FT"]["evaluable"] for s in SERIES)
    ex = sum(results[s]["scores"]["FT"]["excluded"] for s in SERIES)
    allw = sum(results[s]["windows"] for s in SERIES)
    L += ["## Plan comparison", "",
          f"The plan (§10.2 row D) states \"{PLAN_SERIES} series, {PLAN_EVENTS} events\" for the detector tests "
          "(NAB AWS CloudWatch and SMD together). This evaluation covers NAB `realAWSCloudwatch` only:", "",
          f"- series evaluated: **{len(SERIES)}** (plan: {PLAN_SERIES}; difference {len(SERIES) - PLAN_SERIES:+d})",
          f"- labelled windows in these series: **{allw}** (evaluable {ev}, excluded because they start in the "
          f"probationary period {ex}); plan: {PLAN_EVENTS} events; difference {allw - PLAN_EVENTS:+d}",
          "- The plan's figure is not reproduced here; SMD is not evaluated (roadmap).", ""]

    L += ["## Per series", ""]
    for det in DETECTORS:
        L += [f"### {det}", "",
              "| series | detected / evaluable | true events | false events | events in excluded windows "
              "| outside days | false alarms per day | precision | delay, min: median (range) |",
              "|---|---|---|---|---|---|---|---|---|"]
        for s in SERIES:
            r = results[s]["scores"][det]
            dv = derived(r)
            L.append(f"| `{s}` | {r['detected']} / {r['evaluable']} | {r['true_events']} | {r['false_events']} | "
                     f"{r['excluded_events']} | {r['outside_days']:.2f} | {fmt(dv['per_day'])} | "
                     f"{fmt(dv['precision'])} | {delay_text(dv)} |")
        L.append("")

    L += ["## Per-series parameters (from the probationary period only)", "",
          "| series | class | rows n | probationary P | step, min | missing values | windows (evaluable / excluded) "
          "| z floor | z min_gap | fixed T |", "|---|---|---|---|---|---|---|---|---|---|"]
    for s in SERIES:
        r = results[s]
        sc = r["scores"]["FT"]
        L.append(f"| `{s}` | {'CPU' if is_cpu(s) else 'other'} | {r['n']} | {r['P']} | {r['step_min']:g} | "
                 f"{r['missing']} | {sc['evaluable']} / {sc['excluded']} | {fnum(r['floor'])} | {fnum(r['min_gap'])} "
                 f"| {fnum(r['T'])} |")
    L.append("")

    L += ["## Input files (SHA256)", "", "| file | SHA256 |", "|---|---|"]
    L += [f"| `{rel}` | `{h}` |" for rel, h in hashes.items()]
    L += ["", "## Limitations", "",
          "- Offline evaluation on public data; not live verified. EternalAI's live loop was not run.",
          "- NAB AWS series are univariate; the live detector sees several signals per service.",
          "- NAB windows are wide and begin before the labelled anomaly point, so delay from the window start is not "
          "delay from onset, and an early alarm inside a window counts as a detection.",
          "- `Z-up`, `FT` and `FT-3` alarm only upwards and cannot catch drops (`Z-two` is reported for that reason).",
          "- The z-score constants were set for a 2-second loop; NAB AWS data is sampled about every 5 minutes.",
          "- SMD (plan §10.2 row D) is not evaluated.", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nab", default=str(ROOT / "data" / "raw" / "nab"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "results" / "nab_detector_eval.md"))
    a = ap.parse_args(argv)
    nab = Path(a.nab)
    hashes = check_inputs(nab)
    windows = load_windows(nab)
    results = {}
    for s in SERIES:
        ts, values = load_series(nab, s)
        results[s] = evaluate_series(ts, values, windows[s], is_cpu(s))
    Path(a.out).write_text(render(results, hashes), encoding="utf-8", newline="\n")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
