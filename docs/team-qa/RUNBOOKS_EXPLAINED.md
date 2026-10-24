# The four runbooks, explained

A **runbook** is one of the four fixed recovery actions EternalAI can run. Only these four exist
(`eternalai/executor.py:1-7`, allow-list `eternalai/rulebook.py:23`). They act on Docker containers through fixed argument
lists; nothing from the LLM or from a user string is passed to a shell (`eternalai/executor.py:9-10`).

All citations refer to commit `65dd9fe`. Everything below is **inferred from code** unless an "Evidence" line names a
results file. The author did not run the system.

**How a runbook gets chosen (applies to all four).** The diagnosis gives a fault type. The table `CAUSE_RUNBOOKS`
(`eternalai/classify.py:19-26`) lists candidate runbooks per fault; the report template takes the first candidate
(`eternalai/llm.py:76`) and the engine proposes the report's runbook (`eternalai/engine.py:347`). If the system abstains
("insufficient evidence"), no runbook is proposed and the incident is escalated to a human (`eternalai/engine.py:392`,
`eternalai/engine.py:421-425`). The policy then decides whether the proposal runs, waits for approval or is blocked
(`eternalai/engine.py:426-439`, `eternalai/policy.py:59-95`).

**Modes (applies to all four).** The rulebook's default mode is **Ask first** (`eternalai/rulebooks/default.yaml:5`); it
can be changed on the dashboard. In short (`eternalai/policy.py:82-95`):
- **Watch only:** the proposal is recorded; nothing is executed.
- **Ask first:** every proposal waits for **Approve**.
- **Autopilot:** only `low`-risk proposals run without asking (`default.yaml:6`); `medium` and `high` wait for approval.
- On **payments** every proposal waits for approval in Ask first and Autopilot (`default.yaml:7`, `policy.py:89-90`).

---

## restart_service

**What it does.** Restarts the service's container in place, like switching a stuck program off and on. The same
container comes back with the same settings (Docker is given 5 seconds to stop it) (`eternalai/executor.py:94-97`).

**When EternalAI proposes it.** First choice when a service is **down**, has an **error spike** or a **latency spike**;
second choice for a **memory leak**, which is not proposed by default because the first candidate is used
(`eternalai/classify.py:20-21,24-25`; `eternalai/llm.py:76`).

**Risk and approval.** Base risk **low** (`eternalai/rulebooks/default.yaml:15`), raised to **medium** when the diagnosis is
an error spike or latency spike (`default.yaml:26-27`; a fault override only raises risk, `eternalai/rulebook.py:61-70`).
- **Autopilot:** a restart for a **down** service runs without asking (low); for an error or latency spike it waits for
  **Approve** (medium) (`default.yaml:6`, `eternalai/policy.py:91-95`).
- **payments:** always waits for approval (`default.yaml:7`).
- **Ask first:** always waits. **Watch only:** never runs (`policy.py:82-83`).

**How success is checked.** After the action EternalAI waits 3 seconds (`eternalai/engine.py:488`), then places one test
checkout per second for 20 seconds (`eternalai/config.py:29`, `eternalai/verify.py:31-39`). A checkout counts as good when
it returns a confirmed order within 1 second (`verify.py:19-26,32,41`). All good: **recovered**; at least half:
**partially recovered**; otherwise **unresolved** (`verify.py:42-43`). Only "recovered" closes the incident as recovered
(`engine.py:497-504`).

**What can go wrong / what it does not fix.**
- It does not undo a bad release (that is `rollback_release`) and does not delete leftover files (that is
  `clear_temp_path`) (`eternalai/executor.py:3-7`).
- If not exactly one managed container is found for the service, the action fails with
  "expected exactly one container for <service>, found <n>" and the incident is escalated (`executor.py:49-54`,
  `engine.py:481-486`).
- On an unseen fault the diagnosis can point at the wrong service: in benchmark v2 (cpu_burn, seed 426) autopilot
  restarted the healthy `inventory` service while the fault was on `orders`; verification was 0/4 and the incident ended
  unresolved (`docs/postmortems/cpu_burn_seed426.md`, lines 8-11).

