# Plan gap closure: ETERNALAI.md vs this repository

Phase 0 of the plan-completion work. Written 2026-10-20 (IST) on branch `plan-complete`, created from `release-candidate` at `c587d20`. No code was changed for this document.

- **Plan:** `C:\Users\premy\OneDrive\Desktop\ETERNALAI.md` (outside the repository; 794 lines, all read). Plan references are written `P:<line>`.
- **Evidence:** repository references are `path:line` at commit `c587d20`. They are not updated for later commits.
- **Branch `hardening`:** four commits made on 2026-10-20 (`480e15c`, `4c0222f`, `a8c9051`, `8d48de5`) already implement several Phase 1 items. They are **not** on this branch. Rows they cover are marked "on `hardening`". Bringing them in is decision D1.
- **Status values:** Done / Done differently / Partial / Not started / Conflicts.
- **"Done differently" rows** end with one of two verdicts:
  - **meets intent:** the current version already meets or exceeds what the plan wants; nothing to add;
  - **add plan version:** the plan's version must be built as well, next to the current one.
- **Phase:** where the work is scheduled (1-7, as in the request). "0" means a decision or input is needed first (sections B and C).

Existing work that is **not in the plan** and must keep working: independent evaluator with private truth, pre-registered benchmarks v1/v2 with checksums, calibration, novelty gate, approval expiry, release grace and suppression, baseline brains, Demo mode, rehearsal capture tooling, generated docs, the Docker Compose demo. Every phase re-runs the full test suite. Phases 2-7 also re-run `scripts/preflight.py` against the Compose stack before they close.

---

## A. Requirement matrix

### A1. Loop, steps and timing (P:40, P:71-85, P:274-292)

| ID | Plan | Requirement | Status | Evidence | Work needed | Acceptance criterion | Phase |
|---|---|---|---|---|---|---|---|
| L1 | P:40, P:195 | Loop runs every 2 s | Done | `eternalai/engine.py:450`; `telemetry/prometheus.yml:2` | none | existing | - |
| L2 | P:75, P:278 | Read 8 health signals per service (p95, err, traffic, CPU, memory, restarts/OOM, readiness, + saturation) | Done differently | 12 queries per service, `eternalai/collector.py:18-31` | Meets intent for Docker. Kubernetes source must give the same frame (K2). | `Prom.signals()` returns the same columns from either source (unit test with recorded responses) | 2 |
| L3 | P:278, P:503 | Collect pod state, restarts, deploy events, limits from the orchestrator | Done differently | Docker state + events, `collector.py:98-127` | Add plan version for Kubernetes (K3). | Kubernetes state reader returns running/restarts/OOMKilled/image/revision/limits for every pod of a test Deployment on kind | 2 |
| L4 | P:270, P:279 | Learn each service's normal **on site** during the first days (rolling mean/std, IF fit on normal data) | Done differently | detectors trained offline on this app's runs, `models/artifacts/detectors.json`; loaded at start, `engine.py:94` | Add plan version: an on-site baseline learner (absorbs only values that looked normal), used for any service without a trained detector, e.g. Online Boutique. | On a new app, after N healthy minutes the learner has a baseline per signal, and an injected fault produces z > 3 on the right signal (test with synthetic series + kind run) | 3 |
| L5 | P:83, P:288 | Verify 16 s later, root **and all callers**; +30 s grace; retry next fix once; then escalate | Partial | wait 3 s + 20 checkouts at 1 s through the whole chain, `engine.py:394-399`, `verify.py:19-46`; one action per incident, no retry (`engine.py:405-416`) | Generic verification of root + upstream callers from the service map (health signals, not only the shop checkout); grace window; retry once with the next-ranked fix; then escalate. Keep the checkout probe for the shop. | Test: failing first fix triggers exactly one retry with fix #2, then escalation; callers' health is part of the verdict; settings come from config | 4 |
| L6 | P:84, P:290 | Plain-English report (template or LLM) to Slack/Telegram/dashboard | Partial | template + LLM report on dashboard, `engine.py:309-333`; no Slack/Telegram | Notifications (N1-N4). | see N1-N4 | 6 |
| L7 | P:85, P:289, P:343-345 | Learn: append incident rows (A features+label, C fix+outcome, B for solved unknowns) and retrain | Not started | only `runtime/incidents_verified.jsonl` append for retrieval, `investigate.py:152-156` | Learn store + dataset-format rows + retraining pipeline (S1-S4). | after each closed incident, one A row and one C row exist in the store; retraining produces a new versioned artifact | 5 |
| L8 | P:270 | Trained models run only when an incident opens | Done | classifier/ranker called in `_diagnose`, `engine.py:271-314` | none | existing | - |
| L9 | P:292 | Model input = last 1-3 min, relative to own normal, + orchestrator context | Done differently | 10 s window features relative to healthy medians, `features/window.py:38-116` | Meets intent for the live classifier. The dataset-A classifier needs the plan's schema (D3). | - | 4 |

### A2. Detection (P:298-308, P:196-197)

