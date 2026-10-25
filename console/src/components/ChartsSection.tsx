import { useCurrentTelemetry } from "../lib/useTelemetry";
import ContinuousWatch from "./ContinuousWatch";
import { ActionsByRunbookChart, IncidentDurationsChart, ScoreHistoryChart, ScorecardPanel } from "./Charts";

export default function ChartsSection() {
  const { data, samples } = useCurrentTelemetry();
  return (
    <div className="charts-section">
      <ContinuousWatch />
      <ScoreHistoryChart samples={samples} incidents={data.incidents.value} />
      {data.services.value === undefined && <p className="notice">Historical samples · current service data unavailable.</p>}
      <div className="live-grid">
        {data.incidents.value !== undefined ? <IncidentDurationsChart incidents={data.incidents.value} /> : <div className="empty">Incident history unavailable.</div>}
        {data.audit.value !== undefined ? <ActionsByRunbookChart audit={data.audit.value} /> : <div className="empty">Action history unavailable.</div>}
      </div>
      <ScorecardPanel />
    </div>
  );
}