**Evidence.**
- **Live verified:** a crash on `web` was restarted by Autopilot and verified recovered
  (`docs/results/live_check_phase1.md`, check `live.autopilot_low_executes`, line 19, 2026-10-21).
- **Live verified:** a restart proposed for **payments** was low risk but waited for approval; it was rejected and nothing
  was executed on payments (check `live.protected_waits`, line 20).
- **Live verified:** the audit log recorded the web restart with the reason "autopilot: low-risk runbook allowed by the
  rulebook" and its verification "recovered" (check `audit.reason_and_verification`, line 24).

**Sources.** `eternalai/executor.py:49-54,94-97`; `eternalai/classify.py:19-26`; `eternalai/llm.py:76`;
`eternalai/rulebooks/default.yaml:5-7,15,26-27`; `eternalai/rulebook.py:61-70`; `eternalai/policy.py:82-95`;
`eternalai/engine.py:481-504`; `eternalai/config.py:29`; `eternalai/verify.py:19-46`;
`docs/results/live_check_phase1.md:19-20,24`; `docs/postmortems/cpu_burn_seed426.md:8-11`.

---

## recreate_container

**What it does.** Stops and removes the service's container, then creates a new one from the **same image**, with the
same name, network alias, environment, volume bindings (see "Data volumes" below), memory limit, ports and restart policy, and starts it
(`eternalai/executor.py:99-102`, helper `_recreate_from` at `executor.py:63-83`). Unlike a restart, the running process
and anything kept only inside the old container are thrown away; the module describes this as clearing leaked state
(`executor.py:5`).

