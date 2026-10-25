# Repository structure

The repository was reorganised into technical folders on 2026-10-25. Folders were moved with `git mv`, so
`git log --follow <file>` still shows each file's full history.

## Old path → new path

| before | after | area |
|---|---|---|
| `eternalai/` (package `eternalai`) | `engine/` (package `engine`) | core |
| `app/` | `services/shop/` | core |
| `loadgen/` | `services/loadgen/` | core |
| `evaluator/` | `evaluator/` (unchanged) | core |
| `models/` | `ml/models/` | ml |
| `data/` | `ml/data/` | ml |
| `dashboard/` | `dashboard/` (unchanged) | ui-integrations |
| `console/` (branch `team/console`) | `console/` | ui-integrations |
| `telemetry/` | `deploy/telemetry/` | platform |
| `scripts/` | `tools/` | core |

## What did not change

- Environment variable names (`ETERNALAI_*`, `EAI_*`), the Compose service name `eternalai`, container and image
  names, API paths and ports.
- The database file name `eternalai.db`.
- `docker compose ...` commands: the Compose files stay in the repository root.
- Run commands change only by the package name, for example `python -m engine.notify.bot`.

## Historical evidence keeps the old paths

These keep the old paths on purpose; use the table above to find each file today:
- Recorded evidence: `results/`, `docs/results/`, `docs/postmortems/`, `docs/session/`. Their file references (for
  example `eternalai/engine.py:450`) point at the commits named in each file.
- Pre-registered plans and gates, frozen before their results: `EVALUATION_PLAN.md`, `EVALUATION_V3_PLAN.md`,
  `FORECAST_CHECK.md`, `LIVE_CHECK_PHASE4A.md`, `NAB_EVAL.md`, `RELEASE_GATE.md`, `V2_PROPOSAL.md`, `v2_seed_plan.md`.
- Historical records: `ETERNALAI_PLAN.md`, `MODEL_CARD_v1.md`, `PLAN_GAP_CLOSURE.md`, `POST_BENCHMARK_RUNBOOK.md`,
  `HANDOFF_FRIEND.md`, `PROJECT_SNAPSHOT.md`, `docs/drafts/`, `docs/handback/`, `docs/team-qa/HANDBACK.md`,
  `docs/team-qa/TROUBLESHOOTING.md`.
- Runbooks for the demo build and the Telegram bot checkout, which run the old layout: `DEMO_CHECKLIST.md`, `DEMO.md`,
  `docs/pitch/DEMO_SCRIPT.md`, `TELEGRAM_CONTINUE_ON_NEW_PC.md`, `docs/team-qa/MANUAL_TEST_CHECKLIST.md`. Their
  commands (for example `python scripts\stock_gate.py`) are run inside `demo-stable-1`.

The demo build `demo-stable-1` (`49155ea`) and the release tags keep the old layout; they are never moved.

## Local data that git does not track

Git-ignored folders such as `data/raw`, `data/runs` and `data/processed` are not moved by `git`. After checking out
this layout, move them by hand to `ml/data/raw`, `ml/data/runs` and `ml/data/processed` if you have them.
