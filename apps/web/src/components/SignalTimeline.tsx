import { useState } from "react";
import {
  CartesianGrid,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { ResponsiveContainer } from "recharts";
import type { TimelinePayload, TimelineSignal } from "../api/client";

const STUFE_COLOR: Record<number, string> = {
  1: "#2ecc71",
  2: "#f1c40f",
  3: "#e74c3c",
};

interface Point extends TimelineSignal {
  t: number;
}

function pct(v: number | null | undefined): string {
  return v == null ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;
}

function TimelineTooltip({ active, payload }: { active?: boolean; payload?: { payload: Point }[] }) {
  const p = payload?.[0]?.payload;
  if (!active || !p) return null;
  const d = new Date(p.timestamp);
  return (
    <div className="tl-tooltip">
      <strong>Stufe {p.stufe}</strong> · {d.toISOString().slice(0, 10)}
      <div>price {p.price.toFixed(2)}</div>
      <div>RSI {p.rsi_value.toFixed(2)} (≤ {p.rsi_threshold.toFixed(2)})</div>
      <div>
        fwd: 30d {pct(p.fwd_30d)} · 90d {pct(p.fwd_90d)} · 365d {pct(p.fwd_365d)}
      </div>
    </div>
  );
}

export function SignalTimeline({ timeline }: { timeline: TimelinePayload }) {
  const [enabled, setEnabled] = useState<Record<number, boolean>>({ 1: true, 2: true, 3: true });

  const points: Point[] = timeline.signals.map((s) => ({ ...s, t: new Date(s.timestamp).getTime() }));
  const perStufe = (stufe: number) => points.filter((p) => p.stufe === stufe);

  return (
    <article className="card">
      <header>
        <h2>{timeline.asset}</h2>
        <span className="badge">
          {timeline.summary.total} triggers · {timeline.n_bars} bars
          {timeline.liberal ? " · liberal" : " · strict"}
        </span>
      </header>

      <div className="tl-filters">
        {[1, 2, 3].map((stufe) => (
          <button
            key={stufe}
            className={enabled[stufe] ? "tl-chip is-on" : "tl-chip"}
            style={{ borderColor: STUFE_COLOR[stufe] }}
            onClick={() => setEnabled((e) => ({ ...e, [stufe]: !e[stufe] }))}
          >
            <span className="tl-dot" style={{ background: STUFE_COLOR[stufe] }} />
            Stufe {stufe} ({timeline.summary.per_stufe[String(stufe)] ?? 0})
          </button>
        ))}
      </div>

      <div className="chart">
        <div className="chart__panel">
          <ResponsiveContainer width="100%" height={220}>
            <ScatterChart margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="#232c39" strokeDasharray="3 3" />
              <XAxis
                type="number"
                dataKey="t"
                domain={["dataMin", "dataMax"]}
                tickFormatter={(v) => new Date(v as number).getUTCFullYear().toString()}
                tick={{ fill: "#8b95a5", fontSize: 11 }}
                name="date"
              />
              <YAxis
                type="number"
                dataKey="price"
                domain={["auto", "auto"]}
                width={56}
                tick={{ fill: "#8b95a5", fontSize: 11 }}
                name="price"
              />
              <ZAxis range={[40, 40]} />
              <Tooltip content={<TimelineTooltip />} cursor={{ strokeDasharray: "3 3" }} />
              {[1, 2, 3]
                .filter((stufe) => enabled[stufe])
                .map((stufe) => (
                  <Scatter
                    key={stufe}
                    name={`Stufe ${stufe}`}
                    data={perStufe(stufe)}
                    fill={STUFE_COLOR[stufe]}
                    isAnimationActive={false}
                  />
                ))}
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>
    </article>
  );
}
