# Kubernetes Package A: transfer status (24 October 2026 IST)

Branch: `friend/phase2-k8s`. Integration remains Claude's responsibility on `plan-complete`. This branch has not been merged into `plan-complete`. Telegram work is separate and untouched. Follow [`COORDINATION.md`](COORDINATION.md) and [`HANDOFF_FRIEND.md`](HANDOFF_FRIEND.md) sections 5–6 before changing shared files or using a shared Docker daemon.

## What is implemented and what is verified

| Item | Implementation | Evidence and remaining limit |
|---|---|---|
| Driver interface and runtime factory | Done | `eternalai/drivers/base.py` and `__init__.py`; tests only. Docker is the default runtime. |
| DockerDriver wrapper | Done | Delegates existing runbooks and audit to `Executor`; tests pass, but the Compose regression on this branch has not run. |
| KubernetesDriver restart, scale, rollback, delete Pod | Done | Namespaced, allow-listed implementation with audit and ownership checks; tests only. No recovery action was reached in kind. |
| KubernetesDriver cleanup | Interface implemented as an audited `NotSupported` result for `clear_temp_path` | Intentional minimal-scope limit; no Kubernetes cleanup runbook exists. |
| Kubernetes Deployment/Pod state reader | Done | `eternalai/sources/k8s_state.py`; tests only. |
| Service map from Deployment annotations | Done | `eternalai/sources/service_map.py`, `config.load_topology()` and static fallback flag; tests only. |
| Kubernetes Prometheus metrics source | Done | `eternalai/sources/k8s_metrics.py`; tests only. Several HTTP/demo-shop signals remain NaN for Online Boutique. |
| Helm chart | Done | `deploy/helm/eternalai/`; `helm lint` and `helm template` passed locally. No Ready brain was observed in a live cluster. |
| Namespaced RBAC | Done | Chart renders watch and ask/autopilot Roles and RoleBindings; tests only. The real `kubectl auth can-i` matrix has not run. |
| kind manifests for **our own shop** | Not started | Package A specifies Online Boutique. `deploy/kind/kind-cluster.yaml` pins the cluster node, and `deploy/online-boutique/` annotates that workload; there are no Kubernetes manifests for EternalAI's Compose demo shop. Scope any new shop port separately with the owner. |
| Scripted end-to-end check | Implemented, acceptance incomplete | `scripts/kind_e2e.py` ran once, failed during monitoring setup before the brain image build. The diagnostic change in `19c3407` has not run live. |

The 14:01 IST execution at `68c6d1d` is recorded in [`kind_e2e_20261024T140102-60f37359.md`](results/kind_e2e_20261024T140102-60f37359.md) and its [JSON record](../results/live-checks/kind_e2e_20261024T140102-60f37359.json). It passed preflight with 6.30 GiB free and created the pinned kind cluster, then recorded `RuntimeError` before Prometheus readiness. The brain image was **not built**. The script removed only cluster `eai` and released its atomic lock. The record does not establish why monitoring failed; a five-minute kubectl wait was observed, but no pod diagnosis was captured. `19c3407` adds pod phase, readiness and reason diagnostics without collecting Pod messages or secrets, and fixes Windows CLI output decoding. Neither fix has live evidence yet.

The second scheduled attempt waited below 6 GiB, acquired no lock, launched no Docker/kind command and was stopped at handover. The Compose regression script exists but was not run: the Kubernetes worktree had no owner-provided `.env`. The needed variable names are `CHAOS_TOKEN` and `ETERNALAI_APPROVAL_TOKEN`; values must be non-default and supplied by the owner. Do not read, copy, print or commit the file. The Compose preflight's historical benchmark-tag identity check may fail because this branch changes `eternalai/`; record that outcome without weakening the check.

The latest completed full suite before this handover document was on WIP commit `dc67df0`: **540 passed, 2 deselected, 1 warning** (the warning is Starlette's `httpx` deprecation). This handover commit also requires a full-suite run. Helm lint and rendering passed on this machine. No Package A feature is yet live verified end to end.

## Continue on Rajat's machine

Use a separate checkout for this branch. The commands below assume the same `D:\eAI` layout; `scripts/stack_lock.py` and `scripts/kind_e2e.py` contain `D:\eAI` paths, so review and update those in small commits with tests if the new machine uses another layout. Never use the old machine's `.venv`, kubeconfig or lock owner file.

```powershell
git clone https://github.com/py007105/eAI D:\eAI\eAI-k8s
Set-Location D:\eAI\eAI-k8s
git switch --track origin/friend/phase2-k8s
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
& D:\eAI\tools\helm.exe lint deploy\helm\eternalai
& D:\eAI\tools\helm.exe template eternalai deploy\helm\eternalai -n eternalai | Out-Null
```

Install `kind`, Helm and `kubectl` on that machine only with the owner's authorization. [`deploy/kind/VERSIONS.md`](../deploy/kind/VERSIONS.md) records pinned versions and published SHA256 values; verify the downloaded files. Ensure Docker has enough resources for kind and Online Boutique. Establish a machine-local Docker schedule and atomic lock before running a live check, and require at least **6 GiB available RAM**. Do not run kind alongside Compose. The scripts own only cluster `eai`, project `eai` and ports 18080–18082, and preserve unrelated resources and volumes. Set `EAI_K8S_WORK_DEADLINE_IST` to a real, timezone-qualified cutoff that leaves cleanup time in the assigned slot.

After the owner has established the lock and slot, run one script at a time:

```powershell
.\.venv\Scripts\python.exe scripts\kind_e2e.py
# After kind has fully torn down and its lock is released, and after the owner creates ignored .env:
.\.venv\Scripts\python.exe scripts\compose_regression_k8s.py
```

Next, inspect the new execution-specific kind result. If monitoring rollout fails again, use its safe pod-condition reasons to diagnose the real cause; keep the failed result, fix only the cause, rerun the full suite and the affected live check. Complete the scripted RBAC, topology, metrics, action, approval and rollback checks before claiming kind acceptance. Run Compose with the owner-provided configuration, preserve its per-execution result, and report every failure. Commit result files by name after a secret scan. Do not merge this branch into `plan-complete`: hand the passing commit and evidence to Claude for integration review. Package A is not ready for that merge today.
