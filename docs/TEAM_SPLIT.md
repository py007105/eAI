# Team split for the final day (Sat 24 Oct 2026)

Feature freeze **20:00 IST**; everything merged, checked and pushed by **23:00 IST**.
Integrator: the owner (main session, `D:\eAI\eAI-release`). Only the integrator merges into `plan-complete`.

## Base

- Base commit: **`f7a28c6`** (`plan-complete` as pushed at 15:00 IST, 578 tests passed, 2 deselected).
- Branch from the commit that adds this file; its parent is `f7a28c6`:
  ```powershell
  git fetch origin
  git switch -c <your branch> origin/plan-complete
  git log --oneline -2        # this file's commit, then f7a28c6
  ```

## Who owns what

You own the files listed for you, and any new file you create under those paths. To change a file you don't own, ask the integrator.

| person | branch | area | owns |
|---|---|---|---|
| Rajat | `team/k8s-rajat` | Kubernetes (with Codex, on Rajat's laptop) | `deploy/**`, `eternalai/drivers/**`, `eternalai/sources/**`, `eternalai/verify_k8s.py`, `docs/KUBERNETES.md`, `scripts/kind_e2e.py`, `scripts/compose_regression_k8s.py`, `scripts/k8s_window_deadline.py`, `tests/test_k8s_*.py`, `tests/test_kind_*.py`, `tests/test_drivers.py`, `tests/test_driver_factory.py`, `tests/test_helm_chart.py`, `tests/test_service_map.py`, `tests/test_verify_k8s.py`, `tests/test_compose_regression_results.py`, `docs/results/kind_e2e*.md`, `results/live-checks/kind_e2e*.json` |
| Sanskar | `team/ui-telegram-sanskar` | Telegram, dashboard UI/UX | `eternalai/notify/**`, `docs/TELEGRAM*.md`, `tests/test_telegram.py`, `tests/test_notify_*.py`, `dashboard/**` except `dashboard/app.py`, `tests/test_dashboard_*.py`, `docs/screenshots/**` |
| Mihir | `team/kb-ml-mihir` | knowledge base, ML, pitch | `data/kb/**`, `eternalai/kb/**`, `tests/test_kb*.py`, `models/**` (see the ML rule below), `docs/pitch/**` (new) |
| integrator | `plan-complete` | wiring, merges, live checks, tags | the shared files below, `docs/COORDINATION.md`, `docs/RELEASE_GATE.md`, `docs/results/` outside the rows above |

**Shared files: only the integrator edits these.**
- `eternalai/engine.py`
- `eternalai/api.py`
- `eternalai/policy.py`
- `eternalai/config.py`
- `eternalai/rulebook.py` and `eternalai/rulebooks/*`
- `docker-compose.yml`
- `dashboard/app.py`

If your work needs a change in one of them, describe it in your PR (function, inputs, outputs) and the integrator makes it.

**Existing work to start from:**
- Rajat's branch starts from Codex's `friend/phase2-k8s`. That branch already changes `engine.py`, `api.py` and `config.py`; those changes are reviewed by the integrator at merge time, and no further changes to them go on the branch.
- Sanskar merges `origin/friend/phase6-telegram` (Telegram code, tests only, not live yet) into his branch first.

## Merge order and times (IST)

1. **KB / ML (Mihir):** PR by 18:00.
2. **UI / Telegram (Sanskar):** PR by 19:00.
3. **Kubernetes (Rajat):** PR by 20:00.

- **20:00:** feature freeze. After this, only fixes for failing checks, each in its own commit.
- **20:00–23:00:** the integrator merges, runs the full test suite after each merge, runs the live checks, pushes, and tags only when a gate passes.

## Rules

- No force-push. Never `git add -A` or `git add .`; add files by name.
- No secrets in git: never commit or print `.env`, tokens, keys or kubeconfig. Scan your diff before every push.
- Push only your own `team/*` branch. Open a PR into `plan-complete`; only the integrator merges.
- Run the full test suite before opening the PR and put its last line in the PR (`pytest -q -p no:cacheprovider`).
- Every feature says **verified live** (with the committed script that checked it) or **tests only**. Fakes only inside `tests/`. No invented numbers: every number comes from a script or a results file.
- Never `docker compose down -v` and never delete volumes. One Docker stack per laptop at a time; kind and Compose never run together.
- **ML rule:** retraining or changing anything in `models/artifacts/` makes a new release candidate, and the full gate rerun takes about 3 hours. That does not fit before 23:00, so tonight's release keeps the current models. New models go on the branch as **tests only / offline results**, are never tuned on evaluation seeds, and are not merged into the release.
- The forecast memory-lead failure and the seed-426 limitation stay documented as they are.