**Data volumes (scope of the check).** The code copies the volume bindings from `HostConfig.Binds`
(`executor.py:69-70`). On the tested configuration (Docker Compose 5.6.0, this repository's `docker-compose.yml`) a
read-only inspection showed the named data volumes in `Binds` (e.g. `eai_inventory-data:/data:rw`), so they are passed
on. This was checked by inspection on that version only; it is not a guarantee for other Compose/Engine versions, and no
live check recreates a container and verifies its data afterwards.

**When EternalAI proposes it.** First choice for a **memory leak**; second choice for a **down** service, which is not
proposed by default because the first candidate (restart) is used (`eternalai/classify.py:20-21`; `eternalai/llm.py:76`).
A container that was killed for running out of memory is diagnosed as a memory leak directly (`eternalai/engine.py:386-387`).

**Risk and approval.** Base risk **low** (`eternalai/rulebooks/default.yaml:17`), but **high** on `orders`, `payments` and
`inventory`, the services that own a data volume (`default.yaml:20-23`; a per-service entry replaces the base risk,
`eternalai/rulebook.py:64`).
- **Autopilot:** runs without asking only on **web** (low). On orders, payments and inventory it waits for **Approve**
  (high risk always requires approval, `eternalai/policy.py:93-94`).
- **payments:** always waits for approval (`default.yaml:7`).
- **Ask first:** always waits. **Watch only:** never runs.

**How success is checked.** The same check as every runbook: 3 s wait, then 20 s of test checkouts; recovered /
partially recovered / unresolved (`eternalai/engine.py:488-504`, `eternalai/config.py:29`, `eternalai/verify.py:31-46`).

**What can go wrong / what it does not fix.**
- The old container is stopped and removed **before** the new one is created (`executor.py:77-82`). If creation fails, the
  action is logged as failed and the incident is escalated (`executor.py:130-133`, `eternalai/engine.py:481-486`); the code
  has no step that brings the old container back. (Inferred from code; not observed.)
- It does not change the release: a bad image is recreated as the same bad image (`executor.py:101`). That is
  `rollback_release`.
- "Expected exactly one container for <service>, found <n>" when the container lookup fails (`executor.py:52-53`).

**Evidence.**
- **Benchmark under the previous policy:** autopilot memory_leak 3/3 recovered (`docs/results/benchmark_v2.md:38`).
  That benchmark ran under `eternalai/rulebooks/benchmark-v2.yaml`, where recreate was low on web and medium elsewhere
  and autopilot ran low and medium automatically (`benchmark-v2.yaml:7,18,22`). Under the current rulebook a recreate on
  orders, payments or inventory would wait for approval. The results table records the scenario and outcome, not which
  runbook ran.
- **Live verified:** none. `docs/results/live_check_phase1.md` has no check that runs `recreate_container`.

**Sources.** `eternalai/executor.py:5,52-53,63-83,99-102,130-133`; `eternalai/classify.py:20-21`; `eternalai/llm.py:76`;
`eternalai/engine.py:386-387,481-504`; `eternalai/rulebooks/default.yaml:7,17,20-23`; `eternalai/rulebook.py:64`;
`eternalai/policy.py:93-94`; `eternalai/rulebooks/benchmark-v2.yaml:7,18,22`; `docs/results/benchmark_v2.md:38`.

---

## rollback_release

**What it does.** Replaces the service's container with one built from the **previous release image**: among the images
labelled for this service, the one with the highest release number (`eai.release_seq`) lower than the current one
(`eternalai/executor.py:104-108`, helper `_previous_release` at `executor.py:85-91`). The replacement keeps the container's
name, network, volumes (in the tested configuration only; see "Data volumes" under `recreate_container`) and limits
(`executor.py:63-83`), but settings that came from the old image are not carried over,
so the older image's own settings apply (`executor.py:29-39`).

**When EternalAI proposes it.** Only for a **bad deploy** (`eternalai/classify.py:23`).

**Risk and approval.** **High** on every service (`eternalai/rulebooks/default.yaml:18`). High risk can never run
automatically: the rulebook loader refuses `high` in the auto-allowed list (`default.yaml:6`, `eternalai/policy.py:6`).
- **Autopilot:** waits for **Approve** ("high-risk action always requires approval", `policy.py:93-94`).
- **Ask first:** waits. **Watch only:** never runs.

**How success is checked.** The same check as every runbook (`eternalai/engine.py:488-504`, `eternalai/config.py:29`,
`eternalai/verify.py:31-46`).

**What can go wrong / what it does not fix.**
- If no earlier release image exists for the service, the action fails with "no earlier release image for <service>" and
  the incident is escalated (`executor.py:89-90`, `engine.py:481-486`).
- Like a recreate, the old container is removed before the new one starts (`executor.py:77-82`).
- It only helps when the fault came from the release; for other faults it is not proposed (`classify.py:19-26`).

**Evidence.**
- **Live verified:** a bad deploy on `orders` in Autopilot produced a rollback proposal with risk high; nothing ran before
  approval; after approval it ran and was verified recovered (`docs/results/live_check_phase1.md`, check
  `live.high_risk_needs_approval`, line 22, 2026-10-21). The audit log shows it with actor `human:live-check` (check
  `audit.reason_and_verification`, line 24).
- **Benchmark under the previous policy:** autopilot bad_deploy 3/3 recovered (`docs/results/benchmark_v2.md:40`). In that
  policy rollback was medium (low on web) and ran automatically (`eternalai/rulebooks/benchmark-v2.yaml:7,19,22`); under
  the current rulebook it always waits for approval.

**Sources.** `eternalai/executor.py:29-39,63-91,104-108`; `eternalai/classify.py:19-26`;
`eternalai/rulebooks/default.yaml:6,18`; `eternalai/policy.py:6,93-94`; `eternalai/engine.py:481-504`;
`docs/results/live_check_phase1.md:22,24`; `docs/results/benchmark_v2.md:40`; `eternalai/rulebooks/benchmark-v2.yaml:7,19,22`.

---

## clear_temp_path

**What it does.** Inside the service's container, deletes the files named `fill-*.bin` that sit directly in the approved
temporary folder `/tmp/eai-scratch` (not in sub-folders) (`eternalai/executor.py:110-116`, `eternalai/config.py:26`). Nothing
else is deleted; the folder and pattern are fixed in code (`executor.py:112`).

**When EternalAI proposes it.** Only for a **disk fill** (`eternalai/classify.py:22`).

**Risk and approval.** Base risk **low** on every service (`eternalai/rulebooks/default.yaml:16`).
- **Autopilot:** runs without asking, except on **payments**, where it waits for approval (`default.yaml:6-7`).
- **Ask first:** waits. **Watch only:** never runs.

**How success is checked.** The same check as every runbook (`eternalai/engine.py:488-504`, `eternalai/config.py:29`,
`eternalai/verify.py:31-46`).

**What can go wrong / what it does not fix.**
- If the delete command exits with an error, the action fails with "clear_temp_path failed: <first 200 characters of the
  output>" and the incident is escalated (`executor.py:113-115`, `engine.py:481-486`).
- It does not remove files with other names or in other folders (`executor.py:112`).

**Evidence.**
- **Benchmark under the previous policy:** autopilot disk_fill 3/3 recovered (`docs/results/benchmark_v2.md:39`).
  `clear_temp_path` was low risk in that policy too (`eternalai/rulebooks/benchmark-v2.yaml:17`), but the previous policy
  had no protected services, no hourly cap and a 90 s cooldown (`benchmark-v2.yaml:8,10-11`).
- **Rehearsal (not a verification):** in demo rehearsal R4 a `clear_temp_path → payments` proposal expired unapproved after
  121.2 s (`docs/results/demo_rehearsal_R4.md`, lines 8 and 17); in R5 a `clear_temp_path → orders` proposal expired after
  121.2 s (`docs/results/demo_rehearsal_R5.md`, line 9). These show the approval window, not the runbook.
- **Live verified:** none. `docs/results/live_check_phase1.md` has no check that runs `clear_temp_path`.

**Sources.** `eternalai/executor.py:110-116`; `eternalai/config.py:26,29`; `eternalai/classify.py:22`;
`eternalai/rulebooks/default.yaml:6-7,16`; `eternalai/engine.py:481-504`; `eternalai/verify.py:31-46`;
`docs/results/benchmark_v2.md:39`; `eternalai/rulebooks/benchmark-v2.yaml:8,10-11,17`;
`docs/results/demo_rehearsal_R4.md:8,17`; `docs/results/demo_rehearsal_R5.md:9`.

---

## Safety rules that apply to every runbook

The policy checks these in a fixed order before the mode is even considered (`eternalai/policy.py:3-5,59-95`).

| rule | what it means | sources | evidence |
|---|---|---|---|
| **Kill switch** | When on, the mode becomes Watch only, every proposal is blocked ("kill switch is on: nothing is executed"), and even approvals are refused. Leaving Watch only is refused until it is switched off; switching it off leaves the mode at Watch only. | `eternalai/policy.py:48-51,68-69`; `eternalai/engine.py:453-454`; `eternalai/api.py:163-175` | live verified: `policy.killswitch_roundtrip` and `live.killswitch_blocks` (`docs/results/live_check_phase1.md:18,21`) |
| **Cooldown 40 s** | After an action on a service, a new action on the same service is blocked for 40 s. | `eternalai/rulebooks/default.yaml:10`; `eternalai/policy.py:78-79` | inferred from code |
| **Circuit breaker** | After 2 actions on a service without a verified recovery, every further action on it is blocked until a verified recovery; the dashboard shows "Circuit breaker open". | `default.yaml:11`; `policy.py:73-77,102-105`; `dashboard/labels.py:19`; `dashboard/app.py:202-203` | inferred from code |
| **Hourly cap 10** | At most 10 executed actions per hour across all services. A verified recovery does not reset it. | `default.yaml:9`; `policy.py:56-57,80-81,102-103` | inferred from code |
| **Audit log** | Every action, successful or failed, is appended to `runtime/audit.jsonl` with runbook, service, actor, policy reason, result or error, and evidence ids; the verification result is appended too. | `eternalai/executor.py:22,56-61,119-138`; `eternalai/engine.py:494-496` | live verified: `audit.reason_and_verification` (`docs/results/live_check_phase1.md:24`) |
| **The LLM never triggers an action** | The LLM only writes report text. The proposal comes from the deterministic table and the policy decides; when an LLM report arrives later its runbook is replaced by the one actually proposed. | `eternalai/policy.py:1`; `eternalai/classify.py:17-18`; `eternalai/engine.py:347,410-415`; `eternalai/llm.py:76` | `docs/DEMO.md` line 92 cites code-path analysis, 12 isolation tests and ten live incidents (`docs/results/llm_live.md`; not re-checked here) |

Also: a proposal that nobody approves expires after 120 s and is escalated with its evidence kept
(`eternalai/config.py:31-33`, `eternalai/engine.py:275-291`).
