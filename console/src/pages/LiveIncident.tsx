import { isRecord, numberValue, serviceState, textValue, type UnknownRecord } from "../lib/api";
import { useTelemetry } from "../lib/useTelemetry";
import {
  approverChannel,
  deriveStages,
  lastAction,
  newestActive,
  recentClosed,
  type Stage,
} from "../lib/pipeline";
import ReportProvider from "../components/ReportProvider";
import { Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const NR = "Not reported";
const clock = (t?: number) =>
  t === undefined ? "" : new Date(t * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });

export function ApproverBadge({ value }: { value: unknown }) {
  const a = approverChannel(value);
  const tone =
    a.channel === "Telegram" ? "cyan" : a.channel === "Dashboard" ? "green" : a.channel === "Autopilot" ? "amber" : "";
  if (a.channel === "Not reported") return <span className="muted">{NR}</span>;
  return (
    <span className={`badge ${tone}`} title={a.raw}>
      {a.channel}
      {a.id ? ` · ${a.id}` : ""}
    </span>
  );
}

function StageCard({ s }: { s: Stage }) {
  return (
    <li className={`stage stage-${s.status}`} aria-current={s.status === "current" ? "step" : undefined}>
      <div className="stage-dot" aria-hidden="true" />
      <div className="stage-label">{s.label}</div>
      <div className="stage-detail">
        {s.status === "skipped" || s.status === "failed"
          ? s.detail ?? s.status
          : s.status === "current"
            ? "in progress"
            : s.status === "pending"
              ? "waiting"
              : s.detail ?? ""}
      </div>
      <div className="stage-time tabular">
        {s.at !== undefined ? `${clock(s.at)}${s.elapsed !== undefined ? ` · +${s.elapsed.toFixed(1)} s` : ""}` : ""}
      </div>
    </li>
  );
}

