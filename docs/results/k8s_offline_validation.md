Kubernetes: manifests and chart validated offline, driver unit-tested. NOT run on a live cluster.

# Offline validation evidence

Validated 2026-10-24 (IST) in detached worktree `D:\eAI\eAI-k8s-check`, source `origin/team/k8s-rajat` at `7f531649cc25440b6e3a050974eec91cb1763978`. No Docker or cluster was used.

Tools: Helm `v3.21.3+g1ad6e68`; `helm-v3.21.3-windows-amd64.zip` SHA256 `ff490897e07e976c65a9bd7690cfc139b35ba5e8f25d00eaf1e53a30f1ad3f62` (matches requested pin). Kubeconform `v0.8.0`; official release ZIP SHA256 `e3f56102bcf4f50b034a567e2482a1c5330799983ddd655952310211aef73d93`, matched the downloaded official `CHECKSUMS` entry before extraction.

Chart: `deploy/helm/eternalai`; values: `deploy/kind/shop/values-shop.yaml`.

- `helm lint deploy/helm/eternalai -f deploy/kind/shop/values-shop.yaml` — PASS; 1 chart linted, 0 failed (only the optional icon recommendation).
- `helm template eternalai deploy/helm/eternalai -f deploy/kind/shop/values-shop.yaml > rendered.yaml` — PASS; rendered `rendered.yaml` (3,711 bytes).
- Kubeconform `-strict -summary` on `rendered.yaml` plus the shop YAMLs — 26 Kubernetes resources validated, 0 invalid; the extra `values-shop.yaml` was correctly rejected as a non-manifest (missing `kind`). A later isolated retry excluding values could not retrieve schemas because the configured proxy at `127.0.0.1:9` refused connections. The initial 26-resource pass is the available schema evidence; no live cluster validation was attempted.
- `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -k "kind or k8s or kubernetes or helm"` — `57 passed, 587 deselected, 1 warning in 10.67s` (exit 0). One Starlette/httpx deprecation warning.

Driver action coverage: `tests/test_k8s_driver.py::test_recovery_actions_use_namespaced_apis_and_audit` covers `restart_service` (restart), `scale_to` (scale), `recreate_container` (delete owned pod), and `rollback_release` (rollback). These are mocked unit tests, not live actions.

Slide bullets:
- Helm lint and template passed for the shop configuration.
- Kubeconform accepted all 26 rendered/shop Kubernetes resources; the values file is not a Kubernetes manifest.
- Kubernetes-focused tests: 57 passed; restart, scale, pod deletion, and rollback are unit-tested only.
