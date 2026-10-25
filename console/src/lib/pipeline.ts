import { isRecord, numberValue, textValue, type UnknownRecord } from "./api";

/** Incident pipeline derived only from fields the EternalAI API returns (incident fields and timeline messages). */
export type StageKey =
  | "detect"
  | "diagnose"
  | "policy"
  | "approval"
  | "fix"
  | "verified";
export type StageStatus = "done" | "current" | "pending" | "skipped" | "failed";
export interface Stage {
  key: StageKey;
  label: string;
  status: StageStatus;
  at?: number; // epoch seconds, as reported by the API
  elapsed?: number; // seconds since the incident opened
  detail?: string;
}

export const ACTIVE_STATUSES = ["open", "awaiting_approval", "executing", "verifying"];

export type Channel =
  | "Telegram"
  | "Dashboard"
  | "Autopilot"
  | "Script"
  | "Person"
  | "Not reported";
export interface Approver {
  channel: Channel;
  id?: string;
  raw?: string;
}

/** "human:telegram:7769231832" -> Telegram; "human:dashboard" / "dashboard" -> Dashboard; "autopilot" -> Autopilot. */
export function approverChannel(value: unknown): Approver {
  const raw = textValue(value);
  if (!raw) return { channel: "Not reported" };
  const lower = raw.toLowerCase();
  if (lower === "autopilot") return { channel: "Autopilot", raw };
  const who = lower.startsWith("human:") ? raw.slice(6) : raw;
  const w = who.toLowerCase();
  if (w.startsWith("telegram:")) return { channel: "Telegram", id: who.slice(9), raw };
  if (w === "telegram") return { channel: "Telegram", raw };
  if (w === "dashboard") return { channel: "Dashboard", raw };
  if (w.startsWith("benchmark-operator") || w.startsWith("kind-e2e"))
    return { channel: "Script", id: who, raw };
  return { channel: "Person", id: who, raw };
}

const timelineAt = (inc: UnknownRecord, re: RegExp): number | undefined => {
  const tl = Array.isArray(inc.timeline) ? inc.timeline : [];
  for (const e of tl) {
    if (isRecord(e) && typeof e.msg === "string" && re.test(e.msg)) {
      const t = numberValue(e.t);
      if (t !== undefined) return t;
    }
  }
  return undefined;
};

export const lastAction = (inc: UnknownRecord): UnknownRecord | undefined => {
  const acts = Array.isArray(inc.actions) ? inc.actions.filter(isRecord) : [];
  return acts.length ? acts[acts.length - 1] : undefined;
};

