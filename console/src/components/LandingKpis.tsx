import { CheckCircle2, Eye, Radar, Scale, Stethoscope } from "lucide-react";
import { isRecord, numberValue, serviceState, textValue } from "../lib/api";
import NumberTicker from "./NumberTicker";
import { useTelemetry } from "../lib/useTelemetry";

const NR = "Not reported";

/** Latest verified recovery time (epoch s) from audit verification rows or incident verification fields. */
export function lastVerifiedRecovery(audit: unknown, incidents: unknown): number | undefined {
  const ts: number[] = [];
  for (const r of Array.isArray(audit) ? audit.filter(isRecord) : [])
    if (textValue(r.kind) === "verification" && textValue(r.outcome) === "recovered") {
      const t = numberValue(r.t);
      if (t !== undefined) ts.push(t);
    }
  for (const i of Array.isArray(incidents) ? incidents.filter(isRecord) : [])
    if (isRecord(i.verification) && textValue(i.verification.outcome) === "recovered") {
      const t = numberValue(i.verification.t);
      if (t !== undefined) ts.push(t);
    }
  return ts.length ? Math.max(...ts) : undefined;
}

export function LandingKpis() {
  const { data, connection } = useTelemetry();
  const live = connection === "live" || connection === "partial";
  const status = isRecord(data.status.value) ? data.status.value : undefined;
  const svc = isRecord(data.services.value) && isRecord(data.services.value.services) ? data.services.value.services : undefined;
  const names = svc ? Object.keys(svc) : [];
  const healthy = svc ? names.filter((n) => serviceState(svc[n]) === "ok").length : undefined;
  const open = numberValue(status?.open_incidents);
  const last = lastVerifiedRecovery(data.audit.value, data.incidents.value);
  const kpis: [string, string][] = [
    ["Mode", live ? textValue(status?.mode) ?? NR : NR],
    ["Services healthy", live && healthy !== undefined ? `${healthy} / ${names.length}` : NR],
    ["Open incidents", live && open !== undefined ? String(open) : NR],
    [
      "Last verified recovery",
      live
        ? last !== undefined
          ? new Date(last * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
          : "none since the API started"
        : NR,
    ],
  ];
  return (
    <div className="kpi-strip" aria-label="Live key figures">
      {kpis.map(([k, v]) => (
        <div key={k} className="kpi">
          <div className="kpi-label">{k}</div>
          <div className="kpi-value">
            <NumberTicker value={v} />
          </div>
        </div>
      ))}
    </div>
  );
}

const STEPS: [string, string][] = [
  ["Observe", "Service metrics and container state are read every 2 s."],
  ["Detect", "Learned per-service limits flag what is unusual."],
  ["Diagnose", "The root-cause service and the likely fault are ranked with evidence."],
  ["Decide", "The rulebook runs low-risk fixes and asks a person for high-risk ones."],
  ["Verify", "A real checkout must pass again before an incident counts as recovered."],
];

const ICONS = [<Eye key="o" size={17} />, <Radar key="d" size={17} />, <Stethoscope key="g" size={17} />, <Scale key="p" size={17} />, <CheckCircle2 key="v" size={17} />];

export function HowItWorks() {
  return (
    <div className="steps-row">
      {STEPS.map(([t, d], i) => (
        <div key={t} className="step">
          <div className="step-icon" aria-hidden="true">{ICONS[i]}</div>
          <div className="step-n">{String(i + 1).padStart(2, "0")}</div>
          <div className="step-t">{t}</div>
          <div className="step-d">{d}</div>
        </div>
      ))}
    </div>
  );
}
