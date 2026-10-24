# Troubleshooting: set-up and demo problems

Every message quoted here appears in the source at commit `65dd9fe` or in an existing results file; the source is given
for each one. Causes and fixes come from the code, `docs/DEMO.md` or a post-mortem. **None of these entries was
reproduced by the author**; they are inferred from code and existing records.

Commands that start, stop or recreate containers are listed because `docs/DEMO.md` gives them. On Prem's machine only Prem
runs them, under the Docker lock (`D:\eAI\STACK_LOCK.md`). Testers do not.

Never paste a token or key into a chat, document, bug report or screenshot.

How the dashboard shows backend errors: approval buttons show "Refused (<code>): <detail>", the mode selector
"Mode not changed (<code>): <detail>", the kill switch "Kill switch not changed (<code>): <detail>"
(`dashboard/app.py:249,256,265`).

---

### 1. The stack refuses to start: "set CHAOS_TOKEN to a real secret in .env"
- **Symptom:** `docker compose` stops before starting anything, with
  "error while interpolating services.evaluator.environment.CHAOS_TOKEN: required variable CHAOS_TOKEN is missing a value:
  set CHAOS_TOKEN to a real secret in .env".
- **Likely cause:** `CHAOS_TOKEN` is not set in `.env`. It is required, and the services also refuse the old default
  `evaluator-only`.
- **What to do:** the owner of the machine (Prem) sets a real secret for `CHAOS_TOKEN` in the git-ignored `.env`. Testers
  never create or read `.env`.
- **Source:** `docker-compose.yml:10`; live verified as `startup.compose_requires_chaos_token`, with the default-token
  refusals `startup.web_refuses_default_token` and `startup.evaluator_refuses_default_token`
  (`docs/results/live_check_phase1.md:10-12`).

### 2. "approval API disabled: set ETERNALAI_APPROVAL_TOKEN to a real secret" (HTTP 503)
- **Symptom:** Approve, Reject, the mode selector or the kill switch shows, for example,
  "Refused (503): approval API disabled: set ETERNALAI_APPROVAL_TOKEN to a real secret". In the Demo mode panel the
  evaluator's equivalent ("starting runs is disabled: set ETERNALAI_APPROVAL_TOKEN to a real secret") is shown as
  "The evaluator refused the approval token. Clear the field and retype it by hand."
- **Likely cause:** the brain (or the evaluator) was started without `ETERNALAI_APPROVAL_TOKEN`, or with the placeholder
  `change-me`. Every write endpoint is then disabled, whatever is typed in the field.
- **What to do:** retyping the token does not help. Prem sets a real `ETERNALAI_APPROVAL_TOKEN` in `.env` and restarts the
  stack (`docs/DEMO.md` section 0, item 1).
- **Source:** `eternalai/api.py:52-55`; `evaluator/main.py:43-47`; `dashboard/demo.py:64-65`; `dashboard/labels.py:132`;
  `eternalai/config.py:15`.

### 3. "Refused (403): invalid approval token" / "Token contains invalid characters"
- **Symptom:** after clicking Approve (or Reject, a mode, the kill switch), the dashboard shows
  "Refused (403): invalid approval token". Or it shows "Token contains invalid characters (spaces, line breaks or
  symbols). Clear the field and retype it by hand."
- **Likely cause:** 403: the field is empty or the token differs from the one the system was started with. Leading and
  trailing spaces and line breaks are removed before sending (`dashboard/app.py:82`), so a 403 means the token itself is
  different (for example extra text pasted with it). "Invalid characters": the value cannot be sent as a header at all
  (for example a line break inside it); the dashboard shows this message instead of the raw error so the token is never
  displayed.
- **What to do:** clear the field and retype the token by hand (`docs/DEMO.md` section 0 item 5, section 3).
- **Source:** `eternalai/api.py:56-57`; `dashboard/app.py:81-91,249`; `dashboard/labels.py:53,86`; `docs/DEMO.md` lines 46, 101.

### 4. The dashboard shows "Backend offline"
- **Symptom:** red text "Backend offline: start it with  uvicorn eternalai.api:app --port 8000"; panels empty; the queue
  shows "Nothing waiting for approval."
