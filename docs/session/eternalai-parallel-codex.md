---
name: eternalai-parallel-codex
description: A Codex session works in parallel on the same machine (worktree D:\eAI\eAI-codex); Docker use goes through D:\eAI\STACK_LOCK.md
metadata:
  node_type: memory
  type: project
  originSessionId: 12581d58-e121-4b2e-975b-4f73c2bafca0
  modified: 2026-10-21T02:47:35.910Z
---

From 2026-10-21 a second AI session (OpenAI Codex CLI) works on the same machine in the git worktree `D:\eAI\eAI-codex` on `friend/...` branches (Telegram = phase 6, Kubernetes = phase 2, KB = phase 4 partial). Contract: `docs/HANDOFF_FRIEND.md` and `AGENTS.md` on `plan-complete`.

**Why:** both sessions share one `.git`, one Docker daemon (Compose project `eai`), the same ports, RAM and `eai/*` image names, so either can silently replace the other's containers or images.

**How to apply:**
- Before any Docker/kind action that starts, stops, builds or changes something, read `D:\eAI\STACK_LOCK.md`. If it is FREE, write `HELD by main | what | since | until | images built from <branch>@<hash>`; when done, write `FREE`. Rebuild images if the last holder built from another branch.
- Codex hands finished branches back locally. Merge them into `plan-complete` with a merge (no rebase), then run the full suite and the live checks.
- Never edit files in `D:\eAI\eAI-codex`.

Related: [[eternalai-working-rules]], [[eternalai-release-status]].
