"""External, read-only container health log for the v2 evaluation (separate process; not part of the driver).

    python scripts/health_watch.py --log D:/eAI/eAI-workspace/eAI/results/benchmark-v2/health_log.tsv [--every 60]

Once per interval it appends one line per required container: UTC and local timestamp, name, running state, health status (`none` when the
image has no healthcheck), RestartCount and StartedAt. It only runs `docker ps` and `docker inspect`; it never restarts, stops, creates or deletes anything.
Runbook actions recreate containers on purpose, which shows up as a new StartedAt (and RestartCount unchanged); those are NOT alerts.

ALERT lines (printed to stdout and appended to the log) mean something the runbooks do not do:
  - a required container missing or not `running` in 3 consecutive samples;
  - health `unhealthy` in 3 consecutive samples;
  - RestartCount increased (the runbooks use the Docker API restart/recreate, which does not raise it, so a rise is a restart policy or a crash loop).
The triage step checks each run's time window against this log (`window_flags`).
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

REQUIRED = ["web", "orders", "inventory", "payments", "evaluator", "loadgen", "prometheus", "eternalai"]
FMT = "{{.Name}}|{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}|{{.RestartCount}}|{{.State.StartedAt}}"
CONSECUTIVE = 3


def parse_line(line):
    name, status, health, restarts, started = line.strip().split("|", 4)
    return {"container": name.lstrip("/"), "state": status, "health": health, "restarts": int(restarts), "started": started}


def sample():
    """{service: record or None} from docker inspect; a container that does not exist is None."""
    out = {}
    for svc in REQUIRED:
        r = subprocess.run(["docker", "inspect", f"eai-{svc}-1", "--format", FMT], capture_output=True, text=True, timeout=30)
        out[svc] = parse_line(r.stdout) if r.returncode == 0 and r.stdout.strip() else None
    return out


class Judge:
    """Stateful alert rules over successive samples."""

    def __init__(self):
        self.down, self.unhealthy, self.restarts = {}, {}, {}

    def step(self, snap):
        alerts = []
        for svc, rec in snap.items():
            is_down = rec is None or rec["state"] != "running"
            self.down[svc] = self.down.get(svc, 0) + 1 if is_down else 0
            if self.down[svc] == CONSECUTIVE:
                alerts.append(f"{svc} not running in {CONSECUTIVE} consecutive samples ({'missing' if rec is None else rec['state']})")
            bad = rec is not None and rec["health"] == "unhealthy"
            self.unhealthy[svc] = self.unhealthy.get(svc, 0) + 1 if bad else 0
            if self.unhealthy[svc] == CONSECUTIVE:
                alerts.append(f"{svc} unhealthy in {CONSECUTIVE} consecutive samples")
            if rec is not None:
                prev = self.restarts.get(svc)
                if prev is not None and rec["restarts"] > prev:
                    alerts.append(f"{svc} RestartCount rose {prev} -> {rec['restarts']} (not a runbook action)")
                self.restarts[svc] = rec["restarts"]
        return alerts


def window_flags(log_lines, t_start, t_end):
    """Triage helper: log lines (as written by this script) inside [t_start, t_end] (UTC epoch seconds) that show a required container not running,
    unhealthy, or an ALERT. Lines before the watcher started are simply absent: runs before that are not covered."""
    flags = []
    for ln in log_lines:
        parts = ln.rstrip("\n").split("\t")
        if len(parts) < 3:
            continue
        try:
            t = float(parts[0])
        except ValueError:
            continue
        if not t_start <= t <= t_end:
            continue
        if parts[2] == "ALERT" or (len(parts) >= 6 and (parts[4] != "running" or parts[5] == "unhealthy")):
            flags.append(ln.rstrip("\n"))
    return flags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--every", type=float, default=60.0)
    a = ap.parse_args()
    os.environ["PATH"] += os.pathsep + r"C:\Program Files\Docker\Docker\resources\bin"
    log, judge = Path(a.log), Judge()
    with log.open("a", encoding="utf-8") as f:
        f.write(f"{time.time():.0f}\t{time.strftime('%Y-%m-%dT%H:%M:%S')}\tWATCHER_START\tinterval {a.every:.0f}s\n")
        f.flush()
        while True:
            now, local = time.time(), time.strftime("%Y-%m-%dT%H:%M:%S")
            try:
                snap = sample()
            except (OSError, subprocess.SubprocessError) as e:
                f.write(f"{now:.0f}\t{local}\tWATCHER_ERROR\t{type(e).__name__}\n")
                f.flush()
                time.sleep(a.every)
                continue
            for svc, rec in snap.items():
                if rec is None:
                    f.write(f"{now:.0f}\t{local}\t{svc}\tmissing\tmissing\tnone\t-\t-\n")
                else:
                    f.write(f"{now:.0f}\t{local}\t{svc}\t{rec['container']}\t{rec['state']}\t{rec['health']}\t{rec['restarts']}\t{rec['started']}\n")
            for al in judge.step(snap):
                msg = f"{now:.0f}\t{local}\tALERT\t{al}"
                f.write(msg + "\n")
                print("ALERT " + msg, flush=True)
            f.flush()
            time.sleep(a.every)


if __name__ == "__main__":
    sys.exit(main())
