"""Pre-demo checks. Prints PASS/FAIL per check and exits non-zero if any fails. Never prints a secret value.

    python scripts/preflight.py [--require-llm-key] [--tag benchmark-system-v1]

Checks: Docker daemon reachable; the four model artifacts load; the approval token inside the brain container is set and not the placeholder;
each LLM key variable is PRESENT (non-empty) inside the brain container (presence only; GROQ is reported but never required, it is untested);
the evaluator scorecard is empty; the code paths the benchmark ran are identical to the benchmark tag.
Each check is a function returning (ok, detail) so tests can replace the Docker, HTTP and git calls with mocks.
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER_TOKENS = {"", "change-me"}
MODEL_ARTIFACTS = ("baselines", "detectors", "classifier", "ranker")
BENCHMARK_PATHS = ["eternalai", "evaluator", "app", "models", "loadgen", "telemetry", "docker-compose.yml",
                   "scripts/run_benchmark.py", "scripts/run_all_arms.ps1"]
LLM_VARS = ("GEMINI_API_KEY", "GROQ_API_KEY")


def _client():
    import docker
    return docker.from_env()


def check_docker(client_factory=_client):
    try:
        client_factory().ping()
        return True, "daemon reachable"
    except Exception as e:  # noqa: BLE001 - any failure means not usable
        return False, f"daemon not reachable ({type(e).__name__})"


def check_models(loader=None):
    if loader is None:
        sys.path.insert(0, str(ROOT))
        from eternalai import artifacts
        loader = artifacts.load
    missing = [n for n in MODEL_ARTIFACTS if loader(n)[0] is None]
    return (not missing), ("all four artifacts load" if not missing else f"missing: {', '.join(missing)}")


def brain_env(client_factory=_client):
    """Environment of the running brain container as a dict (values are returned to callers but never printed)."""
    cs = client_factory().containers.list(filters={"label": "com.docker.compose.service=eternalai"})
    if not cs:
        return None
    return dict(e.split("=", 1) for e in cs[0].attrs["Config"]["Env"] if "=" in e)


def check_token(env):
    if env is None:
        return False, "brain container not running"
    tok = env.get("ETERNALAI_APPROVAL_TOKEN", "")
    return (tok not in PLACEHOLDER_TOKENS), ("approval token set" if tok not in PLACEHOLDER_TOKENS else "approval token is empty or the default")


def check_llm_keys(env, require=False):
    if env is None:
        return False, "brain container not running"
    present = {v: bool(env.get(v, "").strip()) for v in LLM_VARS}
    detail = ", ".join(f"{v} {'present' if p else 'ABSENT'}" for v, p in present.items()) + " (Groq is untested; never required)"
    return (present["GEMINI_API_KEY"] or not require), detail


def check_scorecard_empty(http_get):
    try:
        n = http_get("http://localhost:8200/scorecard")["runs"]
    except Exception as e:  # noqa: BLE001
        return False, f"evaluator not reachable ({type(e).__name__})"
    return n == 0, f"scorecard holds {n} run(s)"


def check_tag(tag, run=None):
    run = run or (lambda args: subprocess.run(args, cwd=ROOT, capture_output=True, text=True))
    if run(["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"]).returncode != 0:
        return False, f"tag {tag} not found"
    r = run(["git", "diff", "--name-only", tag, "--", *BENCHMARK_PATHS])
    changed = [x for x in r.stdout.split() if x]
    return (r.returncode == 0 and not changed), ("benchmark code paths identical to tag" if not changed else f"differs from tag: {', '.join(changed[:5])}")


def run_all(require_llm=False, tag="benchmark-system-v1", client_factory=_client, http_get=None, loader=None, run=None):
    if http_get is None:
        import httpx
        http_get = lambda url: httpx.get(url, timeout=5).json()  # noqa: E731
    docker_ok = check_docker(client_factory)
    results = [("docker daemon", docker_ok), ("models load", check_models(loader))]
    env = None
    if docker_ok[0]:
        try:
            env = brain_env(client_factory)
        except Exception:  # noqa: BLE001
            env = None
    results += [("approval token", check_token(env)), ("llm key variables", check_llm_keys(env, require_llm)),
                ("scorecard empty", check_scorecard_empty(http_get)), ("benchmark tag", check_tag(tag, run))]
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--require-llm-key", action="store_true")
    ap.add_argument("--tag", default="benchmark-system-v1")
    a = ap.parse_args()
    res = run_all(a.require_llm_key, a.tag)
    for name, (ok, detail) in res:
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")
    sys.exit(0 if all(ok for _, (ok, _) in res) else 1)


if __name__ == "__main__":
    main()