export function deriveStages(inc: UnknownRecord): Stage[] {
  const opened = numberValue(inc.opened_t);
  const status = textValue(inc.status) ?? "";
  const active = ACTIVE_STATUSES.includes(status);
  const act = lastAction(inc);
  const verdict = textValue(act?.verdict);
  const ver = isRecord(inc.verification) ? inc.verification : undefined;
  const el = (t?: number) =>
    t !== undefined && opened !== undefined ? Math.max(0, t - opened) : undefined;

  const detectAt = timelineAt(inc, /^anomaly confirmed/i) ?? opened;
  const cause = textValue(inc.likely_cause);
  const diagnosed = cause !== undefined && cause !== "pending";
  const diagnoseAt = timelineAt(inc, /^diagnosed /i);
  const policyAt = timelineAt(inc, /^policy:/i) ?? numberValue(act?.t);
  const approvalNeeded =
    verdict === "needs_approval" ||
    verdict === "expired_unapproved" ||
    (typeof verdict === "string" && verdict.startsWith("rejected_by_")) ||
    !!textValue(act?.approved_by);
  const executed = act?.executed === true;
  const fixAt = timelineAt(inc, /^executed /i) ?? numberValue(act?.executed_t);
  const outcome = textValue(ver?.outcome);
  const verAt = numberValue(ver?.t) ?? timelineAt(inc, /^verification:/i);

  const stages: Stage[] = [
    { key: "detect", label: "Detect", status: "done", at: detectAt, elapsed: el(detectAt),
      detail: Array.isArray(inc.services) ? `anomaly on ${inc.services.join(", ")}` : undefined },
    { key: "diagnose", label: "Diagnose", status: diagnosed ? "done" : "pending", at: diagnoseAt,
      elapsed: el(diagnoseAt), detail: diagnosed ? cause : undefined },
    { key: "policy", label: "Policy decision", status: verdict ? "done" : "pending", at: policyAt,
      elapsed: el(policyAt), detail: verdict },
    { key: "approval", label: "Approval", status: "pending" },
    { key: "fix", label: "Fix executed", status: executed ? "done" : "pending", at: executed ? fixAt : undefined,
      elapsed: executed ? el(fixAt) : undefined, detail: textValue(act?.runbook_id) },
    { key: "verified", label: "Verified recovered", status: "pending", at: undefined },
  ];
  const approval = stages[3];
  if (verdict && !approvalNeeded) {
    approval.status = "skipped";
    approval.detail = verdict === "execute" ? "not needed (policy allowed it)" : verdict;
  } else if (textValue(act?.approved_by)) {
    approval.status = "done";
    approval.detail = textValue(act?.approved_by);
    approval.at = fixAt;
    approval.elapsed = el(fixAt);
  } else if (verdict === "expired_unapproved" || (verdict ?? "").startsWith("rejected_by_")) {
    approval.status = "failed";
    approval.detail = verdict;
  } else if (verdict === "needs_approval") {
    approval.detail = "waiting for a person";
  }
  if (verdict === "blocked" || verdict === "observe_only") {
    stages[4].status = "skipped";
    stages[4].detail = verdict === "blocked" ? "blocked by policy" : "watch-only: nothing executed";
  }
  const verified = stages[5];
  if (outcome === "recovered") {
    verified.status = "done";
    verified.at = verAt;
    verified.elapsed = el(verAt);
    verified.detail = "recovered";
  } else if (outcome) {
    verified.status = "failed";
    verified.at = verAt;
    verified.elapsed = el(verAt);
    verified.detail = outcome;
  }
  if (active) {
    const cur = stages.find((s) => s.status === "pending");
    if (cur) cur.status = "current";
  }
  return stages;
}

/** Report provenance exactly as `report_meta` reports it. A template report is never relabelled as LLM.
 * The backend accepts an LLM report only after its evidence ids validate (eternalai/llm.py validate()), so a
 * non-template provider means "passed"; `fallback_reasons` lists failed LLM attempts. */
export interface ReportProvenance {
  provider?: string; // as reported, e.g. "template", "gemini", "groq"
  pending: boolean;
  validated?: boolean; // true for an accepted LLM report; undefined for template
  fallbackReasons: string[];
  disagreed?: boolean;
}
export function reportProvenance(meta: unknown): ReportProvenance {
  const m = isRecord(meta) ? meta : undefined;
  const provider = textValue(m?.provider);
  const reasons = Array.isArray(m?.fallback_reasons)
    ? m.fallback_reasons.filter((x): x is string => typeof x === "string")
    : [];
  return {
    provider,
    pending: m?.llm_pending === true,
    validated: provider && provider !== "template" ? true : undefined,
    fallbackReasons: reasons,
    disagreed: typeof m?.llm_disagreed === "boolean" ? m.llm_disagreed : undefined,
  };
}

/** The newest active incident; otherwise undefined (the view then shows the watching state). */
export function newestActive(incidents: unknown): UnknownRecord | undefined {
  const list = Array.isArray(incidents) ? incidents.filter(isRecord) : [];
  return list
    .filter((i) => ACTIVE_STATUSES.includes(textValue(i.status) ?? ""))
    .sort((a, b) => (numberValue(b.opened_t) ?? 0) - (numberValue(a.opened_t) ?? 0))[0];
}

/** The newest closed incident that closed within `withinS` seconds of `now` (epoch seconds). */
export function recentClosed(incidents: unknown, now: number, withinS = 600): UnknownRecord | undefined {
  const list = Array.isArray(incidents) ? incidents.filter(isRecord) : [];
  return list
    .filter((i) => !ACTIVE_STATUSES.includes(textValue(i.status) ?? ""))
    .filter((i) => {
      const c = numberValue(i.closed_t);
      return c !== undefined && now - c <= withinS;
    })
    .sort((a, b) => (numberValue(b.closed_t) ?? 0) - (numberValue(a.closed_t) ?? 0))[0];
}
