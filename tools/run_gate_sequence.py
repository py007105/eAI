"""Re-run every live release-gate item (G2-G7) of one candidate in ONE new execution, including the G5 stimulus.

    python tools/run_gate_sequence.py --reference 20261024T001813-4cedc8bf     # from the candidate's pinned checkout

docs/RELEASE_GATE.md: every result must name the candidate commit and the execution ID; a file from another execution
does not count. So after a G5 INCOMPLETE the live items are all repeated here, in one execution:
  phase1 (G2), phase4a --no-build (G3), controlled (G4, G6, G7 and the old C2 attempt), g5 (G5, tools/live_check_g5.py).
It reuses tools/run_v3_sequence.py unchanged (atomic lock held for the whole run, fresh execution folder, manifest,
outputs copied with SHA256, fail-closed verdicts). It does not build: it refuses unless the checkout is at the reference
execution's commit with unchanged system code and the image IDs and configuration equal the reference manifest's, and it
re-checks the image IDs at the end. The tracked result files left by the reference execution are restored to the commit
first, only after checking that the reference execution kept identical copies. Never promotes anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import resume_eval_v3 as resume  # noqa: E402  (the same preflight as the evaluation resumption)
import run_v3_sequence as seq  # noqa: E402
import stack_lock  # noqa: E402

ROOT = seq.ROOT
STEPS = [("phase1", ["tools/live_check_phase1.py"], "docs/results/live_check_phase1.md", 3600),
         ("phase4a", ["tools/live_check_phase4a.py", "--no-build"], "docs/results/live_check_phase4a.md", 3600),
         ("controlled", ["tools/live_check_controlled.py"], "docs/results/live_check_controlled.md", 3 * 3600),
         ("g5", ["tools/live_check_g5.py"], "docs/results/live_check_g5.md", 2 * 3600)]
EXTRA = {"phase1": ["results/live-checks/phase1.json"], "phase4a": ["results/live-checks/phase4a.json"],
         "controlled": ["results/live-checks/controlled.json"], "g5": ["results/live-checks/g5.json"]}
HARNESS = ["tools/run_gate_sequence.py", "tools/live_check_g5.py", "tools/resume_eval_v3.py", "tools/eval_v3_cases.py"]


def sha(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def restore_left_outputs(ref_dir: Path, dry: bool = False) -> list:
    """Tracked result files modified by the reference execution: restore them only if that execution kept them."""
    changed = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True,
                             text=True).stdout.split("\n")
    paths = [ln[3:].strip() for ln in changed if ln.strip()]
    kept = [p for p in paths if sha(ROOT / p) == sha(ref_dir / "outputs" / p)]
    if kept != paths:
        raise SystemExit(f"tracked changes not kept by the reference execution, refusing: {sorted(set(paths) - set(kept))}")
    if kept and not dry:
        subprocess.run(["git", "checkout", "--", *kept], cwd=ROOT, check=True)
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", required=True, help="execution whose commit, images and configuration must match")
    ap.add_argument("--preflight-only", action="store_true", help="read-only: check, restore nothing, run nothing")
    a = ap.parse_args()
    ref_dir = ROOT / "results" / "executions" / a.reference
    ref = json.loads((ref_dir / "manifest.json").read_text(encoding="utf-8"))
    env = {**seq.os.environ, "PATH": seq.os.environ.get("PATH", "") + seq.os.pathsep + seq.DOCKER_BIN, "CHAOS_TOKEN": "x"}
    if a.preflight_only:
        print(json.dumps({"would_restore": restore_left_outputs(ref_dir, dry=True), "problems": resume.preflight(ref, env),
                          "exec_id_would_be": seq.EXEC_ID}, indent=1))
        return
    restored = restore_left_outputs(ref_dir)
    problems = resume.preflight(ref, env)
    seq.EXEC_DIR.mkdir(parents=True, exist_ok=False)
    manifest = {"execution_id": seq.EXEC_ID, "kind": "release-gate live items G2-G7 (re-run in one execution)",
                "commit": ref["commit"], "reference_execution": a.reference, "checkout": str(ROOT),
                "restored_tracked_outputs": restored, "harness_sha256": {h: sha(ROOT / h) for h in HARNESS},
                "images": ref["images"], "configuration": ref["configuration"], "steps": [], "completion": "running",
                "started": stack_lock.ist()}
    seq.save(manifest)
    if problems:
        manifest.update(completion="refused", problems=problems, finished=stack_lock.ist())
        seq.save(manifest)
        sys.exit("refused: " + "; ".join(problems))
    token = stack_lock.take("main", f"gate sequence {seq.EXEC_ID} at {ref['commit']}", f"plan-complete@{ref['commit']}")
    manifest["lock_taken"] = stack_lock.ist()
    seq.save(manifest)
    try:
        for name, cmd, results_rel, timeout in STEPS:
            rec = seq.run_step([sys.executable, "-u", *cmd], timeout, token, manifest, name)
            seq.collect(rec, [results_rel] + EXTRA[name])
            rec["verdict"] = seq.verdict(rec, results_rel, ref["commit"])
            seq.save(manifest)
        manifest["images_after"] = seq.image_ids()
        manifest["images_unchanged"] = manifest["images_after"] == ref["images"]
        v = {r["name"]: r["verdict"]["status"] for r in manifest["steps"]}
        manifest["gate_live_items_all_passed"] = (len(v) == 4 and all(s == "PASS" for s in v.values())
                                                  and manifest["images_unchanged"])
        manifest["completion"] = "complete"
    except Exception as e:  # noqa: BLE001
        manifest["completion"] = f"incomplete: {type(e).__name__}: {e}"
        raise
    finally:
        manifest["finished"] = stack_lock.ist()
        seq.save(manifest)
        stack_lock.release("main", f"plan-complete@{ref['commit']}", token=token)
        manifest["lock_released"] = stack_lock.ist()
        seq.save(manifest)


if __name__ == "__main__":
    main()
