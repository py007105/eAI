import { reportProvenance } from "../lib/pipeline";

/** "Report written by: <provider>" exactly as the API's report_meta says; never relabels a template report. */
export default function ReportProvider({ meta }: { meta: unknown }) {
  const p = reportProvenance(meta);
  if (!p.provider) return <div className="muted report-provider">Report written by: Not reported</div>;
  const isTemplate = p.provider === "template";
  return (
    <div className="report-provider">
      <span>Report written by: </span>
      <span className={`badge ${isTemplate ? "" : "cyan"}`}>{p.provider}</span>
      {isTemplate ? (
        <span className="muted">
          {" "}
          deterministic template
          {p.pending ? " · LLM report pending" : ""}
          {p.fallbackReasons.length ? ` · LLM fell back (${p.fallbackReasons.join("; ")})` : ""}
        </span>
      ) : (
        <span className="muted">
          {" "}
          · evidence ids validated by the backend
          {p.disagreed ? " · the LLM suggested a different runbook; the engine's choice was kept" : ""}
        </span>
      )}
    </div>
  );
}