| ID | Plan | Requirement | Status | Evidence | Work needed | Acceptance criterion | Phase |
|---|---|---|---|---|---|---|---|
| D1 | P:300, P:196 | z-score per signal: z > 3 and min absolute gap, 3 checks in a row, warm-up 15, baseline absorbs only normal values | Partial | exists only in the v1 baseline brain, `eternalai/baselines.py:75-110`; not in the main engine | Add z-score detection to the engine next to forest + learned limits (kept). Constants from config/env, defaults §6.3. | Unit tests for gap, streak, warm-up, no absorption of abnormal values; the engine reports which signal fired | 3 |
| D2 | P:302, P:197 | Isolation Forest on healthy data, 100 trees, features `[p95, err, cpu, mem_ratio, sat]`, score < −0.08 for 5 checks | Done differently | 200 trees, 10 relative features, threshold learned from validation (+0.05), 3-tick persistence, `detect.py:21-26`, `:75-100`; CV says the forest "added nothing measurable" over the limits (`docs/results/detector_margin.md`) | Meets intent (trained on healthy data, thresholds from validation). Plan constants become config defaults for the on-site detector (L4) only; the trained detector keeps its fitted values. | The on-site detector uses the plan's constants unless overridden (test) | 3 |
| D3 | P:304-308 | Never show raw scores; rank signals by z to explain; levels normal/watching/abnormal; message in words | Partial | dashboard status line in words (`dashboard/views.py`); evidence summaries include raw metric values (`investigate.py:56-64`); ranked-cause chart shows support numbers | Explanation builder: top signals by z, level colour, sentence with current vs normal and trend. Replace raw scores in UI and report. | No UI string or report contains an anomaly score; test on a fixed incident gives the plan-style sentence | 3 |
| D4 | P:308 | Forest fires but no single signal explains it → "unusual combination" → no automatic action | Not started | anomaly from forest alone is not distinguished (`detect.py:97-100`) | Mark forest-only incidents "unusual combination"; policy forces needs_approval / no auto action. | Test: forest-only anomaly in autopilot → no execution | 3 |
| D5 | P:224, P:694 | Event-level precision/recall and detection delay, no point-adjust, vs fixed thresholds (CPU > 90%) | Partial | detection rate and time to detect per run (`evaluator/scoring.py:12-52`, `docs/results/benchmark_v2.md:59-71`); no precision/recall table; no fixed-threshold baseline except threshold_restart | Evaluation script over benchmark raw rows: event P/R, delay median/range; fixed-threshold comparator. | `docs/results/detect_events.md` generated from raw files by script | 7 |
| D6 | P:362 | Dataset D: detector tests on NAB AWS CloudWatch (20 series) and SMD | Not started | not present | Download NAB/SMD, run detector, report event-level scores. | Results file with per-series event P/R, generated by script | 3 |
| D7 | - | Idle false alerts; zero-width learned error limits on payments/inventory | Open issue | 7 idle incidents in R4, 7 in R5/R5b (`docs/results/demo_rehearsal_R4.md`, `demo_rehearsal_R5.md`); limits (−0.0, 0.0) | Minimum-width floor for learned limits (plan's "min absolute gap", P:300). Measure idle incidents before/after on the same idle duration. Does not retrain the classifier. | Measured idle incidents per hour before vs after, same stack, same duration, reported as measured | 3 |

### A3. Prediction (P:310-314, P:198-201)

| ID | Plan | Requirement | Status | Evidence | Work needed | Acceptance criterion | Phase |
|---|---|---|---|---|---|---|---|
| F1 | P:312, P:198 | Time to limit: linear fit on last 8 points, trust if R² ≥ 0.8, act when eta ≤ fix time + margin (memory 75 s, disk 60 s) | Done differently | Theil-Sen over 120 s with confidence bound, horizon 90 s, > 25% of limit, `forecast.py:14-30`, `config.py:28`, `engine.py:419-447` | Meets intent statistically (robust slope with a confidence bound). Add per-resource margins (75/60 s) as config. **Never fired live** (`docs/FORECAST_CHECK.md`). | Live forecast check records real lead times (F3) | 3 |
| F2 | P:313-314, P:199 | Holt traffic forecast (α 0.4, β 0.15, 16 s ahead); scale out before saturation, scale back in when calm | Not started | not present (`git grep -i holt` empty outside baselines) | Holt forecaster; capacity per service (config/annotation); scale_out / scale_in runbooks through policy; replica min/max. | Unit test of the recurrences; on kind, a surge leads to a scale-out proposal before p95 exceeds the limit, and scale-in after calm | 3 |
| F3 | P:696 | Lead time and crashes prevented, leak/disk with vs without | Not started | `docs/FORECAST_CHECK.md`: "No result exists" | Run the forecast check live (needs RAM headroom, C3). | Results file with measured lead times and crash counts | 3 |

### A4. Root cause (P:316-320, P:648)

| ID | Plan | Requirement | Status | Evidence | Work needed | Acceptance criterion | Phase |
|---|---|---|---|---|---|---|---|
| R1 | P:318 | Rule baseline (deepest abnormal) kept as safety net; recent deploy ≤ 300 s prime suspect | Done | fallback `engine.py:277-279`; `recent_deploy` feature `rca.py:17-18` | none | existing | - |
| R2 | P:319 | Trained gradient-boosted ranker, target `is_root`, top-1/top-3 | Done differently | trained on own 105 runs (`models/artifacts/ranker.json`); top-1 0.978, top-3 1.000 out-of-fold (`docs/results/models_cv_v2.md`) | Add plan version trained on dataset A (`root_cause_train_sampled.csv`) and report both on the same held-out data. | Both rankers scored on the same never-seen-system split | 4 |
| R3 | P:319 | Graph features `depth_from_entry`, `callers_client_lat_max_ratio` | Partial | has `n_anomalous_callees`, `n_anomalous_callers`, `caller_blame` (`rca.py:17-18`); no depth or client-latency | Add both features (client latency from dependency-call histograms or traces). | Feature present in the evidence table; tests | 4 |
| R4 | P:320, P:456, P:648 | Service map from OTel service graph / traces / annotation `eternalai.io/depends-on`; static fallback | Not started | static `config.py:18-19` | Discovery: annotations on kind; traces (Jaeger already in compose, `docker-compose.yml:120`); static map as fallback. | On kind with Online Boutique, the discovered map equals the published call graph; with discovery off, static map used | 2 |
| R5 | P:328 | Two strong root candidates at once → unknown | Not started | not present | Abstain when the top-2 ranker support is within a margin chosen on validation. | Test: near-tie ranking → abstain, no action | 4 |
| R6 | - | Wrong-service action on unseen fault (seed 426) | Open issue | `docs/postmortems/cpu_burn_seed426.md:8-21` | R5 + D4 reduce this; re-run seed 426 after Phase 4. | Seed 426 re-run reported as measured | 7 |

### A5. Fault identification (P:114-135, P:322-329, P:649-650)

| ID | Plan | Requirement | Status | Evidence | Work needed | Acceptance criterion | Phase |
|---|---|---|---|---|---|---|---|
| C1 | P:116-135 | 15 fault types + normal: memory_leak, cpu_runaway, disk_filling, resource_exhaustion, crash, crash_loop, oom_kill, slow_service, overload, db_slowdown, network_delay, packet_loss, dns_failure, bad_deploy, bad_config, app_error (the table lists 16 types; the heading says 15) | Partial | live classifier: 6 fault classes + healthy, `classify.py:14` | Dataset-A classifier with the plan's types; Chaos Mesh data for missing ones (E3). Plan's count to be stated as measured (16 rows). | Classifier exposes every plan type; per-class report on held-out data | 4 |
| C2 | P:324-326, P:650 | HistGradientBoosting trained on `train_balanced.csv`, joblib, loaded in brain | Done differently | `SafeHGB` (HGB wrapper) trained on own runs, calibrated, `models/train_models.py:230-241` | Add plan version trained on dataset A (needs C1 input). Keep current classifier. | Both classifiers loadable; brain config chooses; both reported on the same held-out data | 4 |
| C3 | P:327, P:650 | Unknown threshold (e.g. 0.6) chosen on `val_real.csv`, never test | Done differently | novelty gate (0.99 quantile of OOF distances, 1.1166) + confidence < 0.40, from out-of-fold data, `classify.py:47-57`, `novelty.py:52-67` | Meets intent for the live model (chosen without test data). Add plan's threshold selection on `val_real.csv` for the dataset-A model. | Threshold file records the validation set it came from; test score computed once | 4 |
| C4 | P:329 | Coarser `category` (6 groups) as fallback | Not started | only a column name in `data/label_map.py:26` | Category model; used when fault-type confidence is low but category confidence is high. | Test: low type confidence + high category confidence → category shown, no automatic fault-specific fix | 4 |
| C5 | P:650, P:691 | Macro-F1 + confusion matrix on `test_unseen_system_real.csv` (Train Ticket); unknown rate on `test_unknown_fault_real.csv`; vs majority and v1 rules | Not started | files not present; RCAEval experiments only (`docs/results/transfer_re1.md:12`) | Needs dataset A (C1). | Results file generated by script | 4 |
| C6 | P:701 | Re-measure plan baselines: 96% mixed / 33% (12-59%) never-seen; root top-3 0.75-0.80 OB, 0.18-0.43 large; unknown AUROC ≈ 0.66 | Not started | needs dataset A | Re-run on dataset A; write the measured values into the plan text. | Measured numbers replace plan numbers where they differ | 4 |
| C7 | P:649, P:748 | Feature builder: live incident → exact dataset schema §10.4 with neutral filling, unit test | Not started | live schema differs (`features/window.py:53-116`) | `features` builder for the dataset-A schema (all §10.4 columns, neutral fill); unit test reproducing a dataset row. | Unit test: bench incident → row equal to the stored dataset row | 4 |
| C8 | P:420 | Neutral filling (ratio 1, change 0) applied at run time too | Done differently | live model uses NaN + `_obs` masks (`models/artifacts/classifier.json`) | Meets intent for the live model (missing ≠ normal is stricter). Plan's neutral fill used for the dataset-A model only. | - | 4 |
| C9 | P:393 | Never use dataset-identity features (source, system, case_id…) | Done | live features list, `classifier.json`; system probe shows RCAEval features still carry identity (0.892-0.896, `transfer_re1.md:34`) | Repeat the system-identification probe for the dataset-A model. | Probe result reported | 4 |
| C10 | P:440-443, P:753 | Split by incident and system; no synthetic rows in val/test; thresholds from validation; never-seen-system score as headline | Partial | grouped splits `eternalai/evaluation/splits.py`; headline today is in-distribution 0.991 for the live model | Apply to dataset A; report never-seen-system macro-F1 as the headline. | Generated results file states the split | 4 |

### A6. Fix choice (P:331-335, P:651)

| ID | Plan | Requirement | Status | Evidence | Work needed | Acceptance criterion | Phase |
|---|---|---|---|---|---|---|---|
| X1 | P:333, P:436 | Knowledge base: every fix per fault, risk, automation, when to use / not, verify condition, time to effect, permanent fix, source, `reviewed_by_team` | Not started | `data/processed/knowledge_base.csv` read by `investigate.py:22-23` is not present | KB files from the workbook (B_* CSVs); loader + validation. | KB loads; every fault type has ≥ 1 fix; rows without `reviewed_by_team` are flagged in UI | 4 |
| X2 | P:334, P:651 | Outcome ranking: no crash > recovered > fewer failed requests > faster; KB prior flagged when unmeasured | Not started | fixed table `classify.py:19-26` | Ranking module over C outcomes; replaces the fixed table; fixed table kept as fallback. | Incident shows ranked fixes with "measured" / "prior" flags; test with a fixture C table | 4 |
| X3 | P:651 | Incident shows probabilities, chosen fix, backups, KB link | Partial | probabilities and the single runbook shown (dashboard) | Show backups and KB row. | UI test with a fixture incident | 4 |
| X4 | P:335, P:725 | cpu_runaway: act only if users are affected | Not started | cpu_burn is "unseen" here (`evaluator/scenarios.py:16-26`) | `fault_overrides.cpu_runaway.act_only_if_user_impact` in the rulebook (P1). | Test: cpu_runaway with entry-service errors 0 → no action | 1/4 |

### A7. Actions and drivers (P:504, P:544-555, P:646, P:747)

| ID | Plan | Requirement | Status | Evidence | Work needed | Acceptance criterion | Phase |
|---|---|---|---|---|---|---|---|
| A1 | P:747 | One driver interface across Docker, local, Kubernetes: `replicas()`, `restart()`, `scale_to()`, `rollback()`, `cleanup()` | Not started | single Docker executor, `eternalai/executor.py` | `Driver` interface; `DockerDriver` = current executor (unchanged behaviour); `KubernetesDriver`; `LocalDriver` (A6). | Same interface tests pass against Docker fake, Kubernetes fake and kind | 2 |
| A2 | P:504, P:546-550, P:646 | Kubernetes: rolling restart (`restartedAt` annotation), scale (`deployments/scale`), delete pod, rollback (previous ReplicaSet template), cleanup via app endpoint or Job (not `pods/exec`) | Not started | no `kubernetes` import | `KubernetesDriver` with the official client. | kind end-to-end script: each action changes the cluster as expected and is audited | 2 |
| A3 | P:216 | scale_up / scale_to runbooks; replicas min 1, max 3 | Not started | not present | Docker: scale via additional containers is not supported by the current shop (fixed names); Kubernetes: scale. | Scale works on kind; Docker driver reports "not supported" explicitly | 2 |
| A4 | P:213 | Restart "with helper replica first" (no downtime) | Not started | restart/recreate in place, `executor.py:94-102` | Kubernetes rolling restart gives this; Docker driver documents that it cannot. | kind: zero failed probes during restart of a 2-replica Deployment | 2 |
| A5 | P:504 | Other Kubernetes controls listed: pause rollout, change limits, patch HPA, cordon node, create Job | Not started | not present | Listed as capabilities, not in the build plan (P:646). See decision D8. | per D8 | 0 |
| A6 | P:158, P:172, P:622 | Local-process runtime (`run_local.py`, `LocalDriver`, `RUNTIME=local`) | Not started | not present | `LocalDriver` + launcher; see decision D8. | per D8 | 0 |
| A7 | P:555, P:750 | Never read Secrets; never write to databases; no deletes of deployments/namespaces/PVCs | Done (Docker) | runbooks limited to 4 actions, `executor.py:94-117` | Enforce in RBAC (H2) and in a driver test that refuses other verbs. | RBAC test: `kubectl auth can-i` denies these verbs | 2 |
| A8 | P:586 | Audit: what, why, evidence, who approved, result | Partial | time, runbook, service, actor, ok, result/error, evidence ids (`executor.py:56-60`, `:119-132`); no reason, no verification result | Add reason and verification outcome to the audit record. | Audit record has all six fields (test) | 1 |

### A8. Policy and safety (P:578-587, P:625-636, P:652)

| ID | Plan | Requirement | Status | Evidence | Work needed | Acceptance criterion | Phase |
|---|---|---|---|---|---|---|---|
| P1 | P:625-636, P:652 | Rulebook YAML (`POLICY_FILE`): mode, protected_services, auto_allowed_risks, max_actions_per_hour, namespaces, fault_overrides; loaded at start and validated | Not started | rules in code, `policy.py:13-59` | YAML loader + schema validation; current constants become the default file; invalid file refuses start. | Tests: valid file loads; each invalid field refused with a message; default file reproduces current decisions | 1 |
| P2 | P:218, P:583 | Rollback and other high-risk actions (config revert, limit changes, DB anything) always need approval, in every mode | Conflicts | autopilot executes rollback, `policy.py:57-58`. **On `hardening` (`480e15c`): fixed** (high risk, never auto) | Bring in; extend "high" to config revert, limit change, any DB action. | Test over every runbook x service x mode: high never executes without approval | 1 |
| P3 | P:207, P:630 | Autopilot runs only `auto_allowed_risks` (plan YAML example: `[low]`; v1: low/medium) | Partial | autopilot runs low and medium (`policy.py:57-58`) | `auto_allowed_risks` from the rulebook; default per D3. | Test per risk level | 1 |
| P4 | P:217 | v1 risk table: cpu_runaway / error_spike / latency_spike restart = medium | Done differently | restart is low on all services (`policy.py:13-19`) | Risk per (fault, action) in the rulebook so the plan's table can be expressed. | Default file reproduces plan risks when selected (test) | 1 |
| P5 | P:582, P:629, P:652 | Protected services (payments, databases): **always need approval** in any mode | Partial | not present at `c587d20`. On `hardening`: protected = **observe_only** (never proposed for approval), which is stricter than and different from the plan | Protected → needs_approval (plan), from the rulebook; see D2. | "Payments action always waits for approval" in autopilot (test + kind check) | 1 |
| P6 | P:580 | Kill switch: one toggle returns everything to Watch mode | Not started | not present. On `hardening`: env + token-protected `POST /killswitch` blocks every action and refuses approvals | Bring in; also set mode to watch-only when switched on, as the plan says. | Test: switch on → mode watch-only, no action executes, approvals refused | 1 |
| P7 | P:581, P:631 | Cap on actions per hour | Not started | not present | `max_actions_per_hour` from the rulebook, counted from the audit log. | Test: action N+1 within the hour → blocked | 1 |
| P8 | P:581, P:202, P:741 | Max 2 attempts per incident | Done differently | 1 action per incident; breaker after 2 unverified per service (`config.py:25`, `policy.py:49-53`) | Add plan version with L5 (retry once). | Test: at most 2 executed actions per incident | 4 |
| P9 | P:581, P:202, P:752 | 40 s cooldown per service; scale cooldown 10 s; defaults as §6.3 | Conflicts | cooldown 90 s, not env-overridable (`config.py:24`) | Make configurable; default per D3. | Env/rulebook override test | 1 |
| P10 | P:581 | One service at a time | Done | new incident only if none open/executing/verifying (`engine.py:189-195`) | none | existing | - |
| P11 | P:584 | Crash loops never "fixed" by more restarts; roll back with approval | Not started | not present | `crash_loop` detection (restarts rising / CrashLoopBackOff) → rollback proposal (high). | Test: rising restart count → no restart executed | 4 |
| P12 | P:585, P:749 | Unknown faults never auto-fixed | Done | abstain → escalate, `engine.py:336-340` | none | existing | - |
| P13 | P:634-635 | `fault_overrides`: cpu_runaway act only if user impact; db_slowdown escalate | Not started | not present | Rulebook overrides (X4). | tests | 1 |
| P14 | P:632 | `namespaces` allowed list | Not started | not applicable to Docker | Rulebook + driver refuse targets outside the list. | Test: action in a non-listed namespace → blocked | 2 |
| P15 | P:498-499 | Adoption stages: Shadow mode (compare suggestions with what engineers did); partial autopilot on chosen services | Not started | modes `watch-only/ask-first/autopilot` only (`config.py:13`) | Per-service autopilot list in the rulebook; Shadow = watch-only + a record of what engineers did, via feedback (S3). | Tests | 5 |
| P16 | P:207, P:603 | Mode names `watch` / `ask` / `autopilot` | Done differently | `watch-only` / `ask-first` / `autopilot` | Meets intent; accept the plan names as aliases. | `POST /mode {"mode":"ask"}` works | 1 |

### A9. Security and deployment (P:471-555)

| ID | Plan | Requirement | Status | Evidence | Work needed | Acceptance criterion | Phase |
|---|---|---|---|---|---|---|---|
| H1 | P:475-482, P:656 | Helm chart: brain Deployment, Service + Ingress, PVC, ServiceAccount + Role/RoleBinding per namespace, ConfigMap (rulebook), Secret, models in image; `helm install` works on a fresh cluster in Watch mode | Not started | not present | `deploy/helm/eternalai/`. Models are already baked into the image (`eternalai/Dockerfile:8`). | `helm install` on fresh kind → brain Ready in watch mode (scripted) | 2 |
| H2 | P:534-571 | Least-privilege namespaced RBAC: read role for watch; act role as in the YAML; never Secrets, deletes of deployments/namespaces/PVCs, RBAC, kube-system | Not started | not present | Roles in the chart; mode-dependent binding. | `kubectl auth can-i` matrix test on kind | 2 |
| H3 | P:482 | 1-2 brain replicas with leader election | Not started | not present | Lease-based leader election; only the leader acts. | kind: 2 replicas, kill leader, the other takes over, no double action | 2 |
| H4 | P:484 | Chart can install kube-prometheus-stack if none exists | Not started | not present | Optional chart dependency. | `--set prometheus.install=true` brings up Prometheus on kind | 2 |
| H5 | P:486, P:574 | Docker hosts only through a socket proxy allowing list/restart | Conflicts | raw Docker socket mounted read-write in brain and evaluator (`docker-compose.yml:59`, `:75`) | Socket proxy for the brain (allowlist the calls the 4 runbooks need); evaluator keeps its own access (test harness). | Brain container has no raw socket; the 4 runbooks still pass the live runbook check | 1 |
| H6 | P:574, P:247 | Dashboard behind SSO (OIDC) with an approver list | Not started | token typed into the dashboard; no login | OIDC login (needs an identity provider, C5) + approver list (N5). | Unauthenticated dashboard request → login; non-approver cannot approve | 6 |
| H7 | P:490, P:341, P:587 | Data stays in cluster; LLM input redacted | Partial | raw ERROR log lines go to the LLM (`investigate.py:77-94`, `llm.py:83-87`) | Redaction (M2). | see M2 | 1 |
| H8 | P:538, P:540 | Prometheus read-only token; cloud read-only via IRSA/Workload Identity | Not started | Prometheus has no auth | Prometheus bearer token support in the collector. Cloud identity needs a cloud account (C6). | Collector sends the token when configured (test) | 2 |
| H9 | - | Published ports, unauthenticated fault start, default chaos token (request item) | Not started | all interfaces (`docker-compose.yml:36-120`); `POST /challenge/start`, evaluator `POST /runs` open; `CHAOS_TOKEN` default `evaluator-only`. On `hardening` (`a8c9051`): fixed | Bring in; update the 9 harness scripts that call `POST /runs` to send the token. | Tests in `tests/test_network_lockdown.py`; benchmark drivers still start runs | 1 |
| H10 | - | Engine lock held during I/O (request item) | Not started | `engine.py:178-201`, `:271-314`, `:430-446`. On `hardening` (`4c0222f`): fixed | Bring in. | `GET /approvals` < 200 ms during a slow diagnosis (test) | 1 |

### A10. LLM (P:337-341, P:465)

| ID | Plan | Requirement | Status | Evidence | Work needed | Acceptance criterion | Phase |
|---|---|---|---|---|---|---|---|
| M1 | P:339, P:749 | Gemini/Groq/template fallback; LLM never acts | Done | `llm.py:116-147`; 12 isolation tests (`tests/test_llm_isolation.py`) | Keep. | existing tests | - |
| M2 | P:341 | Redact secrets/PII before sending | Not started | `llm.py:83-87` | Redactor for tokens, keys, emails, IPs, card-like numbers, bearer headers; applied to every outbound field. | Tests with seeded secrets: none reach the request body | 1 |
| M3 | P:339 | Default Gemini model `gemini-2.5-flash` (plan) | Conflicts | code default `gemini-3.8-flash`, 0/5 valid live (`llm.py:22`, `docs/results/llm_live.md:17`); demo uses `gemini-3.5-flash-lite`, 4/5 valid | Default to the model that was measured to work; record the measurement; plan text updated to the measured choice. Re-check live needs the Gemini key in `.env` (not read by me). | Default model equals a model with a recorded live result | 1 |
| M4 | - | Gemini key in URL query | Not started | `llm.py:93` | Send as `x-goog-api-key` header. | Test: request URL has no key | 1 |
| M5 | P:340, P:327 | RAG over the KB for unknown faults; cite KB rows; suggest options | Partial | retrieval over past verified incidents (`investigate.py:125-150`); KB absent | RAG over KB + past incidents; citations validated like evidence ids. | Test: cited KB ids must exist; unknown fault gets suggestions, no action | 5 |
| M6 | P:341, P:465 | Can be disabled or self-hosted | Partial | disabled when no keys (`llm.py:130-147`); no self-hosted provider | OpenAI-compatible local endpoint provider (e.g. Ollama); needs RAM (C3). | Provider test with a fake server | 5 |

### A11. Learning loop (P:343-345, P:653)

| ID | Plan | Requirement | Status | Evidence | Work needed | Acceptance criterion | Phase |
|---|---|---|---|---|---|---|---|
| S1 | P:460, P:653 | Learn store: SQLite (Postgres-ready, `DB_URL`) for incidents, actions, outcomes, feedback, KB | Not started | JSONL only (`investigate.py:152-156`, `executor.py:56-60`) | SQLAlchemy-core store; SQLite default; Postgres URL accepted. | Tests on SQLite; schema migration test | 5 |
| S2 | P:653 | Append incidents in dataset A/C format | Not started | not present | Writer from C7 builder. | New rows appear after each incident (test + live run) | 5 |
| S3 | P:610, P:653 | `POST /api/feedback/{incident}`: human confirms/corrects fault → training data | Not started | not present | Token-protected endpoint. | Test: feedback stored and used as the label in exports | 5 |
| S4 | P:270, P:345 | Periodic retraining replaces model files; versioned artifacts | Not started | artifacts carry commit/time/hash (`eternalai/artifacts.py:26-34`), no retraining job | Retraining pipeline writing versioned artifact folders; brain loads a chosen version; never on test data. | Retrain from store produces vN+1 with metadata; brain reload test | 5 |

### A12. Notifications and approvals (P:250, P:612-618, P:652)

| ID | Plan | Requirement | Status | Evidence | Work needed | Acceptance criterion | Phase |
|---|---|---|---|---|---|---|---|
| N1 | P:174, P:464 | Telegram notifications (v1 had them) | Not started | not present | Telegram sender. Needs a bot token and chat id (C4). | Message delivered to a test chat (live, with your bot) | 6 |
| N2 | P:464, P:652 | Slack with interactive Approve/Reject | Not started | not present | Slack app, signed request verification, same `engine.approve` path and approver checks. Needs a workspace (C4). | Approve tap in Slack executes once; replayed/unsigned request refused (tests + live) | 6 |
| N3 | P:250 | PagerDuty | Not started | not present | Events API v2 trigger/resolve. Needs a routing key (C4). | Incident created and resolved in PagerDuty (live) | 6 |
| N4 | P:612-618 | Message format: cause + confidence, signals in words, root + affected, action, verified time, permanent fix | Not started | not present | Formatter shared by all channels. | Snapshot test of the message for a fixture incident | 6 |
| N5 | P:574 | Approver list per user | Not started | any token holder approves (`api.py:51-56`) | Approver list in the rulebook; identity from SSO/Slack/Telegram user id. | Non-listed user refused on every channel (tests) | 6 |

### A13. API, dashboard, configuration (P:591-623)

| ID | Plan | Requirement | Status | Evidence | Work needed | Acceptance criterion | Phase |
|---|---|---|---|---|---|---|---|
| I1 | P:593, P:756 | Dashboard on port 8080; `docker compose up --build` works | Done differently | dashboard 8050, shop on 8080 (`docker-compose.yml:36`, `:91`); build needs `--profile releases` first (`README.md:18-23`) | See D5. | per D5 | 0 |
| I2 | P:595 | Live map green/yellow/red, incident timeline, approvals, mode switch | Done | dashboard (`dashboard/app.py:115-126`, `dashboard/views.py`) | none | existing | - |
| I3 | P:595 | Per-service charts | Partial | map, causes and forecast graphs (`dashboard/app.py:115-126`); no per-service time series | Per-service signal charts. | UI check | 3 |
| I4 | P:595 | "Crash it" / chaos buttons | Done differently | Demo mode starts hidden evaluator runs (`dashboard/demo.py`) | Meets intent for blind demos; visible per-service chaos buttons would let the brain's operator choose the fault, see D6. | per D6 | 0 |
| I5 | P:595 | Stats: detection-to-fix, fix-to-verified | Partial | scorecard (`api.py:183-185`) | Stats panel from incident timelines. | UI test | 5 |
| I6 | P:602-608 | v1 routes `/api/state`, `/api/mode`, `/api/approvals/{id}`, `/api/chaos/...`, `/api/deploy/...`, `/api/traffic`, `/api/registry` | Done differently | `/status`, `/mode`, `/approvals/{id}/approve|reject`, no traffic/registry/deploy (`eternalai/api.py`) | Add `/api/*` aliases with the same auth; `/api/registry` from the driver; `/api/traffic` to loadgen; chaos/deploy per D6. | Route tests | 5 |
| I7 | P:610 | `GET /api/incidents/{id}` (features, class probabilities, root ranking, chosen fix, KB rows), `GET /api/kb/{fault_type}`, `GET /healthz` | Partial | `/incidents/{iid}` (no KB rows), `/health` (`api.py:67`, `:100-106`) | KB rows, `/api/kb`, `/healthz` alias. | Route tests | 4/5 |
| I8 | P:622-623, P:752 | Env vars: RUNTIME, METRICS_SOURCE, LOADGEN_URL, DOCKER_SOCKET, BRAIN_PORT, TICK_SECONDS, MAX_REPLICAS, COOLDOWN_SECONDS, VERIFY_AFTER_SECONDS, MAX_ATTEMPTS, MODE, GEMINI/GROQ_*, TELEGRAM_*, NAMESPACES, POLICY_FILE, MODEL_DIR, UNKNOWN_THRESHOLD, SLACK_*, DB_URL; all thresholds env-overridable | Partial | many settings have no env override, e.g. cooldown, step, verify timing, persistence (`PROJECT_SNAPSHOT.md` §20) | Every setting in `config.py` with env override; plan names accepted (current `ETERNALAI_*` names kept). | Test: each listed variable changes the setting | 1 (rest with each phase) |

### A14. Data (P:349-444)

| ID | Plan | Requirement | Status | Evidence | Work needed | Acceptance criterion | Phase |
|---|---|---|---|---|---|---|---|
| T1 | P:357-361, P:426-437 | Dataset A/B/C files: `train_balanced.csv`, `val_real.csv`, `test_unseen_system_real.csv`, `test_unknown_fault_real.csv`, `root_cause_train_sampled.csv`, B_*/C_* CSVs, `A_rcaeval_case_index.csv`; build scripts | Not started | not present; `data/clean_workbook.py` expects an external workbook (`docs/ARCHITECTURE.md:46`) | **Needs the workbook / CSVs from you (C1).** | Files present with checksums; build scripts regenerate them | 4 |
| T2 | P:403-410, P:424 | Quality audit and balanced-v2 numbers (84.7% balance, 11.2:1, 38.3% empty, 100% / 33% macro-F1, 58% → 54-65%) | Not started | needs T1 | Re-measure; correct the plan text where numbers differ. | Generated audit file | 4 |
| T3 | P:444 | Every external KB row keeps its source; `reviewed_by_team` | Not started | needs T1 | Validation in the KB loader. | Loader test | 4 |
| T4 | P:658 | Add RCAEval telemetry and retrain; never-seen-system score before/after | Partial | RCAEval RE1 experiments with a separate model (`docs/results/rcaeval_re1.md`, `transfer_re1.md`) | Add to dataset-A training; report before/after. | Results file | 4 |

### A15. Evaluation (P:654-655, P:687-701)

| ID | Plan | Requirement | Status | Evidence | Work needed | Acceptance criterion | Phase |
|---|---|---|---|---|---|---|---|
| E1 | P:462, P:707 | Online Boutique and Sock Shop deployed | Not started | own 4-service shop only | Deploy on kind (needs RAM, C3). | Both apps healthy on kind with load | 7 |
| E2 | P:690-691 | Live system evaluated on a never-seen system (Train Ticket) | Not started | RCAEval only | Train Ticket has about 40+ services; RAM (C3). | Results file from live runs | 7 |
| E3 | P:654 | Chaos Mesh: crash_loop, oom_kill, dns_failure, bad_config, packet_loss, resource_exhaustion; ≥ 5 runs per fault | Not started | own evaluator, 9 scenarios (`evaluator/scenarios.py:16-26`) | Chaos Mesh on kind; experiments as YAML; evaluator keeps the truth. | ≥ 5 logged runs per fault | 7 |
| E4 | P:655, P:697 | Part C: every candidate fix on every fault, ≥ 4-5 runs; `C_experiment_matrix.csv` → measured | Not started | v1 measured one fix per fault vs no action | Experiment driver over fault x fix. | Matrix status measured for every pair | 7 |
| E5 | P:97, P:708 | Memory leak with vs without: plan says 0/5 crashes 0.2% vs 3/3 crashed 23.9% | Conflicts | v1 measured autopilot 11.2% vs no action 0.4%, no crash in the window (`docs/results/benchmark.md:68-72`) | Re-run with vs without (a leak that does crash within the window, and the current one); write the measured result into the plan. | Results file; plan text matches it | 7 |
| E6 | P:95-106 | Other prototype claims (disk, error spike, bad deploy, surge, crash, slow service, CPU; detection 3.9-7.4 s / 16.6 s) | Partial | v1 measured on this system: disk 0.0% vs 35.9%, error spike 25.2% vs 51.5%, bad deploy 20.0% vs 33.5%, crash 45.9% vs 71.8%, latency 8.1% vs 0.0% (`docs/results/benchmark.md:23-40`); **traffic surge: autopilot 12.68% vs no action 0.00%** (`benchmark.md:88-92`), the opposite of the plan's "0% vs 12.0%"; cpu_burn 37.51% vs 62.60% with a different injection (`benchmark.md:83-87`) | Replace the plan's table with measured values and their conditions. Scale-ahead (F2) then re-measured. | Plan §4 table states only measured numbers with source | 7 |
| E7 | P:695 | False alarms per day from a 24 h healthy run vs fixed thresholds | Not started | CV estimate 1.1 per 100 healthy service-minutes (`docs/results/models_cv_v2.md`); idle incidents in rehearsals | 24 h idle run (after D7 fix) with both detectors. | Results file with alarms/day, measured | 7 |
| E8 | P:699 | ≥ 5 repeats; median and range | Partial | v1: 5 seeds; v2: 3 seeds (`docs/results/benchmark_v2.md`) | New benchmark runs use ≥ 5 seeds and report median and range. | Results files | 7 |
| E9 | - | Re-run scenarios affected by the new policy; every quoted number states policy and system | Not started | affected: v2 autopilot bad_deploy and memory_leak (6 runs) (analysis on `hardening`, 2026-10-20) | Re-run under the new policy; label old numbers "benchmark-system-v2 policy". | README/docs numbers each carry policy + system | 7 |

### A16. Tests and engineering rules (P:745-756)

| ID | Plan | Requirement | Status | Evidence | Work needed | Acceptance criterion | Phase |
|---|---|---|---|---|---|---|---|
| Q1 | P:751 | Every action through the rulebook, logged, verified | Partial | policy + audit + verify (`engine.py:341-416`); no autopilot path test | Full-path tests (on `hardening`, `480e15c`) + rulebook. | Test over every runbook x service | 1 |
| Q2 | request | Tests for `verify.py`, `rca.py`, `collector.py`, `api.py`, `investigate.py` | Not started | no direct tests (`PROJECT_SNAPSHOT.md` §19); `collector.py` covered on `hardening` (`8d48de5`) | New test modules. | Each module has a test file; suite passes | 1 |
| Q3 | P:755 | Python 3.12, scikit-learn + joblib | Done | `FROM python:3.12-slim` in all Dockerfiles; joblib artifacts | none | existing | - |
| Q4 | request | Prometheus query errors do not lose the tick | Not started | `collector.py:38-49`. On `hardening` (`8d48de5`): fixed | Bring in. | tests in `tests/test_collector.py` | 1 |

### A17. Demo script (P:705-714)

| ID | Plan | Requirement | Status | Evidence | Work needed | Acceptance criterion | Phase |
|---|---|---|---|---|---|---|---|
| G1 | P:707 | Online Boutique (or demo shop) under load, autopilot | Done (demo shop) | `docs/DEMO.md` | Online Boutique variant after E1. | rehearsal record | 7 |
| G2 | P:708 | Memory leak → Predicted → classifier → restart with helper → verified; Watch-only run crashes for contrast | Partial | predicted never fired live; no-action leak does not crash (`benchmark.md:68-72`) | After F1/F3/E5. | rehearsal record | 7 |
| G3 | P:709 | Bad deploy → rollback waits for approval → approve on Slack/Telegram | Partial | rollback auto-executes at `c587d20`; dashboard approval only | After P2, N1/N2. | rehearsal record | 6 |
| G4 | P:710 | Surge → forecast → scale out → scale in | Not started | F2 | After F2. | rehearsal record on kind | 7 |
| G5 | P:711-712 | Crash → restart; unseen pattern → UNKNOWN + LLM suggestions | Partial | crash and abstain done; no LLM suggestions for unknown (M5) | After M5. | rehearsal record | 5 |
| G6 | P:713 | Show the new training row created by Learn | Not started | S2 | After S2. | rehearsal record | 5 |
| G7 | P:714, P:718-726 | Honest numbers slide (§20) with measured values | Partial | `PROJECT_SNAPSHOT.md` §23 | Update §20 of the plan with measured values. | Plan §20 matches results files | 7 |

---

## B. Plan layout → existing modules (no folders renamed)

| Plan (P:664-683) | This repository |
|---|---|
| `brain/main.py` | `eternalai/api.py` (+ `dashboard/app.py` for the UI) |
| `brain/engine.py`, `config.py`, `policy.py` | `eternalai/engine.py`, `config.py`, `policy.py` (+ new rulebook file `config/policy.yaml`, Phase 1) |
| `brain/sources/prometheus.py` | `eternalai/collector.py` (`Prom`) |
| `brain/sources/k8s_state.py` | new `eternalai/sources/k8s_state.py` (Phase 2) |
| `brain/drivers/docker.py`, `k8s.py`, `local.py` | `eternalai/executor.py` becomes `DockerDriver`; new `eternalai/drivers/` package (Phase 2) |
| `brain/detect.py`, `predict.py`, `diagnose.py` | `eternalai/detect.py`, `forecast.py`, `rca.py` + `classify.py` |
| `brain/features.py` | `eternalai/features/window.py` (live) + new dataset-schema builder (Phase 4) |
| `brain/models/`, `artifacts/*.joblib` | `models/artifacts/`, `eternalai/artifacts.py` |
| `brain/kb/` | new `eternalai/kb/` (loader + ranking) and `data/kb/` (CSV files) (Phase 4) |
| `brain/learn.py`, `store.py` | new `eternalai/learn.py`, `eternalai/store.py` (Phase 5) |
| `brain/explain.py` | `eternalai/llm.py` + `eternalai/investigate.py` |
| `brain/notify.py` | new `eternalai/notify/` (Phase 6) |
| `brain/static/` | `dashboard/` (Dash) |
| `training/` | `models/train_models.py`, `models/eval_*.py` |
| `chaos/chaos-mesh/*.yaml` | new `deploy/chaos-mesh/` (Phase 7); Docker faults stay in `evaluator/` |
| `deploy/helm`, `rbac`, `kind-cluster.yaml`, `online-boutique/` | new `deploy/` (Phase 2, 7) |
| `services/` | `app/` + `loadgen/` |
| `bench/` | `evaluator/` + `scripts/run_benchmark.py` + `results/` |

---

## C. Inputs I need from you (blocking)

| ID | Needed for | What |
|---|---|---|
| C1 | Phase 4 (C1-C10, R2, X1-X2, T1-T4) | The dataset A/B/C workbook or the v2 CSVs listed at P:426-437, and their path. Without them, the 15-type classifier, KB and outcome ranking cannot be built from the plan's data. |
| C2 | Phase 2 | Permission to download `kind` and `helm` (not installed; `kubectl` is present from Docker Desktop), **or** turn on Docker Desktop's Kubernetes. |
| C3 | Phases 2, 3, 7 | RAM: 15.7 GB total, 4.5 GB free at the time of writing. The earlier forecast check already stopped on low memory (`docs/FORECAST_CHECK.md`). Online Boutique + Sock Shop + Chaos Mesh + kube-prometheus-stack at once is unlikely to fit; Train Ticket (40+ services) very unlikely. Options: run one app at a time, or a bigger machine / cloud cluster from you. |
| C4 | Phase 6 | Slack workspace + app (bot token, signing secret), Telegram bot token + chat id, PagerDuty routing key, all placed by you in `.env` (I will not read it). |
| C5 | H6 | An OIDC identity provider for dashboard SSO, or approval to run a local one (e.g. Dex) on kind for the demo. |
| C6 | H8 | Cloud read-only identity (IRSA / Workload Identity) needs a cloud account. Without one, this row can only be documented, not run. |
| C7 | M3 | Live LLM checks use the Gemini key already in `.env` (I will not read it; scripts read it from the environment). |

## D. Decisions I need from you

| ID | Question | My suggestion |
|---|---|---|
| D1 | `plan-complete` starts at `c587d20` and does not contain the 4 `hardening` commits that already do several Phase 1 items. | Merge `hardening` into `plan-complete` as the first Phase 1 step (no rebase, no history rewrite). |
| D2 | Protected services: the plan says "always need approval" (P:582); `hardening` made them observe-only. | Follow the plan: protected → needs approval, in every mode. |
| D3 | Defaults: the plan says defaults as §6.3 (cooldown 40 s, verify 16 s + 30 s grace, 2 attempts, autopilot auto for low/medium per v1, or `[low]` per the YAML example). Changing current defaults (cooldown 90 s, `low`+`medium`) changes benchmarked behaviour. | Put both in the rulebook. Ship the plan's values as the default file, keep a `benchmark-v2.yaml` that reproduces the measured system, and label every number with the file it ran under. |
| D4 | The plan file is outside the repository. "Update the plan text to match measured results" needs either permission to edit `C:\Users\premy\OneDrive\Desktop\ETERNALAI.md`, or a tracked copy. | Commit a copy as `docs/ETERNALAI_PLAN.md` and correct it there; the Desktop file stays untouched unless you say so. |
| D5 | Dashboard port 8080 (plan) is the shop's port here. | Keep the shop on 8080 and the dashboard on 8050; record it as "done differently". |
| D6 | Visible chaos/deploy buttons and `/api/chaos`, `/api/deploy` let the operator pick the fault, which the blind evaluator was built to avoid. | Add them only behind a `DEMO_CHAOS=1` flag, token-protected, routed through the evaluator so the truth stays private. |
| D7 | Not in the build list but in the plan text: pause rollout, change limits, patch HPA, cordon node, create Job (P:504). | Add as drivers' "not supported" with a test, unless you want them built. |
| D8 | `LocalDriver` / `run_local.py` (v1 had a local-process runtime, P:158). | Build `LocalDriver` behind the same interface (small), since rule P:747 names it. |

## E. Scale

Phases 2-7 need a cluster, external accounts and the dataset. The hackathon is on 24-25 October 2026. Finishing every row before then is unlikely; Phase 1 (safety) and Phase 2 (Kubernetes driver, Helm, RBAC on kind) are the items with the highest plan priority (P:646-656).
