import { useEffect, useRef, useState } from "react";
import { isRecord, numberValue, textValue, type UnknownRecord } from "../lib/api";

const NR = "Not reported";
const display = (v: unknown, unit = "") => typeof v === "boolean" ? (v ? "Yes" : "No") : numberValue(v) !== undefined ? `${v}${unit}` : textValue(v) ?? NR;

/** Observes an operator-started run. Never starts a run or fetches truth before completion. */
export default function EvaluatorRun() {
  const [id, setId] = useState("");
  const [status, setStatus] = useState<UnknownRecord>();
  const [result, setResult] = useState<UnknownRecord>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const pending = useRef<AbortController | null>(null);
  const revision = useRef(0);
  useEffect(() => () => { revision.current++; pending.current?.abort(); }, []);
  async function read(reveal = false) {
    const runId = id.trim();
    if (!/^[a-zA-Z0-9_-]{1,64}$/.test(runId)) { setError("Enter the run ID returned by the operator command."); return; }
    const version = ++revision.current;
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    const timeout = window.setTimeout(() => controller.abort(), 5000);
    setBusy(true); setError(""); setResult(undefined);
    if (!reveal) setStatus(undefined);
    try {
      const response = await fetch(`/api/challenge/${encodeURIComponent(runId)}/${reveal ? "reveal" : "status"}`, { method: "GET", signal: controller.signal, headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(response.status === 409 ? "Results are available after scoring finishes." : `Run unavailable (HTTP ${response.status}).`);
      const data: unknown = await response.json();
      if (!isRecord(data)) throw new Error("Unexpected evaluator response.");
      if (reveal) {
        if (!isRecord(data.truth) || !isRecord(data.score) || data.truth.run_id !== runId) throw new Error("Unexpected result for this run.");
      } else if (data.run_id !== runId || !["running", "finished", "failed"].includes(String(data.state))) throw new Error("Unexpected status for this run.");
      if (version === revision.current) { if (reveal) setResult(data); else setStatus(data); }
    } catch (e) {
      if (version === revision.current) { setError(e instanceof Error ? e.message : "Run unavailable."); setStatus(undefined); }
    } finally {
      window.clearTimeout(timeout);
      if (version === revision.current) { setBusy(false); pending.current = null; }
    }
  }
  const truth = isRecord(result?.truth) ? result.truth : undefined;
  const score = isRecord(result?.score) ? result.score : undefined;
  return <section className="panel evaluator-run">
    <div className="panel-title"><div><h2>Evaluator run</h2><small>Inspect a run started from your operator terminal.</small></div><span className="badge">Read-only</span></div>
    <form className="run-form" onSubmit={(e) => { e.preventDefault(); void read(); }}>
      <label htmlFor="run-id" className="sr-only">Evaluator run ID</label>
      <input id="run-id" className="search" value={id} placeholder="Enter run ID" maxLength={64} autoComplete="off" onChange={(e) => {
        revision.current++; pending.current?.abort(); setBusy(false); setId(e.target.value); setStatus(undefined); setResult(undefined); setError("");
      }} />
      <button className="btn" disabled={busy || !id.trim()}>{busy ? "Checking…" : "Check run"}</button>
      {status?.state === "finished" && !result && <button className="btn btn-primary" type="button" disabled={busy} onClick={() => void read(true)}>Reveal result</button>}
    </form>
    {error && <p className="notice" role="alert">{error}</p>}
    {status && <p className="proof-note">Run <strong>{id.trim()}</strong> · {display(status.state)} · elapsed at check: {display(status.elapsed_s, " s")}{status.state === "running" ? " · Check again after scoring; ground truth remains hidden." : ""}</p>}
    {truth && score && <div className="run-result">
      <h3>{display(truth.scenario)} · {display(truth.target)}</h3>
      <dl className="detail-list">
        {[
          ["Detected", display(score.detected)], ["Verified recovery", display(score.recovered)],
          ["Detection time", display(score.time_to_detect_s, " s")], ["Recovery time", display(score.time_to_verified_recovery_s, " s")],
          ["Correct top-ranked service", display(score.diagnosis_top1)], ["Target in top three", display(score.diagnosis_top3)],
          ["Failed requests", display(score.failed_request_pct, "%")], ["False alerts", display(score.false_alerts)],
          ["Scorer-flagged interventions", display(score.harmful_interventions)],
        ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
      </dl>
      <p className="proof-note">The scorer flags actions on a non-target service, or any action during a healthy run. This count does not measure added damage.</p>
    </div>}
  </section>;
}
