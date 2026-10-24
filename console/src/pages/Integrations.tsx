import { isRecord, textValue, type UnknownRecord } from "../lib/api";
import { actionsByChannel } from "../lib/charts";
import { approverChannel, type Channel } from "../lib/pipeline";
import { useTelemetry } from "../lib/useTelemetry";

const NR = "Not reported";

function Source({ path }: { path: string }) {
  return <div className="source-label">Source: {path}</div>;
}

export default function Integrations() {
  const { data, connection } = useTelemetry();
  const live = connection === "live" || connection === "partial";
  const status = isRecord(data.status.value) ? (data.status.value as UnknownRecord) : undefined;
  const policy = status && isRecord(status.policy) ? (status.policy as UnknownRecord) : undefined;
  const runbookRisk = policy && isRecord(policy.runbook_risk) ? (policy.runbook_risk as UnknownRecord) : undefined;
  const byChannel = live ? actionsByChannel(data.audit.value) : undefined;
  const incidents = Array.isArray(data.incidents.value) ? data.incidents.value.filter(isRecord) : [];
  const approvedBy: Record<string, number> = {};
  for (const inc of incidents)
    for (const a of Array.isArray(inc.actions) ? inc.actions.filter(isRecord) : []) {
      const who = textValue(a.approved_by);
      if (who) {
        const c: Channel = approverChannel(who).channel;
        approvedBy[c] = (approvedBy[c] ?? 0) + 1;
      }
    }
  return (
    <div className="integrations">
      <section className="panel">
        <div className="panel-title">
          <h2>Runtime · Docker Compose</h2>
          <span className="badge cyan">live runtime</span>
        </div>
        <p>
          The services, the evaluator and the EternalAI engine run as containers defined in the repository's Compose file.
          Actions go through an allow-listed set of runbooks; their risk comes from the loaded rulebook.
        </p>
        <h3 className="sub-head">Allow-listed runbooks (live, from /status → policy.runbook_risk)</h3>
        {live && runbookRisk ? (
          <div className="chip-row">
            {Object.entries(runbookRisk).map(([rb, risk]) => (
              <span key={rb} className={`chip risk-${String(risk)}`}>
                {rb} <b>{String(risk)}</b>
              </span>
            ))}
          </div>
        ) : (
          <div className="muted">{NR}</div>
        )}
        <Source path="docker-compose.yml; rulebook eternalai/rulebooks/default.yaml (via /status)" />
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Telemetry · Prometheus</h2>
        </div>
        <p>Prometheus scrapes the services every 2 s; the engine reads it and this console polls the API every 2 s.</p>
        <Source path="telemetry/prometheus.yml (scrape_interval: 2s)" />
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Telegram · separate bot via REST API</h2>
        </div>
        <p>
          A separate process polls the REST API and posts approve / reject requests to an allowed Telegram account. It
          calls the same approve endpoint as the dashboard; this console does not send anything.
        </p>
        <h3 className="sub-head">Executed actions by channel (derived from audit records)</h3>
        {byChannel ? (
          <div className="chip-row tabular">
            {(Object.entries(byChannel) as [Channel, number][])
              .filter(([c]) => c !== "Not reported")
              .map(([c, n]) => (
                <span key={c} className="chip">
                  {c} <b>{n}</b>
                </span>
              ))}
          </div>
        ) : (
          <div className="muted">{NR}</div>
        )}
        <h3 className="sub-head">Approvals in returned incidents (derived from incident approver fields)</h3>
        {live ? (
          Object.keys(approvedBy).length ? (
            <div className="chip-row tabular">
              {Object.entries(approvedBy).map(([c, n]) => (
                <span key={c} className="chip">
                  {c} <b>{n}</b>
                </span>
              ))}
            </div>
          ) : (
            <div className="muted">No approved actions in the returned incidents.</div>
          )
        ) : (
          <div className="muted">{NR}</div>
        )}
        <Source path="docs/results/dry_run_1_20261024-1948.md, docs/results/dry_run_2_20261024-2236.md (real taps verified)" />
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>LLM reports</h2>
        </div>
        <p>
          LLM reports: Gemini, evidence ids validated by the backend; deterministic template fallback; the LLM never acts.
          Each incident shows its report provider exactly as the API reports it.
        </p>
        <Source path="eternalai/llm.py (validate(): evidence ids must exist; template_report fallback)" />
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Kubernetes</h2>
          <span className="badge">validated offline</span>
        </div>
        <p>
          Validated offline: Helm lint+render, 26/26 resources schema-valid, 57 tests; not run on a live cluster.
        </p>
        <Source path="docs/results/k8s_offline_validation.md" />
      </section>
    </div>
  );
}
