---
name: eternalai-release-status
description: "EternalAI (github.com/py007105/eAI) state on 2026-10-21 ~09:45 IST: plan-complete pushed, demo-stable-1 tagged; Phase 3/4a/5 code done, live checks pending"
metadata:
  type: project
---
Active branch: `plan-complete` (pushed to GitHub; owner's go 2026-10-21). Work folder `D:\eAI\eAI-release` (worktree); venv `D:\eAI\eAI-workspace\eAI\.venv`; Docker CLI `C:\Program Files\Docker\Docker\resources\bin`; compose project `eai`. Freeze 2026-10-23 20:00 IST.

- Done: Phase 0 gap matrix (`docs/PLAN_GAP_CLOSURE.md`), Phase 1 safety (live check 17/17, tag `demo-stable-1`, pushed).
- Code done, live checks pending: forecast every tick + forecast check v3 pre-registered (smoke: leak 37.1 s, gradual disk 86.1 s lead); forest-only -> approval; close root candidates -> abstain (margin file not yet computed); SQLite learn store + POST /feedback.
- Next: 20-run forecast check exactly as designed; root margin from runs_all; one Phase 4a live check -> tag demo-stable-2 and push it; then Phase 4 core (KB, outcome ranking, dataset-A classifier; dataset at D:\eAI\plan_dataset\, read-only, never commit the xlsx); Phase 7 re-runs per `docs/DOCKER_SCHEDULE.md`.
- Owner's standing permissions: push `plan-complete` and every `demo-stable-N` tag (never force). Changes to eternalai/, evaluator/, app/, models/ are allowed for plan work. Continuation guide: `docs/CONTINUE_ON_NEW_PC.md`.

**Why:** the owner moves between PCs and needs the exact resume point.
**How to apply:** start every session by reading `docs/CONTINUE_ON_NEW_PC.md` and section G of the gap matrix; never `down -v`, never read or print .env. See [[eternalai-working-rules]], [[eternalai-parallel-codex]].
