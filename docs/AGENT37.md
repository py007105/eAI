# Agent37 incident investigator

Agent37 hosts an LLM agent that investigates a real EternalAI incident and explains it. EternalAI's deterministic
engine stays authoritative: it detects, diagnoses, decides with the policy engine, asks a person when required,
executes allow-listed runbooks and verifies recovery with checkout probes. Agent37 only recommends.

## How it works
1. An operator selects an incident in the dashboard and presses **Investigate with Agent37** (approval token required,
   because each run spends Agent37 credit). API: `POST /agent37/investigate/{incident_id}`.
2. EternalAI sends a bounded brief (incident fields, evidence ids, timeline, current service scores) to the Agent37
   instance (`POST https://{instance}.agent37.app/v1/responses`). Incident text is marked untrusted.
3. The agent may call up to `AGENT37_MAX_STEPS` read-only tools. It asks in JSON; EternalAI runs the tool locally and
   returns the result in the same session: `get_incident_evidence`, `get_service_health`, `get_dependency_context`,
   `search_verified_incident_history`, `get_policy_constraints`. No tool changes anything; the agent's sandbox cannot
   reach this host, Docker or the brain.
4. The final answer is validated: known service, real evidence ids only (invented ids are dropped and listed),
   runbook on the allow-list or `none`.
5. The suggested runbook is evaluated by a copy of the live `PolicyEngine` (advisory verdict; nothing recorded).
   Execution only ever happens through the incident's own engine action, the existing Approvals panel / Telegram,
   and the allow-listed executor; verification is EternalAI's checkout probes.
6. The record (steps, tokens, reported cost, finding, policy verdict) is stored in `runtime/agent37_investigations.json`
   and survives restarts. `GET /agent37/investigations/{id}` adds the incident's live engine pipeline.

Also: `GET /agent37/twin` (services, health, dependencies, open incidents, last Agent37 finding) and
`GET /agent37/graph` (services, incidents, suspected causes, proposed and executed actions, verified outcomes).
Both are plain reads with no LLM call. A diagnosis is always a SUSPECTED_CAUSE, never confirmed.

## Cost controls
- Provider-enforced: the instance's monthly managed-spend cap (`budget.monthly_cap_micros`, set at create); calls over it
  fail with `402 instance_budget_exhausted` and the investigation is marked `budget_blocked`.
- Auto-sleep after 5 idle minutes (compute bills disk only while asleep); `tools/agent37_setup.py stop --yes` stops it.
- Local: `AGENT37_LOCAL_BUDGET_USD` stops new runs once the summed per-turn `cost_usd` reported by Agent37 reaches it
  (an estimate of LLM spend only, not the bill). One investigation per unchanged incident; 3 failures in a row pause
  the feature for 10 minutes. Twin and graph never call Agent37.

## Setup
```powershell
$env:AGENT37_API_KEY = "<your key>"          # server-side only; never commit it
python tools\agent37_setup.py status          # free: wallet and budget
python tools\agent37_setup.py create --cap-usd 3 --yes   # PAID: one instance, auto-sleep, $3 monthly cap
$env:AGENT37_INSTANCE_ID = "<id printed above>"
```
Start the stack as usual (Compose passes `AGENT37_API_KEY`, `AGENT37_INSTANCE_ID` to the brain), open the dashboard
(http://127.0.0.1:8050), type the approval token, select an incident, press **Investigate with Agent37**.

## Demo
1. Healthy shop: Infrastructure twin panel shows four healthy services.
2. Bad deploy on payments (ask-first), as in the demo checklist; the incident appears and waits for approval.
3. Investigate with Agent37: watch the execution trace (turns, tools), the finding, cited evidence, missing evidence.
4. Policy verdict on the suggestion (payments is protected: `needs_approval`).
5. Approve in the existing Approvals panel (or Telegram); EternalAI executes and verifies with checkout probes.
6. The knowledge graph shows the incident, suspected causes (classifier and Agent37), executed action and verified outcome.

## Verification status (25 Oct 2026)
Live runs on one existing instance (`ao7buwhar5`, Hermes agent, monthly cap $2), brain built from this branch (`6d2eb86`).

| item | status |
|---|---|
| One real web crash; EternalAI detected it in 5.7 s, restarted web on its own (autopilot, low risk) and verified recovery with 19 checkout probes at 100 % (evaluator: recovered in 36.5 s, 0 false alerts) | VERIFIED LIVE (11:20 AM IST, incident `16442779`) |
| One investigation: 5 agent turns, 4 read-only tools run on the EternalAI host, a final JSON answer that passed schema validation (cited ev1-ev7, none dropped) | VERIFIED LIVE (11:20:58-11:21:31 AM IST, 33 s) |
| The completed finding is stored (`runtime/agent37_investigations.json` in the brain's volume) and returned identical after restarting only the brain container | VERIFIED LIVE |
| The dashboard shows the saved finding after that restart (picker lists the stored investigation; panel shows explanation, evidence, missing evidence, policy verdict) | VERIFIED LIVE (browser check; it triggered no Agent37 call) |
| Policy stays authoritative: the agent suggested no runbook, EternalAI's policy engine returned `no_action_suggested`; the executor audit shows only EternalAI's own autopilot restart, 0 Agent37-initiated actions | VERIFIED LIVE for the no-action case |
| Policy verdict when the agent DOES suggest a runbook (advisory evaluation on a copy of the policy engine, needs-approval path) | VERIFIED IN TESTS ONLY |
| Earlier live runs: run 1 failed on turn 3 with `ConnectError`; run 2's answer was rejected by the first schema (`fault` over 60 characters). Fixed: connect-only retry, trimmed free text | observed live; fixes VERIFIED IN TESTS ONLY (replay of the real answer) |
| Agent37 spend | UNCONFIRMED. After 9 live turns the instance and workspace usage endpoints read 0 LLM calls and $0.00 (compute $0.00 too, which may settle hourly); wallet unchanged at $10. Either the instance's model calls bypass the managed meter or the meter lags; per-turn `cost_usd` was reported as 0 |
| Cap | VERIFIED LIVE: `monthly_cap_micros` 2000000, 0 consumed before and after |

Not tested live: an Agent37 recommendation that needs approval and goes through the Approvals panel or Telegram; budget exhaustion (402) against the real service.

Also found by the live check: `main` could not load its frozen model files after the `eternalai` -> `engine` rename.
Fixed in `engine/artifacts.py` (legacy module names aliased); `tests/test_artifacts_load.py` loads every real artifact.
