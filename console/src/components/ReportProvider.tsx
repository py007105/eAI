import { reportProvenance } from "../lib/pipeline";

/** "Report written by: LLM | template" from the API's report_meta; never relabels a template report. The model vendor
 * is not named on screen: any non-template provider is shown as "LLM", and vendor prefixes are dropped from fallback reasons. */
const noVendor = (r: string) => r.replace(/^[a-z0-9_-]+:\s*/i, "");

/** Timeline text as returned, except the API's "report by <provider>" names the LLM generically ("template" kept). */
export const maskReportVendor = (msg: string) => msg.replace(/^report by (?!template\b)[a-z0-9_.-]+/i, "report by LLM");

export default function ReportProvider({ meta }: { meta: unknown }) {
  const p = reportProvenance(meta);
  if (!p.provider) return <div className="muted report-provider">Report written by: Not reported</div>;
  const isTemplate = p.provider === "template";
  return (
    <div className="report-provider">
      <span>Report written by: </span>
      <span className={`badge ${isTemplate ? "" : "cyan"}`}>{isTemplate ? "template" : "LLM"}</span>
      {isTemplate ? (
        <span className="muted">
          {" "}
          deterministic template
          {p.pending ? " · LLM report pending" : ""}
          {p.fallbackReasons.length ? ` · LLM fell back (${p.fallbackReasons.map(noVendor).join("; ")})` : ""}
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
