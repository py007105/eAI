"""One detached overnight runner for the main session's Docker window (records everything; never promotes or pushes).

    python scripts/run_overnight.py --log-dir D:\\eAI\\overnight-20261024 --candidate D:\\eAI\\eAI-eval-71eb2f5 \\
        --combined D:\\eAI\\eAI-combined-<hash> --reference 20261024T001813-4cedc8bf

1. Single runner: a PID file in --log-dir created with O_EXCL; refuses if another live runner holds it.
2. Waits until --start (IST). Then waits until the Docker lock is FREE and free RAM >= --min-free-gb (docs/COORDINATION.md:
   a Compose window needs about 3 GB), never past a step's latest start time. Takes the lock ATOMICALLY once
   (scripts/stack_lock.py) and holds it across the steps; children run in parent mode (they never release it).
3. Steps, each started only before its latest start time and only with enough free RAM (otherwise recorded as not started):
   gate     - candidate checkout: scripts/run_gate_sequence.py --reference <ID>   (G2-G7 in one new execution)
   resume   - candidate checkout: scripts/resume_eval_v3.py --original <ID>       (exactly the missing evaluation cases)
   combined - combined checkout: scripts/live_check_combined.py                    (builds the combined images: last)
   The children keep their own memory guards; nothing here lowers them.
4. Releases only its own lock and stops the stack in a `finally`. Status in <log-dir>/status.json, log in runner.log.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import memguard  # noqa: E402
import stack_lock  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
DOCKER_BIN = r"C:\Program Files\Docker\Docker\resources\bin"


def now():
    return datetime.now(IST)


def at(hhmm: str, after: datetime) -> datetime:
    """The first moment at or after `after` (minus 12 h) with this IST clock time: 21:00 today, 05:00 tomorrow."""
    h, m = map(int, hhmm.split(":"))
    t = after.replace(hour=h, minute=m, second=0, microsecond=0)
    return t if t >= after - timedelta(hours=12) else t + timedelta(days=1)


def pid_alive(pid: int) -> bool:
    r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
    return str(pid) in r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-dir", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--combined", required=True)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--start", default="21:00")
    ap.add_argument("--end", default="05:00")
    ap.add_argument("--min-free-gb", type=float, default=3.0)
    ap.add_argument("--gate-latest", default="23:30")
    ap.add_argument("--resume-latest", default="01:30")
    ap.add_argument("--combined-latest", default="04:15")
    ap.add_argument("--steps", default="gate,resume,combined", help="comma-separated subset, run in the fixed order")
    a = ap.parse_args()
    wanted = [s for s in a.steps.split(",") if s]
    unknown = set(wanted) - {"gate", "resume", "combined"}
    if unknown:
        sys.exit(f"unknown steps: {sorted(unknown)}")
    logdir = Path(a.log_dir)
    logdir.mkdir(parents=True, exist_ok=True)
    pidf = logdir / "runner.pid"
    if pidf.exists():
        old = int(pidf.read_text().strip() or 0)
        if old and pid_alive(old):
            sys.exit(f"another runner is alive (PID {old})")
        pidf.unlink()
    fd = os.open(pidf, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    launched = now()
    start, end = at(a.start, launched), None
    end = at(a.end, start)
    latest = {"gate": at(a.gate_latest, start), "resume": at(a.resume_latest, start), "combined": at(a.combined_latest, start)}
    status = {"pid": os.getpid(), "launched": launched.isoformat(timespec="seconds"), "window": [start.isoformat(), end.isoformat()],
              "latest_start": {k: v.isoformat() for k, v in latest.items()}, "min_free_gb": a.min_free_gb, "steps": [],
              "state": "waiting for the window"}
    log_f = open(logdir / "runner.log", "a", encoding="utf-8")

    def log(msg):
        log_f.write(f"{now():%Y-%m-%d %H:%M:%S} IST {msg}\n")
        log_f.flush()

    def save():
        (logdir / "status.json").write_text(json.dumps(status, indent=1), encoding="utf-8")

    def wait_until(cond, deadline, what):
        last = 0.0
        while not cond():
            if now() >= deadline:
                return False
            if time.time() - last >= 600:
                log(f"waiting: {what} (free RAM {memguard.free_ram_gb():.2f} GB; lock: {stack_lock.state()[:60]})")
                last = time.time()
            time.sleep(60)
        return True

    save()
    log(f"runner start, PID {os.getpid()}; window {start:%H:%M}-{end:%H:%M} IST")
    token = None
    try:
        while now() < start:
            time.sleep(min(60, (start - now()).total_seconds()))
        status["state"] = "waiting for the lock and memory"
        save()
        ok = wait_until(lambda: stack_lock.is_free() and memguard.free_ram_gb() >= a.min_free_gb, latest[wanted[0]],
                        "lock FREE and enough free RAM for the first step")
        if not ok:
            status["state"] = "not started: lock or memory not available before the gate's latest start"
            log(status["state"])
            return
        token = stack_lock.take("main", "overnight runner (gate, evaluation resume, combined)", "see status.json")
        status["lock_taken"] = now().isoformat(timespec="seconds")
        status["state"] = "running"
        save()
        log("lock taken atomically")
        env = {**os.environ, "PATH": os.environ.get("PATH", "") + os.pathsep + DOCKER_BIN,
               stack_lock.PARENT_ENV: "main", stack_lock.TOKEN_ENV: token, "PYTHONIOENCODING": "utf-8"}
        py = sys.executable
        steps = [("gate", a.candidate, [py, "-u", "scripts/run_gate_sequence.py", "--reference", a.reference]),
                 ("resume", a.candidate, [py, "-u", "scripts/resume_eval_v3.py", "--original", a.reference]),
                 ("combined", a.combined, [py, "-u", "scripts/live_check_combined.py"])]
        steps = [s for s in steps if s[0] in wanted]
        for name, cwd, cmd in steps:
            rec = {"name": name, "cwd": cwd, "command": " ".join(cmd[1:])}
            status["steps"].append(rec)
            if not wait_until(lambda: memguard.free_ram_gb() >= a.min_free_gb, latest[name], f"free RAM for {name}"):
                rec["state"] = f"not started: free RAM below {a.min_free_gb} GB until its latest start {latest[name]:%H:%M}"
                log(f"{name}: {rec['state']}")
                save()
                continue
            before = set(os.listdir(Path(cwd) / "results" / "executions")) if (Path(cwd) / "results" / "executions").exists() else set()
            rec["start"] = now().isoformat(timespec="seconds")
            rec["free_gb_at_start"] = round(memguard.free_ram_gb(), 2)
            save()
            log(f"{name}: start ({rec['free_gb_at_start']} GB free)")
            budget = max(60.0, (end - now()).total_seconds())
            with open(logdir / f"{name}.out.log", "a", encoding="utf-8") as f:
                try:
                    rec["exit"] = subprocess.run(cmd, cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=budget).returncode
                except subprocess.TimeoutExpired:
                    rec["exit"] = "killed at the end of the window"
            rec["end"] = now().isoformat(timespec="seconds")
            after = set(os.listdir(Path(cwd) / "results" / "executions")) if (Path(cwd) / "results" / "executions").exists() else set()
            rec["new_execution_folders"] = sorted(after - before)
            save()
            log(f"{name}: exit {rec['exit']}; new executions {rec['new_execution_folders']}")
        status["state"] = "finished"
    except Exception as e:  # noqa: BLE001
        status["state"] = f"error: {type(e).__name__}: {e}"
        log(status["state"])
        raise
    finally:
        if token:
            subprocess.run(["docker", "compose", "stop"], cwd=a.candidate, env={**os.environ, "PATH": os.environ.get("PATH", "")
                           + os.pathsep + DOCKER_BIN, "CHAOS_TOKEN": "x"}, capture_output=True, timeout=600)
            stack_lock.release("main", "see status.json", token=token)
            status["lock_released"] = now().isoformat(timespec="seconds")
            log("lock released")
        status["finished"] = now().isoformat(timespec="seconds")
        save()
        log_f.close()
        pidf.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
