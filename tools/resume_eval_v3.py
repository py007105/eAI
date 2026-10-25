"""Resume an incomplete evaluation-v3 execution: run exactly its missing registered cases, nothing else.

    python tools/resume_eval_v3.py --original 20261024T001813-4cedc8bf      # from the ORIGINAL pinned checkout

Why this is a valid resumption (docs/EVALUATION_V3_PLAN.md is unchanged): every case is independent - a fixed seed, a
brain reset before every run (tools/run_benchmark.py reset_brain) and its own evaluator run - and the runner itself skips
(arm, scenario, seed) cases already present in its results file ("rerun the arm to retry"). So:
- refuse unless this checkout is at the original commit, with no change in the system code, the image IDs equal the
  original manifest's, and the configuration hashes equal the original manifest's;
- a NEW execution ID, linked to the original in its manifest; its results file starts as a byte copy of the original
  rows, so the runner runs only the missing cases, with the original commands and arguments (tools/run_final_eval.py);
- afterwards the original rows must be unchanged and every added row must be a case that was missing, at most once
  (tools/eval_v3_cases.py check_resume). Original and resumed rows are rendered separately; a combined table only if
  that check passes and all 50 cases are present. The memory guard is unchanged (--min-free-gb 1.5).
- Takes the Docker lock atomically (tools/stack_lock.py) and releases only its own lock.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import eval_v3_cases as cases  # noqa: E402
import stack_lock  # noqa: E402

ROOT = HERE.parent
DOCKER_BIN = r"C:\Program Files\Docker\Docker\resources\bin"
SYSTEM_PATHS = ["eternalai", "models", "data", "dashboard", "services", "evaluator", "loadgen", "docker-compose.yml",
                "tools/run_benchmark.py", "tools/run_final_eval.py", "tools/stock_gate.py", "tools/memguard.py"]


def sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def git(*a) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def image_ids(env) -> dict:
    out = {}
    for img in sorted(set(subprocess.run(["docker", "compose", "--profile", "releases", "config", "--images"], cwd=ROOT,
                                         env=env, capture_output=True, text=True).stdout.split())):
        r = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", img], env=env, capture_output=True, text=True)
        out[img] = r.stdout.strip() or None
    return out


def preflight(orig: dict, env) -> list[str]:
    problems = []
    if git("rev-parse", "--short", "HEAD") != orig["commit"]:
        problems.append(f"checkout is not at the original commit {orig['commit']}")
    changed = git("status", "--porcelain", "--untracked-files=no", "--", *SYSTEM_PATHS)
    if changed:
        problems.append(f"system code or evaluation scripts changed in this checkout: {changed}")
    now = image_ids(env)
    if now != orig.get("images"):
        problems.append("image IDs differ from the original execution: "
                        + json.dumps({k: [v, now.get(k)] for k, v in (orig.get("images") or {}).items() if now.get(k) != v}))
    conf = {rel: sha(ROOT / rel) for rel in orig.get("configuration", {})}
    if conf != orig.get("configuration"):
        problems.append("configuration hashes differ from the original execution")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", required=True, help="execution ID to resume")
    ap.add_argument("--preflight-only", action="store_true", help="only check commit, code, images and configuration (read-only)")
    a = ap.parse_args()
    orig_dir = ROOT / "results" / "executions" / a.original
    orig = json.loads((orig_dir / "manifest.json").read_text(encoding="utf-8"))
    orig_raw = ROOT / "results" / "benchmark-v3" / a.original / "raw.jsonl"
    original_rows = cases.rows(orig_raw)
    missing = cases.missing_cases(original_rows)

    if a.preflight_only:
        env = {**os.environ, "PATH": os.environ.get("PATH", "") + os.pathsep + DOCKER_BIN, "CHAOS_TOKEN": "x"}
        problems = preflight(orig, env)
        print(json.dumps({"original": a.original, "original_rows": len(original_rows), "missing": len(missing),
                          "problems": problems}, indent=1))
        sys.exit(1 if problems else 0)
    eid = f"{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    ex = ROOT / "results" / "executions" / eid
    ex.mkdir(parents=True, exist_ok=False)
    raw = ROOT / "results" / "benchmark-v3" / eid / "raw.jsonl"
    raw.parent.mkdir(parents=True, exist_ok=False)
    log = raw.parent / "run.log"
    tok = secrets.token_urlsafe(24)
    base = {k: v for k, v in os.environ.items() if k not in ("CHAOS_TOKEN", "ETERNALAI_APPROVAL_TOKEN")}
    env = {**base, "ETERNALAI_APPROVAL_TOKEN": tok, "EAI_EVALUATOR_TOKEN": tok, "EAI_BENCH_TOKEN": tok,
           "CHAOS_TOKEN": secrets.token_urlsafe(24), "OTEL_SDK_DISABLED": "true", "ETERNALAI_POLICY_FILE": "",
           "GEMINI_API_KEY": "", "GROQ_API_KEY": "", "EAI_EXEC_ID": eid,
           "PATH": base.get("PATH", "") + os.pathsep + DOCKER_BIN}
    man = {"execution_id": eid, "kind": "resumption of evaluation v3", "resumes_execution": a.original,
           "original_commit": orig["commit"], "commit": git("rev-parse", "--short", "HEAD"),
           "resume_script_sha256": sha(Path(__file__)), "cases_module_sha256": sha(HERE / "eval_v3_cases.py"),
           "original_rows": len(original_rows), "original_raw_sha256": sha(orig_raw),
           "cases_to_resume": [list(c) for c in missing], "steps": [], "completion": "running", "started": stack_lock.ist()}

    def save():
        (ex / "manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")

    save()
    problems = preflight(orig, env)
    if problems:
        man.update(completion="refused", problems=problems, finished=stack_lock.ist())
        save()
        sys.exit("refused: " + "; ".join(problems))
    man["images"], man["configuration"] = orig["images"], orig["configuration"]
    shutil.copyfile(orig_raw, raw)          # the runner skips every case already in its results file
    token = stack_lock.take("main", f"evaluation v3 resumption {eid} of {a.original}", f"plan-complete@{orig['commit']}")
    man["lock_taken"] = stack_lock.ist()
    save()

    def sh(cmd, timeout=8 * 3600):
        rec = {"command": " ".join(str(c) for c in cmd), "start": stack_lock.ist()}
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"\n== {stack_lock.ist()} {rec['command']}\n")
            f.flush()
            try:
                rec["exit"] = subprocess.run(cmd, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=timeout).returncode
            except subprocess.TimeoutExpired:
                rec["exit"] = "timeout"
        rec["end"] = stack_lock.ist()
        man["steps"].append(rec)
        save()
        return rec

    try:   # the same commands as tools/run_final_eval.py main()
        services = subprocess.run(["docker", "compose", "config", "--services"], cwd=ROOT, env=env, capture_output=True,
                                  text=True).stdout.split()
        sh(["docker", "compose", "up", "-d", "--force-recreate", *[s for s in services if s != "jaeger"]], 900)
        time.sleep(60)
        py = sys.executable
        sh([py, "tools/stock_gate.py", "--restock", "--force"], 300)
        sys.path.insert(0, str(ROOT / "tools"))
        import run_final_eval as rf  # noqa: E402  (the candidate's own constants)
        common = ["--manage-stack", "--reps", "5", "--seed0", "600", "--raw", str(raw), "--models-label", rf.MODELS,
                  "--policy-file", "", "--min-free-gb", "1.5"]
        sh([py, "-u", "tools/run_benchmark.py", "--arm", "eternalai_autopilot", *common, "--scenarios", *rf.ALL])
        sh([py, "tools/stock_gate.py", "--restock"], 300)
        sh([py, "-u", "tools/run_benchmark.py", "--arm", "no_action", *common, "--scenarios", "memory_leak"])
    finally:
        sh(["docker", "compose", "stop"], 600)
        stack_lock.release("main", f"plan-complete@{orig['commit']}", token=token)
        man["lock_released"] = stack_lock.ist()
        combined = cases.rows(raw)
        v = cases.check_resume(original_rows, combined)
        man["resume_check"] = v
        man["completion"] = ("complete: all 50 cases" if v["valid"] and not v["still_missing"]
                             else f"incomplete: {len(v['still_missing'])} cases still missing" if v["valid"] else "INVALID resumption")
        man["finished"] = stack_lock.ist()
        save()
        render(eid, a.original, original_rows, combined, v)


def render(eid, orig_id, original_rows, combined, v):
    import run_final_eval as rf
    outdir = ROOT / "docs" / "results" / "benchmark_v3_resume"
    outdir.mkdir(parents=True, exist_ok=True)
    tmp = ROOT / "results" / "benchmark-v3" / eid
    parts = [("original", original_rows, f"execution `{orig_id}`"),
             ("resumed", combined[v["original"]:], f"resumption `{eid}` (only the added cases)")]
    if v["valid"] and not v["still_missing"]:
        parts.append(("combined", combined, f"original + resumption, all {len(combined)} registered cases"))
    for name, rows_, label in parts:
        p = tmp / f"{name}.jsonl"
        p.write_text("".join(json.dumps(r) + "\n" for r in rows_), encoding="utf-8")
        rf.RAW, rf.OUT, rf.EXEC_ID = p, outdir / f"{eid}_{name}.md", f"{label}"
        rf.render()
    summary = ["# Evaluation v3 resumption", "",
               f"- Resumption execution `{eid}` of `{orig_id}`; check: `{json.dumps(v)}`.",
               "- Reports: " + ", ".join(f"`docs/results/benchmark_v3_resume/{eid}_{n}.md`" for n, _, _ in parts) + ".",
               "- A combined table exists only when the original rows are unchanged, every added case was missing, nothing is "
               "duplicated, and all 50 registered cases are present."]
    (outdir / f"{eid}_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
