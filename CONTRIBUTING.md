# Contributing

## Areas and folders

| area | folders |
|---|---|
| core | `engine/` (except `kb/`, `notify/`), `services/`, `evaluator/`, `tools/`, `docker-compose*.yml` |
| ml | `ml/`, `engine/kb/` |
| ui-integrations | `dashboard/`, `console/`, `engine/notify/` |
| platform | `deploy/` |

`docs/` and `tests/` are shared: change the docs and tests that belong to your area. `results/` holds recorded
evidence; add new run results, never edit old ones. The owner of each area is listed in `.github/CODEOWNERS`.

## How to make a change

1. Branch from `main`: `git switch main && git pull && git switch -c <area>/<short-topic>`
   (for example `ml/kb-ranking-fix`, `platform/kind-values`).
2. Change files in your area. If you must touch another area, say so in the pull request.
3. Run the checks for what you changed:
   - Python: `python -m pytest -q` from the repository root (the full suite must pass).
   - Console: `cd console && npm ci && npm run test -- --run && npm run lint && npm run build`.
   - Compose: `docker compose config -q` after changing a Compose file or a build path.
4. Add files by name (`git add <path>`), never `git add .`. Never commit `.env`, tokens or keys.
5. Push your branch and open a pull request into `main`. The area owner reviews it; merge after approval.

`main` is protected: no direct pushes and no force pushes. Release tags (`v1.0.0-rc.*`, `demo-stable-1`) are never
moved.

## Rules that keep results honest

- Every number in docs comes from a script or a results file; name the source.
- Unknown stays unknown: do not turn a missing value into zero or "healthy".
- Do not claim a feature runs live until a recorded run shows it (for example, Kubernetes is validated offline only).
