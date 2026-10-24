import { useEffect, useState } from "react";
import { isRecord, numberValue, textValue, type UnknownRecord } from "./api";
import type { Sample } from "./history";
import { approverChannel, type Channel } from "./pipeline";

/** Per-service score rows aligned on poll time; a failed poll leaves null (a gap), never a made-up value. */
export function scoreSeries(samples: Record<string, Sample[]>): { rows: Record<string, number | null>[]; names: string[] } {
  const names = Object.keys(samples).sort();
  const stamps = [...new Set(names.flatMap((n) => samples[n].map((s) => s.at)))].sort((a, b) => a - b);
  const rows = stamps.map((at) => {
    const row: Record<string, number | null> = { at };
    for (const n of names) {
      const s = samples[n].find((x) => x.at === at);
      row[n] = s ? s.value : null;
    }
    return row;
  });
  return { rows, names };
}

const timelineAt = (inc: UnknownRecord, re: RegExp) => {
  for (const e of Array.isArray(inc.timeline) ? inc.timeline : [])
    if (isRecord(e) && typeof e.msg === "string" && re.test(e.msg)) return numberValue(e.t);
  return undefined;
};

/** Seconds from the incident opening to diagnosis and to verification, from incident timestamps only. */
export function incidentDurations(incidents: unknown, limit = 10) {
  const list = Array.isArray(incidents) ? incidents.filter(isRecord) : [];
  return list
    .filter((i) => numberValue(i.opened_t) !== undefined)
    .sort((a, b) => (numberValue(a.opened_t) ?? 0) - (numberValue(b.opened_t) ?? 0))
    .slice(-limit)
    .map((i) => {
      const opened = numberValue(i.opened_t)!;
      const diag = timelineAt(i, /^diagnosed /i);
      const ver = isRecord(i.verification) ? numberValue(i.verification.t) : undefined;
      return {
        id: textValue(i.id) ?? "?",
        diagnose_s: diag !== undefined ? +(diag - opened).toFixed(1) : null,
        verified_s: ver !== undefined ? +(ver - opened).toFixed(1) : null,
        outcome: isRecord(i.verification) ? textValue(i.verification.outcome) ?? null : null,
      };
    });
}

/** Executed actions (audit rows with an actor; verification rows excluded), counted per minute and runbook. */
export function actionsByRunbook(audit: unknown) {
  const rows = Array.isArray(audit) ? audit.filter(isRecord) : [];
  const actions = rows.filter((r) => textValue(r.actor) && textValue(r.kind) !== "verification" && numberValue(r.t));
  const runbooks = [...new Set(actions.map((r) => textValue(r.runbook) ?? "unknown"))].sort();
  const buckets = new Map<number, Record<string, number>>();
  for (const r of actions) {
    const minute = Math.floor(numberValue(r.t)! / 60) * 60;
    const b = buckets.get(minute) ?? {};
    const k = textValue(r.runbook) ?? "unknown";
    b[k] = (b[k] ?? 0) + 1;
    buckets.set(minute, b);
  }
  const data = [...buckets.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([minute, counts]) => ({ minute, ...Object.fromEntries(runbooks.map((r) => [r, counts[r] ?? 0])) }));
  return { data, runbooks };
}

/** Executed actions by approval channel, derived from audit `actor` values. */
export function actionsByChannel(audit: unknown): Record<Channel, number> {
  const out: Record<Channel, number> = { Telegram: 0, Dashboard: 0, Autopilot: 0, Script: 0, Person: 0, "Not reported": 0 };
  const rows = Array.isArray(audit) ? audit.filter(isRecord) : [];
  for (const r of rows) {
    if (textValue(r.kind) === "verification") continue;
    if (!textValue(r.actor)) continue;
    out[approverChannel(r.actor).channel] += 1;
  }
  return out;
}

export type ScorecardState =
  | { state: "loading" }
  | { state: "ok"; value: UnknownRecord }
  | { state: "unavailable"; reason: string };

/** /scorecard comes from the evaluator through the brain; polled separately (10 s) so an evaluator outage
 * never marks the whole console as disconnected. */
export function useScorecard(intervalMs = 10000): ScorecardState {
  const [s, setS] = useState<ScorecardState>({ state: "loading" });
  useEffect(() => {
    let alive = true;
    const run = async () => {
      try {
        const r = await fetch("/api/scorecard", { method: "GET", headers: { Accept: "application/json" } });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const v = await r.json();
        if (alive) setS(isRecord(v) ? { state: "ok", value: v } : { state: "unavailable", reason: "unexpected response" });
      } catch (e) {
        if (alive) setS({ state: "unavailable", reason: e instanceof Error ? e.message : "error" });
      }
    };
    void run();
    const t = window.setInterval(run, intervalMs);
    return () => {
      alive = false;
      window.clearInterval(t);
    };
  }, [intervalMs]);
  return s;
}
