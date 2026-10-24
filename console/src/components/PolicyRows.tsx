import { isRecord, numberValue, textValue } from "../lib/api";

const NR = "Not reported";
const list = (v: unknown) => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : undefined);

/** Readable rulebook from /status → policy. Every value comes from the API; missing fields show "Not reported". */
export default function PolicyRows({ policy }: { policy: unknown }) {
  if (!isRecord(policy)) return <div className="muted">{NR}</div>;
  const auto = list(policy.auto_allowed_risks);
  const prot = list(policy.protected_services);
  const rr = isRecord(policy.runbook_risk) ? policy.runbook_risk : undefined;
  const sr = isRecord(policy.service_risk) ? policy.service_risk : undefined;
  const fo = isRecord(policy.fault_overrides) ? policy.fault_overrides : undefined;
  const cooldown = numberValue(policy.cooldown_s);
  const perHour = numberValue(policy.max_actions_per_hour);
  const breaker = numberValue(policy.max_unverified_actions_per_service);
  return (
    <div>
      <dl className="policy-rows tabular">
        <dt>Rulebook file</dt>
        <dd>{textValue(policy.file) ?? NR}</dd>
        <dt>Runs automatically</dt>
        <dd>
          {auto ? (
            <span className="chip-row" style={{ margin: 0 }}>
              {auto.map((r) => (
                <span key={r} className={`chip risk-${r}`}>{r} risk</span>
              ))}
            </span>
          ) : NR}
        </dd>
        <dt>Protected services</dt>
        <dd>{prot ? (prot.length ? prot.join(", ") : "none") : NR}</dd>
        <dt>Cooldown per service</dt>
        <dd>{cooldown !== undefined ? `${cooldown} s` : NR}</dd>
        <dt>Max actions per hour</dt>
        <dd>{perHour !== undefined ? perHour : policy.max_actions_per_hour === null ? "no cap" : NR}</dd>
        <dt>Unverified actions before the breaker opens</dt>
        <dd>{breaker !== undefined ? breaker : NR}</dd>
      </dl>
      {rr && (
        <>
          <h3 className="sub-head">Runbook risk</h3>
          <div className="chip-row">
            {Object.entries(rr).map(([k, v]) => (
              <span key={k} className={`chip risk-${String(v)}`}>
                {k} <b>{String(v)}</b>
              </span>
            ))}
          </div>
        </>
      )}
      {sr && Object.keys(sr).length > 0 && (
        <>
          <h3 className="sub-head">Service overrides</h3>
          <div className="chip-row">
            {Object.entries(sr).flatMap(([svc, m]) =>
              isRecord(m)
                ? Object.entries(m).map(([rb, risk]) => (
                    <span key={`${svc}-${rb}`} className={`chip risk-${String(risk)}`}>
                      {rb} on {svc} <b>{String(risk)}</b>
                    </span>
                  ))
                : [],
            )}
          </div>
        </>
      )}
      {fo && Object.keys(fo).length > 0 && (
        <>
          <h3 className="sub-head">Fault overrides</h3>
          <div className="chip-row">
            {Object.entries(fo).map(([fault, m]) => (
              <span key={fault} className="chip">
                {fault}
                <b>
                  {isRecord(m)
                    ? Object.entries(m)
                        .map(([k, v]) => (k === "risk" ? String(v) : k === "action" ? String(v) : `${k.replace(/_/g, " ")}`))
                        .join(" · ")
                    : NR}
                </b>
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
