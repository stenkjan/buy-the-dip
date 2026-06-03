import type { HistoryBar, Signal } from "../api/client";
import { AssetChart } from "./AssetChart";

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
        <h2>{signal.symbol}</h2>
        <span className="badge">Stufe {signal.stufe}</span>
      </header>
      <dl>
        <dt>Trigger</dt><dd>{signal.triggered ? "YES" : "no"}</dd>
        <dt>Price</dt><dd>{signal.price.toFixed(2)}</dd>
        <dt>RSI</dt><dd>{signal.rsi_value.toFixed(2)} (≤ {signal.rsi_threshold.toFixed(2)})</dd>
        <dt>Tranche</dt><dd>{tr ? `${tr[0]}–${tr[1]}%` : "n/a"}</dd>
        <dt>Bar</dt><dd>{new Date(signal.timestamp).toUTCString()}</dd>
      </dl>
      {history && history.length > 0 && <AssetChart bars={history} />}
    </article>
  );
}
