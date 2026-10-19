# Telemetry condition of every data batch, and what it means for the retrained models

Read-only analysis (2026-10-18). Sources: run files in `data/runs` (`t_inject`), `docs/results/stage0_telemetry.md`, `docs/postmortems/surge-false-alarm-diagnosis.md` (finding 4, H7), git log of `docker-compose.yml`.

| batch | when (UTC) | apps' exporter | Jaeger collector | evidence |
|---|---|---|---|---|
| 72 original training runs (seeds 1000-1707) | first injection 2026-10-16 19:09, last 2026-10-17 11:13 | ON (`OTEL_SDK_DISABLED: "false"` in compose since the first commit) | **not recorded; probably alive, unverified** | The Jaeger container that was inspected was created 13:52Z on 17 Oct, after the last training run (a recreate, compose memory limits commit 19:21 IST). The earlier instance is gone, so its state during training cannot be shown. No OOM evidence exists for it either way. |
| v1 benchmark (seeds 100-148) | from about 15:50Z on 2026-10-17 | ON | **dead** (OOM-killed 15:15:34Z) | `OOMKilled=true`, exit 137 |
| Stage 0 (non-benchmark) | 2026-10-18 | T1 ON, T2 ON, T3 OFF | T1 alive (capped store), T2 dead, T3 not started | `stage0_telemetry.md` |
| 34 fresh training runs (seeds 1800-1842) | 2026-10-18 | OFF (`OTEL_SDK_DISABLED=true`) | not started | `scripts/v2_stack.ps1`, stage 1 logs |
| v2 evaluation (seeds 200-318) | 2026-10-18 onward | OFF | not started | same script |

## What this means for the retrained models

The retrained models mix conditions: 72 runs with the exporter on (collector probably reachable) and 34 with the exporter off. The condition is not a model input and cross-validation folds mix both, so the CV numbers cannot separate its effect. What limits the damage: the v2 memory features are relative to the run's own recent past (`mem_rel_growth`), not absolute levels, so a constant memory offset from the exporter mostly drops out. CPU, latency and error features may still differ slightly between the two conditions; that was not measured. The v2 evaluation uses the condition of the newer 34 runs (T3), and the older 72 runs were made with an exporter that the apps no longer run. This is a limitation, stated in the model card.

## HYPOTHESIS (not proven): the original training had a reachable collector, the v1 benchmark a dead one, and that explains v1's memory shift

If the training-time Jaeger was alive (unverified), then training and benchmark differed in exactly this respect. Support, all indirect:
- Stage 0, same code and same surge intensity (40), two runs per condition: web surge increment **T1 (Jaeger alive) 3.1 and 3.0 MB; T2 (Jaeger dead, the v1 benchmark condition) 9.7 and 9.7 MB; T3 (exporter off) 0.5 and 0.6 MB.** Inventory: 2.5/3.1, 9.4/9.9, 0.5/0.5 MB.
- v1 training surges showed about +1 MB (surge diagnosis data), closer to T1 and T3 than to T2.
- The size of the rise scales with request rate (busy `web` and `inventory` rise, idle services do not), which is what a filling exporter queue would do (H7).

Against or limiting: two runs per condition; the training-time collector state is not recorded; other differences between training and benchmark (container age, prior load, high-water marks on `inventory`) were not separated from the exporter. This stays a hypothesis; Stage 0 is a diagnostic, not a test of H7 with a controlled mechanism check (no span-queue size was measured).
