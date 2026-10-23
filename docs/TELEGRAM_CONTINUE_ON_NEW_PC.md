# Telegram branch: continue on another PC

This note belongs to `friend/phase6-telegram`. It is a progress record, not a completed package hand-back. The
main-session plan and requirement matrix remain owned by the main session (`docs/PLAN_GAP_CLOSURE.md`); its current
decision puts package A (Kubernetes) first and package C with the main session. Preserve this Telegram branch for
later work unless the owner changes that order.

## Saved state

- Package B commits: `332aecf` (message formatter), `2f2887e` (Bot API sender and callbacks), `bde10d1`
  (notifier factory and queued delivery). The latest `plan-complete` was merged into this branch before this note.
- Unit tests after that merge: `506 passed, 2 deselected, 1 warning` from
  `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` on 2026-10-23. Every Telegram item is **verified in
  tests only**. No real bot, phone tap, or Docker live check has run on this branch.
- The Telegram update offset defaults to `runtime/telegram_update_id.txt`; `git check-ignore` confirms that path is
  ignored. The `.env`, `.venv`, runtime files, training runs, and datasets are not in git.
- Pending Package B work, in handoff order: rulebook `approvers` validation; API per-user token identity; engine hooks;
  Compose variables; hash-token script and documentation; then the real Telegram live check and hand-back. Shared-file
  edits each require their own `shared:` commit and a full test run. See `docs/HANDOFF_FRIEND.md` sections 5, 7, 11.2.

## Restore on the new Windows PC

Use paths below as examples. The main clone and the Codex worktree must be different folders. The worktree command
requires the pushed `origin/friend/phase6-telegram` branch.

```powershell
git clone https://github.com/py007105/eAI D:\eAI\eAI-release
cd D:\eAI\eAI-release
git switch plan-complete
git worktree add -b friend/phase6-telegram D:\eAI\eAI-codex origin/friend/phase6-telegram
cd D:\eAI\eAI-codex
git status
git log --oneline -5
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
git check-ignore .env runtime/telegram_update_id.txt
```

The owner must transfer `.env` securely and configure any needed Telegram bot token, chat id, and approver identities
by hand. Never paste those values into an AI chat, commit them, or copy `.venv` between PCs. The main-session guide
`docs/CONTINUE_ON_NEW_PC.md` lists the other non-git items to transfer, including training runs and Claude memory.
Recreate `D:\eAI\STACK_LOCK.md` and adjust machine-specific paths as that guide describes before any Docker or kind
work. Unit tests need no Docker lock.

## Prompt for Codex on the new PC

> Work only in `D:\eAI\eAI-codex` on `friend/phase6-telegram`. Read `AGENTS.md`,
> `docs/HANDOFF_FRIEND.md`, and `docs/TELEGRAM_CONTINUE_ON_NEW_PC.md` fully. The main session owns
> `D:\eAI\eAI-release`; never read, edit, or run git there. Confirm branch, clean status, local and remote heads,
> and the full test suite. Merge `plan-complete` into this friend branch when it has advanced; never rebase.
> The first three Telegram commits are done, tests only. Confirm with the owner whether to resume package B now,
> since the updated handoff gives package A priority. If resuming B, start with prompt 11.2 item 4: the rulebook
> approvers key. Make one small commit at a time, with each shared file in its own `shared:` commit. Run the full suite
> after every commit and show the last line. Do not push without the owner's go. Do not touch Docker without the
> shared stack lock. No secrets may be read or logged.
