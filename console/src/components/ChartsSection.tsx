import { useTelemetry } from "../lib/useTelemetry";
import ContinuousWatch from "./ContinuousWatch";
import { ActionsByRunbookChart, IncidentDurationsChart, ScoreHistoryChart, ScorecardPanel } from "./Charts";

export default function ChartsSection() {
  const { data, samples, connection } = useTelemetry();
  const live = connection === "live" || connection === "partial";
  return (
    <div className="charts-section">
      <ContinuousWatch />
      <ScoreHistoryChart samples={samples} incidents={data.incidents.value} />
      <div className="live-grid">
        {live ? (
          <>
            <IncidentDurationsChart incidents={data.incidents.value} />
            <ActionsByRunbookChart audit={data.audit.value} />
          </>
        ) : (
          <div className="empty">Incident and action charts need a connected API.</div>
        )}
      </div>
      <ScorecardPanel />
    </div>
  );
}
