import type { HistoryBar, Signal } from "../api/client";
import { AssetChart } from "./AssetChart";

const STUFE_COLOR: Record<number, string> = {
  1: "#2ecc71",
  2: "#f1c40f",
  3: "#e74c3c",
};

export function SignalCard({
  signal,
  history,
}: {
  signal: Signal;
  history?: HistoryBar[];
}) {
  const tr = signal.tranche_pct_range;
  return (
    <article className={`card card--stufe-${signal.stufe} ${signal.triggered ? "is-triggered" : ""}`}>
      <header>
        <h2>
          <span className="stufe-dot" style={{ background: STUFE_COLOR[signal.stufe] }} />
          {signal.symbol}
        </h2>
        <span className="badge">Stufe {signal.stufe}</span>
      </header>

      <div className={signal.triggered ? "trigger-banner is-on" : "trigger-banner"}>
        {signal.triggered ? "● BUY-THE-DIP TRIGGERED" : "no trigger"}
      </div>

      <dl>
        <dt>Price</dt><dd>{signal.price.toFixed(2)}</dd>
        <dt>RSI</dt><dd>{signal.rsi_value.toFixed(2)} (≤ {signal.rsi_threshold.toFixed(2)})</dd>
        <dt>Tranche</dt><dd>{tr ? `${tr[0]}–${tr[1]}%` : "n/a"}</dd>
        <dt>Bar</dt><dd>{new Date(signal.timestamp).toUTCString()}</dd>
      </dl>
      {history && history.length > 0 && <AssetChart bars={history} />}
    </article>
  );
}
