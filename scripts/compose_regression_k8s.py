"""Package A Docker-path regression, run only in Codex's assigned stack window.

Build and start Compose from this candidate, run the existing stock and preflight
checks, then stop what this script started. A failed check is preserved as evidence.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import secrets
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from eternalai.redact import redact  # noqa: E402
from scripts.stack_lock import is_free, release, take  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
CHECKS: list[dict] = []


def now_ist():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")


def check(name, ok, detail=""):
    item = {"check": name, "result": "PASS" if ok else "FAIL", "detail": redact(str(detail)), "t": now_ist()}
    CHECKS.append(item)
    print(redact(f"[{item['result']}] {name}: {item['detail']}"), flush=True)
    return ok


def run(args, timeout=900):
    return subprocess.run([str(arg) for arg in args], cwd=ROOT, capture_output=True, text=True, timeout=timeout)


def command(args, timeout=900):
    process = run(args, timeout)
    if process.returncode:
        raise RuntimeError(f"{Path(str(args[0])).name} command exited {process.returncode}")
    return process.stdout.strip()


def free_memory_gb():
    class Status(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                    ("total_phys", ctypes.c_ulonglong), ("avail_phys", ctypes.c_ulonglong),
                    ("total_page", ctypes.c_ulonglong), ("avail_page", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong), ("avail_virtual", ctypes.c_ulonglong),
                    ("avail_extended", ctypes.c_ulonglong)]
    status = Status()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise RuntimeError("could not read available memory")
    return status.avail_phys / (1024 ** 3)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_results(head, run_id, started_at, images):
    result = {"execution_id": run_id, "started_at_ist": started_at, "finished_at_ist": now_ist(),
              "branch": "friend/phase2-k8s", "commit": head, "images": images,
              "configuration": {
                  "compose_sha256": file_hash(ROOT / "docker-compose.yml"),
                  "rulebook_sha256": file_hash(ROOT / "eternalai/rulebooks/default.yaml"),
                  "env_file_present": (ROOT / ".env").is_file(),
                  "project": "eai", "profile": "releases",
                  "preflight_tag": "benchmark-system-v2"},
              "checks": CHECKS}
    out_md = ROOT / f"docs/results/compose_regression_k8s_{run_id}.md"
    out_json = ROOT / f"results/live-checks/compose_regression_k8s_{run_id}.json"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with out_json.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    rows = ["# Kubernetes branch Compose regression", "", f"- Execution: `{run_id}`",
            f"- Time: {started_at} to {result['finished_at_ist']}", f"- Commit: `{head}`",
            f"- Configuration and image IDs: [JSON result](../../results/live-checks/{out_json.name})", "",
            "| Check | Result | Detail |", "|---|---|---|"]
    rows += [f"| {c['check']} | {c['result']} | {c['detail'].replace('|', '/')} |" for c in CHECKS]
    with out_md.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(rows) + "\n")
    return out_md, out_json


def main():
    head = command(["git", "rev-parse", "HEAD"])
    run_id = datetime.now(IST).strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(4)
    started_at = now_ist()
    origin = f"friend/phase2-k8s@{head[:7]}"
    held = False
    images = {}
    try:
        if not is_free():
            raise RuntimeError("the shared Docker lock is occupied")
        if not (ROOT / ".env").is_file():
            raise RuntimeError("Compose credentials are not configured in this worktree")
        if command(["docker", "ps", "--filter", "label=com.docker.compose.project=eai",
                    "--format", "{{.ID}}"]):
            raise RuntimeError("Compose project eai is already running")
        clusters = command([ROOT.parent / "tools/kind.exe", "get", "clusters"]).splitlines()
        if clusters:
            raise RuntimeError("a kind cluster is already running")
        available = free_memory_gb()
        if available < 3:
            raise RuntimeError(f"only {available:.2f} GiB available; Compose requires about 3 GiB")
        try:
            take("codex", "Compose regression", origin)
        except SystemExit:
            raise RuntimeError("could not acquire shared Docker lock") from None
        held = True
        check("preflight", True, f"no running eai Compose/kind; {available:.2f} GiB free")

        command(["docker", "compose", "-p", "eai", "--profile", "releases", "build"], timeout=2400)
        check("build", True, "Compose images built from candidate commit")
        command(["docker", "compose", "-p", "eai", "--profile", "releases", "up", "-d"], timeout=900)
        check("startup", True, "Compose profile releases started")
        for tag in command(["docker", "compose", "-p", "eai", "--profile", "releases",
                            "config", "--images"]).splitlines():
            if tag and tag not in images:
                images[tag] = command(["docker", "image", "inspect", "--format", "{{.Id}}", tag])

        for attempt in range(1, 25):
            stock = run([sys.executable, "scripts/stock_gate.py", "--restock", "--force"], timeout=180)
            if stock.returncode == 0:
                break
            time.sleep(5)
        check("stock_gate", stock.returncode == 0,
              f"attempts {attempt}, exit {stock.returncode}; "
              f"{redact(stock.stdout.strip().splitlines()[-1]) if stock.stdout.strip() else 'no output'}")
        preflight = run([sys.executable, "scripts/preflight.py"], timeout=180)
        lines = [redact(line) for line in preflight.stdout.splitlines() if line.startswith(("PASS  ", "FAIL  "))]
        for line in lines:
            verdict, item = line.split("  ", 1)
            check("preflight: " + item.split(":", 1)[0], verdict == "PASS", item.split(":", 1)[-1].strip())
        check("preflight_exit", preflight.returncode == 0, f"exit {preflight.returncode}")
    except Exception as exc:
        check("aborted", False, type(exc).__name__)
    finally:
        if held:
            try:
                command(["docker", "compose", "-p", "eai", "--profile", "releases", "stop"], timeout=180)
                check("compose_stopped", True, "project eai stopped; volumes preserved")
            except Exception as exc:
                check("compose_stopped", False, type(exc).__name__)
            try:
                release("codex", origin)
                check("lock_release", True, "atomic owner file released")
            except (Exception, SystemExit) as exc:
                check("lock_release", False, type(exc).__name__)
        write_results(head, run_id, started_at, images)
    return 0 if CHECKS and all(item["result"] == "PASS" for item in CHECKS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
