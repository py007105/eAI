import {
  Area,
  AreaChart,
  ReferenceLine,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { isRecord, numberValue, type UnknownRecord } from "../lib/api";
import { actionsByRunbook, incidentDurations, scoreSeries, useScorecard } from "../lib/charts";
import type { Sample } from "../lib/history";

const AXIS = "#66706b";
const GRID = "#e6eae8";
const COLORS = ["#39ff14", "#12b76a", "#0a0f0c", "#8a948f", "#0b8a3a", "#4a5550"];
const tip = { background: "#ffffff", border: "1px solid #e6eae8", borderRadius: 10, color: "#0a0f0c", fontVariantNumeric: "tabular-nums" };
const hhmmss = (ms: number) => new Date(ms).toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
const hhmm = (s: number) => new Date(s * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

function Panel({ title, note, children }: { title: string; note: string; children: React.ReactNode }) {
  return (
    <section className="panel chart-panel">
      <div className="panel-title">
        <h2>{title}</h2>
        <small>{note}</small>
      </div>
      {children}
    </section>
  );
}

export function ScoreHistoryChart({ samples, incidents }: { samples: Record<string, Sample[]>; incidents?: unknown }) {
  const { rows, names } = scoreSeries(samples);
  const first = rows.length ? Number(rows[0].at) : 0;
  const marks = (Array.isArray(incidents) ? incidents : [])
    .filter(isRecord)
    .map((i) => ({ at: (numberValue(i.opened_t) ?? 0) * 1000, bad: i.status !== "recovered" }))
    .filter((m) => m.at >= first);
  return (
    <Panel title="Anomaly score over time" note="Recent observed samples · gaps indicate unavailable data">
      {rows.length < 2 ? (
        <div className="empty">Collecting samples…</div>
      ) : (
        <div style={{ height: 260 }} className="tabular">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={rows} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
              <defs>
                {names.map((n, i) => (
                  <linearGradient key={n} id={`fill-${n}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0.12} />
                    <stop offset="100%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="at" type="number" domain={["dataMin", "dataMax"]} tickFormatter={hhmmss} stroke={AXIS} fontSize={12} />
              <YAxis stroke={AXIS} fontSize={12} width={44} />
              <Tooltip contentStyle={tip} labelFormatter={(v) => hhmmss(Number(v))} />
              <Legend />
              {marks.map((m, i) => (
                <ReferenceLine key={i} x={m.at} stroke={m.bad ? "#f04438" : "#f79009"} strokeDasharray="4 3" label={{ value: "incident", fill: "#b42318", fontSize: 11, position: "top" }} />
              ))}
              {names.map((n, i) => (
                <Area key={n} type="monotone" dataKey={n} stroke={COLORS[i % COLORS.length]} strokeWidth={2.2}
                  fill={`url(#fill-${n})`} dot={false} isAnimationActive={false} connectNulls={false} />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}

export function IncidentDurationsChart({ incidents }: { incidents: unknown }) {
  const data = incidentDurations(incidents);
  return (
    <Panel title="Time to diagnose and to verified recovery" note="Seconds from each incident opening, from incident timestamps (latest 10)">
      {data.length === 0 ? (
        <div className="empty">No incidents returned yet.</div>
      ) : (
        <div style={{ height: 220 }} className="tabular">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
              <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
              <XAxis dataKey="id" stroke={AXIS} fontSize={11} />
              <YAxis stroke={AXIS} fontSize={11} width={44} unit="s" />
              <Tooltip contentStyle={tip} />
              <Legend />
              <Bar dataKey="diagnose_s" name="opened → diagnosed" fill="#0a0f0c" radius={[6, 6, 0, 0]} isAnimationActive={false} />
              <Bar dataKey="verified_s" name="opened → verified" fill="#39ff14" radius={[6, 6, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}

export function ActionsByRunbookChart({ audit }: { audit: unknown }) {
  const { data, runbooks } = actionsByRunbook(audit);
  return (
    <Panel title="Actions over time by runbook" note="Executed actions per minute, from /audit (the API keeps the most recent records)">
      {data.length === 0 ? (
        <div className="empty">No executed actions in the returned audit records.</div>
      ) : (
        <div style={{ height: 220 }} className="tabular">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
              <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
              <XAxis dataKey="minute" tickFormatter={hhmm} stroke={AXIS} fontSize={11} />
              <YAxis allowDecimals={false} stroke={AXIS} fontSize={11} width={32} />
              <Tooltip contentStyle={tip} labelFormatter={(v) => hhmm(Number(v))} />
              <Legend />
              {runbooks.map((r, i) => (
                <Bar key={r} dataKey={r} stackId="a" fill={COLORS[i % COLORS.length]} isAnimationActive={false} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}

const stat = (v: unknown) => {
  const r = isRecord(v) ? v : undefined;
  const m = numberValue(r?.mean);
  const sd = numberValue(r?.sd);
  return m === undefined ? "–" : sd === undefined ? String(m) : `${m} ± ${sd}`;
};

export function ScorecardPanel() {
  const sc = useScorecard();
  const rows =
    sc.state === "ok" && isRecord(sc.value.by_scenario)
      ? Object.entries(sc.value.by_scenario).filter(([, v]) => isRecord(v)) as [string, UnknownRecord][]
      : [];
  return (
    <Panel title="Evaluator scorecard" note="Live from /scorecard (evaluator runs scored since its results file was last reset)">
      {sc.state === "loading" ? (
        <div className="empty">Loading…</div>
      ) : sc.state === "unavailable" ? (
        <div className="empty">
          <strong>Scorecard unavailable</strong>Could not read evaluator results ({sc.reason}).
        </div>
      ) : rows.length === 0 ? (
        <div className="empty">
          <strong>No scored runs yet</strong>The evaluator reports {numberValue(sc.value.runs) ?? "Not reported"} runs.
        </div>
      ) : (
        <>
          <div style={{ height: 200 }} className="tabular">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows.map(([s, r]) => ({ s, runs: numberValue(r.runs) ?? null, detected: numberValue(r.detected) ?? null, recovered: numberValue(r.recovered) ?? null }))}
                margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
                <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
                <XAxis dataKey="s" stroke={AXIS} fontSize={11} />
                <YAxis allowDecimals={false} stroke={AXIS} fontSize={11} width={32} />
                <Tooltip contentStyle={tip} />
                <Legend />
                <Bar dataKey="runs" fill="#8a948f" radius={[6, 6, 0, 0]} isAnimationActive={false} />
                <Bar dataKey="detected" fill="#0a0f0c" radius={[6, 6, 0, 0]} isAnimationActive={false} />
                <Bar dataKey="recovered" fill="#39ff14" radius={[6, 6, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="table-wrap">
            <table className="data-table tabular">
              <thead>
                <tr>
                  <th>Scenario</th><th>Runs</th><th>Detected</th><th>Recovered</th><th>False alerts</th>
                  <th>Scorer-flagged interventions</th><th>Detect s</th><th>Verified s</th><th>Failed req %</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(([s, r]) => (
                  <tr key={s}>
                    <td>{s}</td><td>{numberValue(r.runs) ?? "–"}</td><td>{numberValue(r.detected) ?? "–"}</td>
                    <td>{numberValue(r.recovered) ?? "–"}</td><td>{numberValue(r.false_alerts) ?? "–"}</td>
                    <td>{numberValue(r.harmful_interventions) ?? "–"}</td><td>{stat(r.time_to_detect_s)}</td>
                    <td>{stat(r.time_to_verified_recovery_s)}</td><td>{stat(r.failed_request_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Panel>
  );
}
