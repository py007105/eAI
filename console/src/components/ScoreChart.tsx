import { Area, AreaChart, ResponsiveContainer } from "recharts";
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
      <ResponsiveContainer width="100%" height={40}>
        <AreaChart data={samples} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={`spark-${name}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#39ff14" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#39ff14" stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="value"
            stroke="#22c40a"
            strokeWidth={2}
            fill={`url(#spark-${name})`}
            dot={false}
            isAnimationActive={false}
            connectNulls={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
