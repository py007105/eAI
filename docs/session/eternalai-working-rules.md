---
name: eternalai-working-rules
description: "How the user wants EternalAI work done: honest script-rendered numbers, quiet mode, explicit confirmation for releases"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 12581d58-e121-4b2e-975b-4f73c2bafca0
  modified: 2026-10-19T21:20:27.935Z
---

- Numbers in docs come from rerunnable scripts (render_*.py, build_docs.py), never hand-typed; no retuning after results; rehearsals are never mixed into benchmark statistics.
- Report the current IST time in status updates; never silently move deadlines; record misses honestly.
- Small separate local commits; secret-scan new records/screenshots (values compared, never printed) before committing; token field must be empty in every screenshot.
- Unresolved observations stay "unresolved" (e.g. expiries recorded as "visibility unresolved, observer not watching"), never upgraded to a cause.
- Quiet mode: short status reports, often "N-line status".

**Why:** the user is preparing a judged demo and values verifiable, non-overstated claims.
**How to apply:** follow these on every EternalAI task; see [[eternalai-release-status]] for current state.
- Timestamps written into documents come from the clock (`date`) or a commit time, never estimated. (2026-10-23: estimated "about 21:05" for a spec actually committed at 20:53, which made a pre-registration look written after its run; corrected to commit times.) Pre-registration is proven by commit order: commit the spec/method, then run.
