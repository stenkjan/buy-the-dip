import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { HistoryBar } from "../api/client";

const STUFE_COLOR: Record<number, string> = {
  1: "#2ecc71", // green
  2: "#f1c40f", // yellow
  3: "#e74c3c", // red
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

// Render prop for the close Line: a colored marker only on bars where the
// strategy would have triggered, colored by Stufe. Non-triggered bars draw
// nothing (keeps the line clean over ~500 points).
interface DotProps {
  cx?: number;
  cy?: number;
  payload?: HistoryBar;
}

function TriggerDot({ cx, cy, payload }: DotProps) {
  if (cx == null || cy == null || !payload?.triggered) return null;
  return (
    <circle
      cx={cx}
      cy={cy}
      r={3.5}
      fill={STUFE_COLOR[payload.stufe] ?? "#fff"}
      stroke="#0e1116"
      strokeWidth={1}
    />
  );
}

export function AssetChart({ bars }: { bars: HistoryBar[] }) {
  if (!bars.length) return null;

  return (
    <div className="chart">
      <div className="chart__panel">
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={bars} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#232c39" strokeDasharray="3 3" />
            <XAxis
              dataKey="timestamp"
              tickFormatter={formatDate}
              minTickGap={48}
              tick={{ fill: "#8b95a5", fontSize: 11 }}
            />
            <YAxis
              domain={["auto", "auto"]}
              width={48}
              tick={{ fill: "#8b95a5", fontSize: 11 }}
            />
            <Tooltip
              contentStyle={{ background: "#141a22", border: "1px solid #232c39" }}
              labelFormatter={(v) => new Date(v as string).toUTCString()}
              formatter={(value: number, name: string) => [value?.toFixed(2), name]}
            />
            <Line
              type="monotone"
              dataKey="ema200_weekly"
              name="EMA200 1W"
              stroke="#e74c3c"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="ema200_daily"
              name="EMA200 1D"
              stroke="#e74c3c"
              strokeWidth={1}
              strokeOpacity={0.6}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="close"
              name="Close"
              stroke="#4ea1ff"
              strokeWidth={1.5}
              dot={<TriggerDot />}
              activeDot={{ r: 4 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="chart__panel">
        <ResponsiveContainer width="100%" height={110}>
          <LineChart data={bars} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#232c39" strokeDasharray="3 3" />
            <XAxis
              dataKey="timestamp"
              tickFormatter={formatDate}
              minTickGap={48}
              tick={{ fill: "#8b95a5", fontSize: 11 }}
            />
            <YAxis
              domain={[0, 100]}
              ticks={[0, 30, 70, 100]}
              width={48}
              tick={{ fill: "#8b95a5", fontSize: 11 }}
            />
            <Tooltip
              contentStyle={{ background: "#141a22", border: "1px solid #232c39" }}
              labelFormatter={(v) => new Date(v as string).toUTCString()}
              formatter={(value: number, name: string) => [value?.toFixed(2), name]}
            />
            <ReferenceLine y={70} stroke="#8b95a5" strokeDasharray="4 4" />
            <ReferenceLine y={30} stroke="#2ecc71" strokeDasharray="4 4" />
            <Line
              type="monotone"
              dataKey="rsi_1d"
              name="RSI 1D"
              stroke="#f1c40f"
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
