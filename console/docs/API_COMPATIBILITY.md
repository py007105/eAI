# API compatibility: console contract

Compared `eternalai/api.py` at `demo-stable-1` (peeled commit `49155ea043db204623e12ebd703129b2eb9da143`) and `origin/plan-complete` (`7cc615a48d8378dcf781b4f7e3deb428c16654c7`). The selected GET handlers are present at both refs, observational, and do not require approval-token headers.

| Route (browser path)  | Backend response                                                                                                       | Optional data / UI mapping                                                                                                                                 |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /health`         | `{ok: boolean}`                                                                                                        | Connection check only. Not used alone to claim telemetry is live.                                                                                          |
| `GET /status`         | Object with `mode`, `kill_switch`, `protected_services`, `policy`, `open_incidents`, `calibration`, model/error fields | Fields are shown only when returned and schema-valid. Probability/confidence only when `calibration.show_probability === true`.                            |
| `GET /services`       | `{services: serviceName -> snapshot, topology: caller -> callees, depfail: edge -> value}`                             | Snapshots may include `features`, `score`, `anomalous`, and `state`; missing values remain unknown. Topology is dependency data, not traffic.              |
| `GET /incidents`      | Array of public incident records                                                                                       | Records include identifiers, opened time, status, services, kind and may include evidence, actions, verification, timeline, report, diagnosis, confidence. |
| `GET /incidents/{id}` | One public incident record or 404                                                                                      | The client currently fetches the common incident list and opens the selected record from that response.                                                    |
| `GET /approvals`      | Array of pending approval details                                                                                      | Items may include `incident_id`, `service`, `runbook_id`, `risk`, `reason`, `cause`, `report`; no expiry field. No action controls are provided.           |
| `GET /audit`          | Most recent bounded records (last 100)                                                                                 | No query or global-total contract; UI shows only returned records.                                                                                         |

The browser also uses these observational routes, mapped from `eternalai/api.py` and `evaluator/main.py`:

| Route | Mapping |
| --- | --- |
| `GET /scorecard` | `{runs, by_scenario}`; independent 10 s polling, 5 s timeout, no overlapping requests; missing numeric fields stay missing |
| `GET /challenge/{id}/status` | Operator-provided run ID; validates matching `run_id` and `running/finished/failed` state; no ground truth |
| `GET /challenge/{id}/reveal` | Offered only after finished status; backend enforces scoring completion; validates matching `truth.run_id` and `score` object |

The new evaluator reads are manual, except scorecard polling. Editing the run ID aborts a pending request and clears the previous result. Error objects returned as HTTP 200 by the status proxy are rejected. No selected route accepts query parameters. `/learn/*` and `/kb/*` are excluded because they are not common to both refs. Write routes, including approvals, mode, kill switch, reset, feedback, and challenge actions, are never called.

Browser requests use relative `/api/...` URLs. Vite's development and preview proxies read `VITE_API_TARGET` server-side, default to `http://127.0.0.1:8000`, and strip the `/api` prefix. A deployed static build requires a same-origin reverse proxy; `vite preview` is not production hosting.

Connection freshness requires schema-valid responses from /status, /services, /incidents, /approvals, and /audit within six seconds. A failed endpoint immediately loses its current values, even if its previous success was recent. Mixed endpoint failures are partial; all failed endpoints are disconnected. Retained values after six seconds are historical and are not shown as current. Confidence additionally requires a fresh, successful status response granting permission.

## Recovery comparison and presentation states

Incident `before` and `after` use `checkout_success`, `error_ratio` (ratios displayed as percentages), and `p95_s` (seconds displayed as milliseconds). Verification uses `outcome`, `probes`, and `success_rate`. The backend measures snapshots around the action/verification window; missing values are never substituted with zero. A partial/unresolved verification does not contribute a verified-recovery duration to the chart.

Landing KPIs, Live Incident, Continuous Watch, integrations, incident charts and 3D incident highlights all gate values independently by endpoint success and freshness. Chart buffers remain explicitly historical when service data is unavailable. The focus toggle only changes layout; incident selection remains live-polling and never pauses or mutates the engine.
