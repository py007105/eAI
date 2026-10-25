import { useState } from "react";
import { Activity, BookOpen, Box, CheckCircle2, FileText, GitCommit, Gavel, Network, Play, Scale, TrendingUp, UserCheck } from "lucide-react";
import type { UnknownRecord } from "../lib/api";
import { buildTrace, type TraceStep } from "../lib/trace";

const icon = (s: TraceStep) => {
  if (s.kind === "causes") return <Scale size={14} />;
  if (s.kind === "policy") return <Gavel size={14} />;
  if (s.kind === "approval") return <UserCheck size={14} />;
  if (s.kind === "action") return <Play size={14} />;
  if (s.kind === "verification") return <CheckCircle2 size={14} />;
  switch (s.source) {
    case "Prometheus metrics":
      return <Activity size={14} />;
    case "Docker container":
      return <Box size={14} />;
    case "Logs":
      return <FileText size={14} />;
    case "Deploy history":
      return <GitCommit size={14} />;
    case "Dependencies":
      return <Network size={14} />;
    case "Forecast":
      return <TrendingUp size={14} />;
    case "Knowledge base":
      return <BookOpen size={14} />;
    default:
      return <FileText size={14} />;
  }
};
const title: Record<TraceStep["kind"], string> = {
  evidence: "Evidence",
  causes: "Ranked causes",
  policy: "Policy verdict",
  approval: "Approval",
  action: "Action",
  verification: "Verification",
};
const EVIDENCE_SHOWN = 4;
const clock = (t?: number) =>
  t === undefined ? "time not reported" : new Date(t * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });

export default function InvestigationTrace({ incident }: { incident: UnknownRecord }) {
  const steps = buildTrace(incident);
  const [expanded, setExpanded] = useState(false);
  // Collapsed view hides only evidence beyond the first EVIDENCE_SHOWN; causes, policy, approval, action and
  // verification always stay visible so the outcome is never folded away.
  const evidenceCount = steps.filter((s) => s.kind === "evidence").length;
  let seen = 0;
  const visible = expanded ? steps : steps.filter((s) => s.kind !== "evidence" || ++seen <= EVIDENCE_SHOWN);
  return (
    <div className="panel-subsection">
      <div className="panel-title">
        <h2>Investigation trace</h2>
        <small>Built only from this incident's evidence items, ranking, actions, verification and timeline</small>
      </div>
      <ol className="trace">
        {visible.map((s, i) => (
          <li key={i} className={`trace-step trace-${s.kind}`}>
            <span className="trace-icon" aria-hidden="true">{icon(s)}</span>
            <div className="trace-body">
              <div className="trace-head">
                <b>{s.kind === "evidence" ? s.source : title[s.kind]}</b>
                <span className="trace-time tabular">{clock(s.t)}</span>
                {s.id && <span className="badge">{s.id}</span>}
                {s.channel && <span className={`badge ${s.channel === "Telegram" ? "cyan" : s.channel === "Dashboard" ? "green" : ""}`}>{s.channel}</span>}
              </div>
              <div className="trace-summary">{s.summary}</div>
            </div>
          </li>
        ))}
      </ol>
      {evidenceCount > EVIDENCE_SHOWN && (
        <button type="button" className="btn" aria-expanded={expanded} onClick={() => setExpanded((v) => !v)}>
          {expanded ? "Show fewer evidence items" : `Show all ${evidenceCount} evidence items`}
        </button>
      )}
    </div>
  );
}
