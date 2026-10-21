# Instructions for AI coding agents (Codex and others)

Read `docs/HANDOFF_FRIEND.md` fully before doing anything. It is the contract for working in this repository in
parallel with the main session. The short version:

- If you are the Codex session: you work only in `D:\eAI\eAI-codex` (a git worktree), only on a `friend/...` branch.
  Never read, edit or run git in `D:\eAI\eAI-release` or `D:\eAI\eAI-workspace`.
- Never read, print, log or commit `.env`, tokens, keys or kubeconfig files. Ask the owner when a secret is needed.
- Never push, force-push, rebase, `reset --hard`, amend merged commits, create/move/delete tags, delete branches, or run
  `git worktree remove/prune`, `git clean`, `git gc --prune`.
- Never `git add -A` / `git add .`; show `git status`, add files by name.
- Docker, ports and RAM are shared with the main session: before any command that starts, stops, builds or changes
  containers or a kind cluster, follow the lock protocol in `D:\eAI\STACK_LOCK.md` (handoff section 1.5).
  Never `docker compose down -v`, never delete volumes.
- Shared files (handoff section 5) change only in small separate commits starting with `shared:`.
- No fakes or mocks outside `tests/`. No invented numbers. Every feature is checked live by a committed script.
- Run `python -m pytest -q -p no:cacheprovider` (with the worktree's own `.venv`) after every commit.
