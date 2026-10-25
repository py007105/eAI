import { useState } from "react";
import { ArrowRight, Check, X as XIcon } from "lucide-react";
import { isRecord, numberValue, serviceState, textValue, type UnknownRecord } from "../lib/api";
import { useCurrentTelemetry } from "../lib/useTelemetry";
import {
  ACTIVE_STATUSES,
  approverChannel,
  deriveStages,
  lastAction,
  newestActive,
  recentClosed,
  type Stage,
} from "../lib/pipeline";
import EvaluatorRun from "../components/EvaluatorRun";
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
    </span>
  );
}

function StageCard({ s, selected, onSelect }: { s: Stage; selected: boolean; onSelect: () => void }) {
  return (
    <li className={`stage stage-${s.status}`} aria-current={s.status === "current" ? "step" : undefined}>
      <button className="stage-select" aria-label={`Inspect ${s.label}`} aria-pressed={selected} onClick={onSelect}>
      <div className="stage-dot" aria-hidden="true">
        {s.status === "done" ? <Check size={15} strokeWidth={3} /> : s.status === "failed" ? <XIcon size={14} strokeWidth={3} color="#ffffff" /> : null}
      </div>
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
      </button>
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
            <XAxis dataKey="s" type="number" stroke="#66706b" tickFormatter={(v) => `${v}s`} />
            <YAxis domain={[0, 110]} stroke="#66706b" tickFormatter={(v) => `${v}%`} />
            <ReferenceLine y={100} stroke="#f04438" strokeDasharray="4 4" />
            <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #e6eae8", borderRadius: 10 }} />
            <Line dataKey="pct" stroke="#f79009" strokeWidth={2.4} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

export function PipelineView({ inc, title }: { inc: UnknownRecord; title: string }) {
  const stages = deriveStages(inc);
  const [selectedStage, setSelectedStage] = useState<string>();
  const detail = stages.find((s) => s.key === selectedStage);
  const act = lastAction(inc);
  const ranking = Array.isArray(inc.ranking) ? inc.ranking.filter(isRecord) : [];
  const root = inc.abstained === true ? undefined : textValue(ranking[0]?.service);
  const evidence = Array.isArray(inc.evidence) ? inc.evidence.filter(isRecord) : [];
  const report = isRecord(inc.report) ? inc.report : undefined;
  const actor = textValue(act?.approved_by) ?? (act?.executed === true && textValue(act?.verdict) === "execute" ? "autopilot" : undefined);
  return (
    <>
      <section className={`panel live-head ${ACTIVE_STATUSES.includes(textValue(inc.status) ?? "") ? "beam" : ""}`}>
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
            <StageCard key={s.key} s={s} selected={selectedStage === s.key} onSelect={() => setSelectedStage(selectedStage === s.key ? undefined : s.key)} />
          ))}
        </ol>
        {detail && <div className="stage-inspector" aria-live="polite">
          <strong>{detail.label} · {detail.status}</strong>
          <span>{detail.detail ?? "No additional detail reported"}</span>
          <span>{detail.at !== undefined ? `Recorded at ${clock(detail.at)}` : "Time not reported"}</span>
        </div>}
        <div className="pipeline-foot">
          <span>Select a stage to inspect its evidence.</span>
          {textValue(inc.id) && <a className="text-link" href={`/console/incidents/${encodeURIComponent(String(inc.id))}`}>Full investigation <ArrowRight size={14} /></a>}
        </div>
      </section>
      <div className="live-grid">
        <section className="panel">
          <div className="panel-title">
            <h2>Decision</h2>
            <small>From the incident record</small>
          </div>
          <dl className="detail-list">
            {[
              ["Leading candidate", inc.abstained === true ? "Abstained · insufficient evidence" : root ?? NR],
              ["Likely cause", textValue(inc.likely_cause) ?? NR],
              ["Runbook", textValue(act?.runbook_id) ?? NR],
              ["Risk", textValue(act?.risk) ?? NR],
              ["Policy reason", textValue(act?.reason) ?? NR],
            ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
            <div><dt>Approved / executed by</dt><dd><ApproverBadge value={actor} /></dd></div>
          </dl>
        </section>
        <section className="panel">
          <div className="panel-title">
            <h2>Report</h2>
            <small>Plain-English summary returned with the incident</small>
          </div>
          <p className="report-text">{textValue(report?.summary) ?? NR}</p>
          <ReportProvider meta={inc.report_meta} />
          <details className="evidence-disclosure">
            <summary>Evidence <span className="badge">{evidence.length} items</span></summary>
            {evidence.length ? <ul className="evidence-list">
              {evidence.map((e, i) => <li key={textValue(e.id) ?? i}>
                <span className="badge">{textValue(e.tool) ?? "evidence"}</span> {textValue(e.summary) ?? NR}
              </li>)}
            </ul> : <p className="muted">{NR}</p>}
          </details>
        </section>
      </div>
      <RecoveryProof inc={inc} />
      <ForecastChart inc={inc} />
    </>
  );
}

export function RecoveryProof({ inc }: { inc: UnknownRecord }) {
  const before = isRecord(inc.before) ? inc.before : undefined;
  const after = isRecord(inc.after) ? inc.after : undefined;
  const verification = isRecord(inc.verification) ? inc.verification : undefined;
  const format = (value: unknown, percent: boolean) => {
    const n = numberValue(value);
    return n === undefined ? NR : percent ? `${(n * 100).toFixed(1)}%` : `${(n * 1000).toFixed(0)} ms`;
  };
  const outcome = textValue(verification?.outcome);
  return <section className="panel recovery-proof">
    <div className="panel-title"><div><h2>Recovery evidence</h2><small>Measured before the action and after verification</small></div>
      <span className={`badge ${outcome === "recovered" ? "green" : outcome ? "amber" : ""}`}>{outcome ?? "Awaiting verification"}</span>
    </div>
    <div className="table-wrap"><table className="data-table tabular">
      <thead><tr><th>Measurement</th><th>Before</th><th>After</th></tr></thead>
      <tbody>{([ ["Checkout success", "checkout_success", true], ["Request errors", "error_ratio", true], ["Web p95 latency", "p95_s", false] ] as const).map(([label, key, percent]) =>
        <tr key={key}><td>{label}</td><td>{format(before?.[key], percent)}</td><td>{format(after?.[key], percent)}</td></tr>
      )}</tbody>
    </table></div>
    <p className="proof-note">Verification probes: <strong>{numberValue(verification?.probes) ?? NR}</strong> · Passed within latency budget: <strong>{format(verification?.success_rate, true)}</strong></p>
  </section>;
}

export default function LiveIncident() {
  const { data } = useCurrentTelemetry();
  const [pinned, setPinned] = useState("");
  const incidents = data.incidents.value;
  const rows = Array.isArray(incidents) ? incidents.filter(isRecord) : undefined;
  const svcPayload = data.services.value;
  const services = isRecord(svcPayload) && isRecord(svcPayload.services) ? svcPayload.services : undefined;
  const active = newestActive(incidents);
  const recent = !active ? recentClosed(incidents, Date.now() / 1000) : undefined;
  const selected = pinned ? rows?.find((i) => textValue(i.id) === pinned) : active ?? recent;
  const names = Object.keys(services ?? {});
  const states = names.map((n) => [n, serviceState(services?.[n])] as const);
  const allHealthy = states.length > 0 && states.every(([, s]) => s === "ok");
  return <>
    <div className="incident-toolbar">
      <div><span className="eyebrow">INCIDENT MONITOR</span><p>{pinned ? "Following the selected incident as it updates." : "Automatically follows the latest active incident."}</p></div>
      <label>Incident<select className="search" aria-label="Choose incident" value={pinned} onChange={(e) => setPinned(e.target.value)}>
        <option value="">Follow latest</option>
        {rows?.filter((i) => textValue(i.id)).slice().sort((a, b) => (numberValue(b.opened_t) ?? 0) - (numberValue(a.opened_t) ?? 0)).map((i) => <option key={String(i.id)} value={String(i.id)}>{String(i.id)} · {textValue(i.status) ?? NR}</option>)}
        {pinned && !rows?.some((i) => i.id === pinned) && <option value={pinned}>{pinned} · unavailable</option>}
      </select></label>
    </div>
    {!rows ? <div className="empty"><strong>Live incident view unavailable</strong>Waiting for fresh incident data.</div>
      : pinned && !selected ? <div className="empty"><strong>Incident unavailable</strong>This incident is not in the current response. Choose Follow latest to return.</div>
      : selected ? <PipelineView key={String(selected.id)} inc={selected} title={ACTIVE_STATUSES.includes(textValue(selected.status) ?? "") ? "Live incident" : "Closed incident"} />
      : <section className="panel watching">
        <div className="panel-title"><div><h2>{allHealthy ? "All services healthy · watching" : "No open incident · watching"}</h2><small>Service anomaly scores · refreshed every 2 s</small></div>
          <span className={`badge ${allHealthy ? "green" : ""}`}>{allHealthy ? "healthy" : "watching"}</span></div>
        {!services ? <div className="empty">Service health unavailable.</div> : <div className="watch-grid">
          {states.map(([n, s]) => {
            const r = isRecord(services[n]) ? services[n] : undefined;
            const score = numberValue(r?.score);
            return <a href="/console/topology" key={n} className={`watch-card watch-${s}`} aria-label={`Inspect ${n} in topology`}>
              <div className="watch-name">{n}<ArrowRight size={14} /></div>
              <div className="watch-score tabular">{score !== undefined ? score.toFixed(3) : NR}</div>
              <div className="watch-state">{s === "ok" ? "no anomaly reported" : s === "anomaly" ? "anomaly reported" : s === "down" ? "not running" : NR}</div>
            </a>;
          })}
        </div>}
      </section>}
    <EvaluatorRun />
  </>;
}
