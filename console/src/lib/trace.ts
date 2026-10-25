import { isRecord, numberValue, textValue, type UnknownRecord } from "./api";
import { approverChannel, lastAction, type Channel } from "./pipeline";

/** Investigation trace built only from the incident's own evidence items, ranking, actions, verification and
 * timeline. Anything the API does not return stays "Not reported". */
export type TraceSource =
  | "Prometheus metrics"
  | "Docker container"
  | "Logs"
  | "Deploy history"
  | "Dependencies"
  | "Forecast"
  | "Knowledge base"
  | "Other";
export interface TraceStep {
  kind: "evidence" | "causes" | "policy" | "approval" | "action" | "verification";
  source?: TraceSource;
  t?: number;
  summary: string;
  id?: string;
  channel?: Channel;
}
const NR = "Not reported";

export function evidenceSource(tool: unknown): TraceSource {
  const t = (textValue(tool) ?? "").toLowerCase();
  if (t === "metrics") return "Prometheus metrics";
  if (t === "container") return "Docker container";
  if (t === "error_logs" || t.includes("log")) return "Logs";
  if (t === "deploy_history") return "Deploy history";
  if (t === "dependency_failures") return "Dependencies";
  if (t === "forecast") return "Forecast";
  if (t === "similar_incidents" || t.includes("kb") || t.includes("knowledge")) return "Knowledge base";
  return "Other";
}

const timelineAt = (inc: UnknownRecord, re: RegExp) => {
  for (const e of Array.isArray(inc.timeline) ? inc.timeline : [])
    if (isRecord(e) && typeof e.msg === "string" && re.test(e.msg)) return numberValue(e.t);
  return undefined;
};

export function buildTrace(inc: UnknownRecord): TraceStep[] {
  const steps: TraceStep[] = [];
  for (const e of Array.isArray(inc.evidence) ? inc.evidence.filter(isRecord) : [])
    steps.push({
      kind: "evidence",
      source: evidenceSource(e.tool),
      t: numberValue(e.t),
      summary: textValue(e.summary) ?? NR,
      id: textValue(e.id),
    });

  const ranking = Array.isArray(inc.ranking) ? inc.ranking.filter(isRecord) : [];
  const diag = isRecord(inc.diagnosis) ? inc.diagnosis : undefined;
  const abstained = inc.abstained === true || textValue(inc.likely_cause) === "insufficient_evidence";
  const diagnosedAt = timelineAt(inc, /^diagnosed /i);
  if (abstained) {
    const why = textValue(diag?.abstain_reason);
    steps.push({ kind: "causes", t: diagnosedAt, summary: `abstained: insufficient evidence${why ? ` (${why})` : ""}` });
  } else if (ranking.length) {
    const top = ranking
      .slice(0, 3)
      .map((r) => `${textValue(r.service) ?? "?"} ${numberValue(r.score)?.toFixed(2) ?? "?"}`)
      .join(" · ");
    const s0 = numberValue(ranking[0]?.score);
    const s1 = numberValue(ranking[1]?.score);
    const margin = s0 !== undefined && s1 !== undefined ? ` · margin ${(s0 - s1).toFixed(2)}` : "";
    steps.push({ kind: "causes", t: diagnosedAt, summary: `${top}${margin} → ${textValue(inc.likely_cause) ?? NR}` });
  } else steps.push({ kind: "causes", summary: NR });

  const act = lastAction(inc);
  steps.push({
    kind: "policy",
    t: numberValue(act?.t),
    summary: act ? `${textValue(act.verdict) ?? NR}${textValue(act.reason) ? ` — ${textValue(act.reason)}` : ""}` : NR,
  });
  const approver = textValue(act?.approved_by);
  const verdict = textValue(act?.verdict);
  steps.push({
    kind: "approval",
    summary: approver
      ? `approved by ${approver}`
      : verdict === "execute"
        ? "not needed (policy allowed it)"
        : verdict === "needs_approval"
          ? "waiting for a person"
          : verdict ?? NR,
    channel: approver ? approverChannel(approver).channel : undefined,
  });
  steps.push({
    kind: "action",
    t: act?.executed === true ? numberValue(act.executed_t) : undefined,
    summary: act
      ? `${textValue(act.runbook_id) ?? NR} on ${textValue(act.service) ?? NR} · ${act.executed === true ? "executed" : "not executed"}`
      : NR,
  });
  const ver = isRecord(inc.verification) ? inc.verification : undefined;
  const rate = numberValue(ver?.success_rate);
  steps.push({
    kind: "verification",
    t: numberValue(ver?.t),
    summary: ver
      ? `${textValue(ver.outcome) ?? NR}${rate !== undefined ? ` (${Math.round(rate * 100)}% of ${numberValue(ver.probes) ?? "?"} checkouts)` : ""}`
      : NR,
  });
  return steps;
}

/** Outcome counts over the incidents the API returned (not global totals). */
export function outcomeCounts(incidents: unknown) {
  const list = Array.isArray(incidents) ? incidents.filter(isRecord) : [];
  const out = { total: list.length, fixedVerified: 0, waitingApproval: 0, blockedKillSwitch: 0, abstained: 0 };
  for (const i of list) {
    const status = textValue(i.status);
    if (status === "recovered") out.fixedVerified += 1;
    if (status === "awaiting_approval") out.waitingApproval += 1;
    const acts = Array.isArray(i.actions) ? i.actions.filter(isRecord) : [];
    if (acts.some((a) => textValue(a.verdict) === "blocked" && /kill switch/i.test(textValue(a.reason) ?? ""))) out.blockedKillSwitch += 1;
    if (i.abstained === true || textValue(i.likely_cause) === "insufficient_evidence") out.abstained += 1;
  }
  return out;
}