- **Likely cause:** the dashboard has had no answer from the brain's `/status` for about 6 s; the brain is down or
  unreachable.
- **What to do:** refresh the page; check `GET http://localhost:8000/status`. In the Docker demo, the brain is restarted
  with `docker compose -p eai up -d eternalai` (Prem only). The `uvicorn` command in the message is for running the brain
  outside Docker.
- **Source:** `dashboard/app.py:39-75,178-184`; `dashboard/labels.py:16`; `docs/DEMO.md` section 3, line 99.

### 5. An approval card disappeared after 120 s ("proposal expired")
- **Symptom:** the card counted down ("Expires in N s unless approved or rejected") and vanished; the incident timeline
  says "no approval within 120 s: proposal expired, escalated to a human with evidence preserved". Nothing was executed.
- **Likely cause:** nobody approved or rejected within the approval window (120 s by default, setting
  `ETERNALAI_APPROVAL_TTL_S`). This is designed: a waiting proposal must not block detection forever.
- **What to do:** in a demo, say so, wait for the Demo mode indicator to show **finished**, click **Reveal**, and start
  another challenge (`docs/DEMO.md` section 3). Approve promptly next time. If the queue showed "Nothing waiting for
  approval." while the brain had a pending proposal, check `GET http://localhost:8000/approvals`, refresh, and report it
  with the bug template: in rehearsals R4 and R5 such expiries happened and their cause is **unresolved**.
- **Source:** `eternalai/config.py:31-33`; `eternalai/engine.py:275-291`; `dashboard/views.py:230-256`;
  `dashboard/labels.py:110`; `docs/DEMO.md` lines 102-103; `docs/results/demo_rehearsal_R4.md` line 40;
  `docs/results/demo_rehearsal_R5.md` line 53.

### 6. "Mode not changed (409): kill switch is on: switch it off before leaving watch-only"
- **Symptom:** choosing Ask first or Autopilot shows that message; the pill "Kill switch ON: nothing is executed" is
  visible.
- **Likely cause:** the kill switch is on. While it is on the mode is held at Watch only.
- **What to do:** if Prem agrees, click **Kill switch** (token typed) to switch it off; the message "Kill switch is off.
  The mode stays watch-only until you change it." appears. Then choose the mode again.
- **Source:** `eternalai/api.py:163-164,169-175`; `eternalai/policy.py:48-51`; `dashboard/labels.py:87,89,92`; live verified
  as `policy.killswitch_roundtrip` (`docs/results/live_check_phase1.md:18`).

### 7. Checkouts fail with HTTP 409: inventory stock ran out
- **Symptom:** verification checkouts or the shop's checkouts fail with HTTP 409; orders answers "cannot reserve stock".
  Recoveries can no longer be verified.
- **Likely cause:** the inventory stock ran out. Every checkout reserves stock, and the load generator, surges and the
  synthetic verification checkout all consume it. This happened in benchmark v2 Stage 3.
- **What to do:** Prem runs `python scripts\stock_gate.py --restock --force`, then `python scripts\stock_gate.py --check`.
- **Source:** `app/orders/main.py:48`; `app/inventory/main.py:50`; `docs/postmortems/v2-stock-exhaustion.md` lines 4-5;
  `scripts/stock_gate.py:3-5`; `docs/DEMO.md` lines 57, 104.

### 8. "a run is already in progress" / "The evaluator is busy with another run"
- **Symptom:** starting a run is refused. From the terminal the evaluator answers HTTP 409 "a run is already in progress";
  in the Demo mode panel this is shown as "The evaluator is busy with another run (started elsewhere?). Wait and try
  again."
- **Likely cause:** a run is still running or restoring, often one started from the terminal, which the Demo mode panel
  cannot see.
- **What to do:** wait until the run finishes; never mix terminal and dashboard starts in one demo.
- **Source:** `evaluator/main.py:157-161`; `dashboard/demo.py:6-7,66-67`; `dashboard/labels.py:133`; `docs/DEMO.md` line 29.

### 9. No LLM key: the report says "template" (expected)
- **Symptom:** the incident report panel shows "Report written by: template".
- **Likely cause:** no `GEMINI_API_KEY` or `GROQ_API_KEY` is set, or the LLM call failed; the report then comes from the
  built-in template. This is expected: the LLM only writes the report and recovery is unaffected.
