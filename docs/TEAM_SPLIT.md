# Team split for the final day (Sat 24 Oct 2026)

Feature freeze **20:00 IST**; everything merged, checked and pushed by **23:00 IST**.
Integrator: the owner (main session, `D:\eAI\eAI-release`). Only the integrator merges into `plan-complete`.
Updated 15:15 IST with the owner's decisions; this replaces the 15:00 version.

## Bases

| person | base (branch from this) | working branch |
|---|---|---|
| Rajat | `origin/friend/phase2-k8s` (`2c721f2`, Codex's Kubernetes work; 540 tests passed there) | `team/k8s-rajat` |
| Sanskar | `origin/friend/phase6-telegram` (`925d8f2`, Telegram code; tests only, not live) | `team/ui-telegram-sanskar` |
| Mihir | `origin/plan-complete` (code base `f7a28c6`) | `team/kb-ml-mihir` |

```powershell
git fetch origin
git switch -c <working branch> <base>
```

## Who owns what

You own the files listed for you, and any new file you create under those paths. To change a file you don't own, ask the integrator.

| person | area | owns |
|---|---|---|
| Rajat | Kubernetes, on Rajat's laptop (with Codex) | `deploy/**`, `eternalai/drivers/**`, `eternalai/sources/**`, `eternalai/verify_k8s.py`, `docs/KUBERNETES.md`, `docs/HANDOFF_K8S_STATUS.md`, `scripts/kind_e2e.py`, `scripts/compose_regression_k8s.py`, `scripts/k8s_window_deadline.py`, his `tests/test_k8s_*.py`, `tests/test_kind_*.py`, `tests/test_drivers.py`, `tests/test_driver_factory.py`, `tests/test_helm_chart.py`, `tests/test_service_map.py`, `tests/test_verify_k8s.py`, `docs/results/kind_e2e*.md`, `results/live-checks/kind_e2e*.json` |
| Sanskar | Telegram, dashboard UI/UX | `eternalai/notify/**`, `docs/TELEGRAM*.md`, `tests/test_telegram.py`, `tests/test_notify_*.py`, `dashboard/**` except `dashboard/app.py`, `tests/test_dashboard_*.py`, `docs/screenshots/**` |
| Mihir | knowledge base review, ML (offline), pitch, README | `data/kb/**`, `eternalai/kb/**`, `tests/test_kb*.py`, `models/**` (see the ML rule), `docs/pitch/**` (new), `README.md`, `docs/QA_FOR_JUDGES.md` |
| integrator | wiring, merges, live checks, tags | the shared files below, `docs/COORDINATION.md`, `docs/RELEASE_GATE.md`, `docs/TEAM_SPLIT.md`, `docs/results/` outside the rows above |

**Shared files: only the integrator edits these.**
- `eternalai/engine.py`
- `eternalai/api.py`
- `eternalai/policy.py`
- `eternalai/config.py`
- `eternalai/rulebook.py` and `eternalai/rulebooks/*`
- `docker-compose.yml`
- `dashboard/app.py`

If your work needs a change in one of them, describe it in your PR (function, inputs, outputs) and the integrator makes it.
**Exception, Rajat only:** his base already changes `engine.py`, `api.py` and `config.py`, and he resolves those conflicts himself (see below).

## Tasks

### Rajat: Kubernetes
1. **First task: retarget the kind end-to-end check to OUR 4-service shop.** The current manifests target Online Boutique; Online Boutique becomes roadmap.
   - Build our images locally and load them into kind with `kind load docker-image` (no registry).
   - Plain Deployments and Services for web, orders, payments, inventory and loadgen.
   - A plain Prometheus Deployment with `kubernetes_sd_configs`, scraping our services' `/metrics`. No heavy monitoring stack, no Prometheus Helm chart (that chart's readiness is the likely cause of the 14:14 failure).
2. **Then run `scripts/kind_e2e.py` on our shop** and commit every execution's result files, PASS or FAIL:
   - must have: crash → restart;
   - must have: bad deploy → rollback after approval;
   - nice to have: scale.
3. **Accepted limitation:** `cleanup()` (`clear_temp_path`) returns NotSupported on Kubernetes. Say so in `docs/KUBERNETES.md`.
4. **Before the PR:**
   - run `git merge origin/plan-complete` into `team/k8s-rajat`;
   - resolve the `engine.py`, `api.py` and `config.py` conflicts on his side;
   - get the full test suite passing; put its last line in the PR.
5. **PR into `plan-complete` by 20:00.**
   - After merging, the owner runs the Compose regression (Phase 1 live check) to prove the Docker path is unchanged.
   - The merge is kept only if every test and that check pass. Otherwise Kubernetes is demoed from Rajat's laptop on his branch and stays unmerged.

### Sanskar: Telegram + dashboard UI/UX
- Continue the Telegram work from `origin/friend/phase6-telegram`: incident updates and approve/reject buttons, with the same checks as the API.
- Live test it with his own bot; the owner supplies the token and chat ID through `.env`, never in git.
- Dashboard UI/UX polish in his files; the Hindi left-axis title is still cramped.
- PR by 19:00.

### Mihir: knowledge base, ML, pitch
- **Review the 17 KB rows** in `data/kb/`: set `reviewed_by_team` per row, only for rows actually reviewed, and note what was checked.
- **Dataset-A offline report:** Train Ticket macro-F1 next to the live classifier, same held-out data. Report only, no change to the live models.
- **Pitch** (`docs/pitch/`).
- **README and judge Q&A rewrite:** every number from a results file. Forecast: memory lead **FAILED** (median 18.3 s vs the 30 s target); disk **PASSED**.
- Docs and KB review PR by 18:30.

## Merge order (IST)
1. **18:30:** Mihir (docs, KB review).
2. **19:00:** Sanskar (UI / Telegram).
3. **20:00:** Rajat (Kubernetes), only if all tests and the Phase 1 live check pass after the merge.

- **20:00:** feature freeze; after this, only fixes for failing checks, each in its own commit.
- **20:00–23:00:** the integrator merges, runs the full suite after each merge and the live checks, tags `demo-stable-2` only if they pass, and pushes.

## Rules
- No force-push. Never `git add -A` or `git add .`; add files by name.
- No secrets in git: never commit or print `.env`, tokens, keys or kubeconfig. Scan your diff before every push.
- Push only your own `team/*` branch. Open a PR into `plan-complete`; only the integrator merges.
- Run the full test suite before the PR; put its last line in the PR (`pytest -q -p no:cacheprovider`).
- Every feature says **verified live** (with the committed script that checked it) or **tests only**. Fakes only inside `tests/`. No invented numbers.
- Never `docker compose down -v`, never delete volumes. One Docker stack per laptop at a time; kind and Compose never run together.
- **ML rule:** no model promotion tonight; the current models stay. New or retrained models go on the branch as offline results only, are never tuned on evaluation seeds, and are not merged into the release.
- The forecast memory-lead failure and the seed-426 limitation stay documented as they are.
