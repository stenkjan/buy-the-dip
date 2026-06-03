import { useState } from "react";
import { adminApi, type SweepEntry, type SweepResult } from "../api/admin";

const KEY_STORAGE = "btd_api_key";

function pct(v: number | null): string {
  return v == null ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;
}

function thresholdLabel(params: Record<string, unknown>): string {
  const t = params.rsi_threshold_stufe1;
  const lib = params.liberal ? "liberal" : "strict";
  return typeof t === "number" ? `RSI ≤ ${t} (${lib})` : JSON.stringify(params);
}

export function SweepPanel() {
  const apiKey = localStorage.getItem(KEY_STORAGE) ?? "";
  const [asset, setAsset] = useState("^NDX");
  const [result, setResult] = useState<SweepResult | null>(null);
  const [running, setRunning] = useState(false);

  async function run() {
    if (!apiKey) return;
    setRunning(true);
    setResult(null);
    try {
      setResult(await adminApi.parameterSweep(apiKey, { asset: asset.trim() }));
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }

  if (!apiKey) {
    return (
      <p className="muted">
        Set the admin API key in the <strong>Bots</strong> tab to run parameter sweeps.
      </p>
    );
  }

  const best: SweepEntry | undefined = result?.results[0];

  return (
    <section>
      <div className="bot-auth">
        <label>
          Asset
          <input value={asset} onChange={(e) => setAsset(e.target.value)} placeholder="^NDX" />
        </label>
        <button onClick={run} disabled={running}>{running ? "Running…" : "Run sweep"}</button>
      </div>

      <p className="muted">
        Replays a grid of RSI thresholds over ~20 years and ranks them by mean forward return
        ({result?.horizon ?? "fwd_90d"}). Suggestions only — nothing is applied automatically.
      </p>

      {running && <p className="muted">Crunching ~20 years per threshold…</p>}

      {result && (
        <article className="card">
          <header>
            <h2>{result.asset}</h2>
            {best && (
              <span className="badge">
                best: {thresholdLabel(best.params)} · {pct(best.mean_forward_return)} mean
              </span>
            )}
          </header>
          <div className="bot-signals">
            <table>
              <thead>
                <tr><th>thresholds</th><th>triggers</th><th>mean ({result.horizon.replace("fwd_", "")})</th><th>win rate</th></tr>
              </thead>
              <tbody>
                {result.results.map((r, i) => (
                  <tr key={i} className={i === 0 ? "sweep-best" : ""}>
                    <td>{thresholdLabel(r.params)}</td>
                    <td>{r.total_signals}</td>
                    <td className={r.mean_forward_return != null && r.mean_forward_return >= 0 ? "pos" : "neg"}>
                      {pct(r.mean_forward_return)}
                    </td>
                    <td>{r.win_rate == null ? "—" : `${(r.win_rate * 100).toFixed(0)}%`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      )}
    </section>
  );
}
