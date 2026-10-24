import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { isRecord, numberValue, type UnknownRecord } from "../lib/api";
import { actionsByRunbook, incidentDurations, scoreSeries, useScorecard } from "../lib/charts";
import type { Sample } from "../lib/history";

const AXIS = "#8d99a6";
const GRID = "#252d36";
const COLORS = ["#72d7e5", "#66c89b", "#e7bd69", "#e47d7d", "#a78bfa", "#a5adb7"];
const tip = { background: "#11161c", border: "1px solid #252d36", color: "#e8edf2", fontVariantNumeric: "tabular-nums" };
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

export function ScoreHistoryChart({ samples }: { samples: Record<string, Sample[]> }) {
  const { rows, names } = scoreSeries(samples);
  return (
    <Panel title="Anomaly score over time" note="Per service, from the 2 s /services polling buffer in this browser; gaps are failed polls">
      {rows.length < 2 ? (
        <div className="empty">Collecting samples…</div>
      ) : (
        <div style={{ height: 260 }} className="tabular">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
              <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
              <XAxis dataKey="at" type="number" domain={["dataMin", "dataMax"]} tickFormatter={hhmmss} stroke={AXIS} fontSize={11} />
              <YAxis stroke={AXIS} fontSize={11} width={44} />
              <Tooltip contentStyle={tip} labelFormatter={(v) => hhmmss(Number(v))} />
              <Legend />
              {names.map((n, i) => (
                <Line key={n} dataKey={n} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={false}
                  isAnimationActive={false} connectNulls={false} />
              ))}
            </LineChart>
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
              <Bar dataKey="diagnose_s" name="opened → diagnosed" fill="#72d7e5" isAnimationActive={false} />
              <Bar dataKey="verified_s" name="opened → verified" fill="#66c89b" isAnimationActive={false} />
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
  return m === undefined ? "–" : `${m} ± ${numberValue(r?.sd) ?? 0}`;
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
          <strong>Evaluator not running</strong>/scorecard did not answer ({sc.reason}).
        </div>
      ) : rows.length === 0 ? (
        <div className="empty">
          <strong>No scored runs yet</strong>The evaluator reports {numberValue(sc.value.runs) ?? 0} runs.
        </div>
      ) : (
        <>
          <div style={{ height: 200 }} className="tabular">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows.map(([s, r]) => ({ s, runs: numberValue(r.runs) ?? 0, detected: numberValue(r.detected) ?? 0, recovered: numberValue(r.recovered) ?? 0 }))}
                margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
                <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
                <XAxis dataKey="s" stroke={AXIS} fontSize={11} />
                <YAxis allowDecimals={false} stroke={AXIS} fontSize={11} width={32} />
                <Tooltip contentStyle={tip} />
                <Legend />
                <Bar dataKey="runs" fill="#a5adb7" isAnimationActive={false} />
                <Bar dataKey="detected" fill="#72d7e5" isAnimationActive={false} />
                <Bar dataKey="recovered" fill="#66c89b" isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="table-wrap">
            <table className="data-table tabular">
              <thead>
                <tr>
                  <th>Scenario</th><th>Runs</th><th>Detected</th><th>Recovered</th><th>False alerts</th>
                  <th>Harmful</th><th>Detect s</th><th>Verified s</th><th>Failed req %</th>
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
