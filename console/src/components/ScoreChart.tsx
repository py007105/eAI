import { Line, LineChart, ResponsiveContainer } from "recharts";
import type { Sample } from "../lib/history";

export default function ScoreChart({
  samples,
  name,
}: {
  samples: Sample[];
  name: string;
}) {
  return (
    <div
      className="service-chart"
      role="img"
      aria-label={`Recent API score samples for ${name}`}
    >
      <ResponsiveContainer width="100%" height={28}>
        <LineChart data={samples}>
          <Line
            type="linear"
            dataKey="value"
            stroke="#72d7e5"
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
            connectNulls={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