- **What to do:** nothing during a demo. Do not ask for or paste keys.
- **Source:** `eternalai/llm.py:116-117,151`; `eternalai/engine.py:401-403`; `dashboard/views.py:161`;
  `docs/DEMO.md` line 108 (rehearsal R2 ran without keys).

### 10. Low memory or Docker stopped during a demo
- **Symptom:** the dashboard stops updating or shows "Backend offline"; free RAM below 1 GB; Docker Desktop stopped; or the
  launcher shows a FAIL line.
- **Likely cause:** the 16.8 GB demo machine ran out of free memory (rehearsals ran with 1.55 to 3.4 GB free), or Docker
  stopped.
- **What to do:** stop the live part and show the results tables and screenshots. **There is no screen recording.** Say
  plainly that the live stack failed; do not improvise numbers. `docs/screenshots/final_banner_fixture.png` is rendered
  from test data and must be called that. Before a demo: close other apps, check free RAM with `python scripts\memguard.py`,
  start only above 2 GB free.
- **Source:** `docs/DEMO.md` section 0b (lines 52-59) and section 3 (line 98).

### 11. A service is stuck after a failed run
- **Symptom:** after a run that failed or ended unresolved, a service stays down or anomalous. A runbook may have failed
  with "expected exactly one container for <service>, found <n>".
- **Likely cause:** the container is missing, duplicated or not managed (the executor needs exactly one container with
  the service's compose label and `eai.managed=true`). A code comment in the evaluator records that two colliding restores
  once failed with a similar error ("expected 1 container ..., found 0").
- **What to do:** Prem runs `docker compose -p eai up -d --force-recreate <service>`. Never `docker compose down -v` and
  never delete a volume.
- **Source:** `docs/DEMO.md` lines 107, 110; `eternalai/executor.py:49-54`; `evaluator/main.py:139-141`.

### 12. The Demo mode panel is unusable: terminal fallback
- **Symptom:** the Demo mode panel shows "evaluator not answering", a run stays in "run in progress" or "restoring" for
  more than about 5 minutes, or the panel cannot be used.
- **Likely cause:** the evaluator is slow or not responding, or the dashboard was restarted (it forgets the runs it
  started).
- **What to do:** wait up to 3 more minutes. If still stuck, use the terminal for the rest of the demo, never both:
  `python scripts\demo_challenge.py start`, then `status <RUN_ID>` until it is no longer running, then `reveal <RUN_ID>`.
- **Source:** `docs/DEMO.md` lines 29, 31, 105-106; `dashboard/labels.py:129`; `dashboard/views.py:324-325`.

---

### 13. "Refused (409): kill switch is on: nothing is executed, not even approved actions"
- **Symptom:** clicking Approve on a card that was already waiting shows this message.
- **Likely cause:** the kill switch was switched on after the proposal was made. Approvals are refused while it is on.
- **What to do:** decide with Prem whether to switch the kill switch off; otherwise Reject or let the card expire.
- **Source:** `eternalai/engine.py:453-454`; `eternalai/api.py:139-142`.

### 14. "Refused (409): no pending approval for that incident"
- **Symptom:** Approve or Reject shows this message.
- **Likely cause:** the proposal is no longer waiting: it was already approved or rejected, or it expired.
- **What to do:** refresh the page; nothing more is needed.
- **Source:** `eternalai/engine.py:451-452,461-463`; `eternalai/api.py:139-153`.

### 15. "Switch the mode to Ask first before the unseen-fault segment."
- **Symptom:** **Start unseen-fault segment** shows this message and nothing starts.
- **Likely cause:** the unseen-fault segment is allowed only in Ask first, by design.
- **What to do:** choose **Ask first** (token typed), then start it again.
- **Source:** `dashboard/demo.py:54-55`; `dashboard/labels.py:134`; `docs/DEMO.md` line 27.

## Gaps

All 12 required topics have a source. Entries 13-15 are extra and also sourced. Messages that may appear but whose
cause is not documented anywhere (for example the pill "Rule fallbacks in use for: …", `dashboard/labels.py:18`) are not
given an entry, because a cause or fix would have to be guessed.
