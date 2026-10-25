import { outcomeCounts } from "../lib/trace";
import { useCurrentTelemetry } from "../lib/useTelemetry";

export default function ContinuousWatch() {
  const { data } = useCurrentTelemetry();
  const live = data.incidents.value !== undefined;
  const last = data.incidents.updatedAt;
  const c = live ? outcomeCounts(data.incidents.value) : undefined;
  const cell = (label: string, v?: number) => (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{v ?? "Not reported"}</div>
    </div>
  );
  return (
    <section className="panel chart-panel">
      <div className="panel-title">
        <h2>Continuous watch</h2>
        <small className="tabular">
          Last successful check {last ? new Date(last).toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" }) : "Not reported"} ·
          counts from returned incidents ({c?.total ?? "?"}), not global totals
        </small>
      </div>
      <div className="kpi-strip" style={{ marginTop: 8 }}>
        {cell("Fixed and verified", c?.fixedVerified)}
        {cell("Waiting for approval", c?.waitingApproval)}
        {cell("Blocked by kill switch", c?.blockedKillSwitch)}
        {cell("Abstained", c?.abstained)}
      </div>
    </section>
  );
}
