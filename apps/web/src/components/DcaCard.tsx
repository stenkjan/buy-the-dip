import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DcaSummary } from "../api/client";

function pct(v: number | null | undefined): string {
  return v == null ? "n/a" : `${(v * 100).toFixed(1)}%`;
}

function usd(v: number | null | undefined): string {
  return v == null ? "n/a" : `$${Math.round(v).toLocaleString("en-US")}`;
}

function shortDate(iso: string): string {
  const d = new Date(iso);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

export function DcaCard({ dca }: { dca: DcaSummary }) {
  const delta = dca.dca_vs_lump_sum_delta_pct;
  return (
    <article className="card">
      <header>
        <h2>{dca.asset}</h2>
        <span className="badge">
          ${dca.monthly_contribution.toLocaleString("en-US")}/mo · {dca.n_months} months
        </span>
      </header>

      <dl className="kpis">
        <dt>Invested</dt><dd>{usd(dca.total_invested)}</dd>
        <dt>Final value</dt><dd>{usd(dca.final_value)}</dd>
        <dt>Total return</dt><dd>{pct(dca.total_return_pct)}</dd>
        <dt>CAGR (money-weighted)</dt><dd>{pct(dca.cagr)}</dd>
        <dt>Max drawdown</dt><dd>{pct(dca.max_drawdown_pct)}</dd>
        <dt>Sharpe (annualised)</dt><dd>{dca.sharpe_annual == null ? "n/a" : dca.sharpe_annual.toFixed(2)}</dd>
        <dt>vs lump-sum</dt>
        <dd className={delta >= 0 ? "pos" : "neg"}>{delta >= 0 ? "+" : ""}{pct(delta)}</dd>
      </dl>

      <div className="chart">
        <div className="chart__panel">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={dca.series} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="#232c39" strokeDasharray="3 3" />
              <XAxis
                dataKey="month"
                tickFormatter={shortDate}
                minTickGap={48}
                tick={{ fill: "#8b95a5", fontSize: 11 }}
              />
              <YAxis
                width={56}
                tickFormatter={(v) => `$${Math.round((v as number) / 1000)}k`}
                tick={{ fill: "#8b95a5", fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{ background: "#141a22", border: "1px solid #232c39" }}
                labelFormatter={(v) => shortDate(v as string)}
                formatter={(value, name) => [usd(typeof value === "number" ? value : null), name]}
              />
              <Line
                type="monotone"
                dataKey="cum_invested"
                name="Invested"
                stroke="#8b95a5"
                strokeWidth={1}
                strokeDasharray="4 4"
                dot={false}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="lump_value"
                name="Lump-sum"
                stroke="#e74c3c"
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="dca_value"
                name="DCA"
                stroke="#4ea1ff"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {dca.history_truncation_warning && (
        <p className="muted disclaimer">⚠ {dca.history_truncation_warning} (free-tier data window)</p>
      )}
    </article>
  );
}