function ForecastChart({ inc }: { inc: UnknownRecord }) {
  const list = Array.isArray(inc.forecasts) ? inc.forecasts.filter(isRecord) : [];
  const f = list[list.length - 1];
  const share = numberValue(f?.share_of_limit_now);
  const eta = numberValue(f?.eta_s);
  if (!f || share === undefined || eta === undefined) return null;
  const data = [
    { s: 0, pct: share * 100 },
    { s: eta, pct: 100 },
  ];
  return (
    <section className="panel">
      <div className="panel-title">
        <h2>Resource forecast</h2>
        <small>
          From the incident's forecast fields: {textValue(f.resource) ?? "resource"} at {(share * 100).toFixed(0)}% of its
          limit, projected to reach it in {eta.toFixed(0)} s (window {numberValue(f.eta_earliest_s)?.toFixed(0) ?? "?"}–
          {numberValue(f.eta_latest_s)?.toFixed(0) ?? "?"} s)
        </small>
      </div>
      <div style={{ height: 180 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <XAxis dataKey="s" type="number" stroke="#8d99a6" tickFormatter={(v) => `${v}s`} />
            <YAxis domain={[0, 110]} stroke="#8d99a6" tickFormatter={(v) => `${v}%`} />
            <ReferenceLine y={100} stroke="#e47d7d" strokeDasharray="4 4" />
            <Tooltip contentStyle={{ background: "#11161c", border: "1px solid #252d36" }} />
            <Line dataKey="pct" stroke="#e7bd69" strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

export function PipelineView({ inc, title }: { inc: UnknownRecord; title: string }) {
  const stages = deriveStages(inc);
  const act = lastAction(inc);
  const ranking = Array.isArray(inc.ranking) ? inc.ranking.filter(isRecord) : [];
  const root =
    textValue(ranking[0]?.service) ?? (Array.isArray(inc.services) ? textValue(inc.services[0]) : undefined);
  const evidence = Array.isArray(inc.evidence) ? inc.evidence.filter(isRecord) : [];
  const report = isRecord(inc.report) ? inc.report : undefined;
  const actor = textValue(act?.approved_by) ?? (act?.executed === true && textValue(act?.verdict) === "execute" ? "autopilot" : undefined);
  return (
    <>
      <section className="panel live-head">
        <div className="panel-title">
          <div>
            <h2>{title}</h2>
            <small className="tabular">
              {textValue(inc.id) ?? NR} · opened {clock(numberValue(inc.opened_t))} · status {textValue(inc.status) ?? NR}
            </small>
          </div>
          <span className={`badge ${textValue(inc.status) === "recovered" ? "green" : "amber"}`}>
            {textValue(inc.status) ?? NR}
          </span>
        </div>
        <ol className="pipeline" aria-label="Incident pipeline">
          {stages.map((s) => (
            <StageCard key={s.key} s={s} />
          ))}
        </ol>
      </section>
      <div className="live-grid">
        <section className="panel">
          <div className="panel-title">
            <h2>Decision</h2>
            <small>From the incident record</small>
          </div>
          <dl className="detail-list">
            <dt>Root-cause service</dt>
            <dd className={root ? "root-service" : "muted"}>{root ?? NR}</dd>
            <dt>Likely cause</dt>
            <dd>{textValue(inc.likely_cause) ?? NR}</dd>
            <dt>Runbook</dt>
            <dd>{textValue(act?.runbook_id) ?? NR}</dd>
            <dt>Risk</dt>
            <dd>{textValue(act?.risk) ?? NR}</dd>
            <dt>Policy reason</dt>
            <dd>{textValue(act?.reason) ?? NR}</dd>
            <dt>Approved / executed by</dt>
            <dd>
              <ApproverBadge value={actor} />
            </dd>
          </dl>
        </section>
        <section className="panel">
          <div className="panel-title">
            <h2>Report</h2>
            <small>Plain-English summary returned with the incident</small>
          </div>
          <p className="report-text">{textValue(report?.summary) ?? NR}</p>
          <ReportProvider meta={inc.report_meta} />
          <div className="panel-title" style={{ marginTop: 14 }}>
            <h2>Evidence</h2>
            <small>{evidence.length} items</small>
          </div>
          {evidence.length ? (
            <ul className="evidence-list">
              {evidence.slice(0, 4).map((e, i) => (
                <li key={i}>
                  <span className="badge">{textValue(e.tool) ?? "evidence"}</span> {textValue(e.summary) ?? NR}
                </li>
              ))}
            </ul>
          ) : (
            <div className="muted">{NR}</div>
          )}
        </section>
      </div>
      <ForecastChart inc={inc} />
    </>
  );
}

export default function LiveIncident() {
  const { data, connection } = useTelemetry();
  const live = connection === "live" || connection === "partial";
  const incidents = data.incidents.value;
  const svcPayload = data.services.value;
  const services = isRecord(svcPayload) && isRecord(svcPayload.services) ? svcPayload.services : undefined;
  const active = live ? newestActive(incidents) : undefined;
  const recent = live && !active ? recentClosed(incidents, Date.now() / 1000) : undefined;
  if (!live || !incidents || !services)
    return (
      <div className="empty">
        <strong>Live incident view unavailable</strong>The API is not connected; nothing is shown as live.
      </div>
    );
  if (active) return <PipelineView inc={active} title="Live incident" />;
  const names = Object.keys(services);
  const states = names.map((n) => [n, serviceState(services[n])] as const);
  const allHealthy = states.length > 0 && states.every(([, s]) => s === "ok");
  return (
    <>
      <section className="panel watching">
        <div className="panel-title">
          <div>
            <h2>{allHealthy ? "All services healthy · watching" : "No open incident · watching"}</h2>
            <small>Live service scores from /services, refreshed every 2 s</small>
          </div>
          <span className={`badge ${allHealthy ? "green" : "amber"}`}>{allHealthy ? "healthy" : "watching"}</span>
        </div>
        <div className="watch-grid">
          {states.map(([n, s]) => {
            const r = isRecord(services[n]) ? (services[n] as UnknownRecord) : undefined;
            const score = numberValue(r?.score);
            return (
              <div key={n} className={`watch-card watch-${s}`}>
                <div className="watch-name">{n}</div>
                <div className="watch-score tabular">{score !== undefined ? score.toFixed(3) : NR}</div>
                <div className="watch-state">
                  {s === "ok" ? "no anomaly reported" : s === "anomaly" ? "anomaly reported" : s === "down" ? "not running" : NR}
                </div>
              </div>
            );
          })}
        </div>
      </section>
      {recent && <PipelineView inc={recent} title="Last incident (closed)" />}
    </>
  );
}
