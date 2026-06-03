import { useEffect, useState } from "react";
import {
  fetchDca,
  fetchHistory,
  fetchSignals,
  type DcaSummary,
  type HistoryPayload,
  type SignalsPayload,
} from "./api/client";
import { DcaCard } from "./components/DcaCard";
import { SignalCard } from "./components/SignalCard";

type Tab = "signals" | "dca";

export function App() {
  const [payload, setPayload] = useState<SignalsPayload | null>(null);
  const [history, setHistory] = useState<HistoryPayload | null>(null);
  const [dca, setDca] = useState<DcaSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<Tab>("signals");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      // History is best-effort and must not block the signal cards.
      const [signals, hist] = await Promise.all([fetchSignals(), fetchHistory()]);
      setPayload(signals);
      setHistory(hist);
      // DCA results are opt-in (manual workflow); fetch per asset, keep the hits.
      const results = await Promise.all(signals.signals.map((s) => fetchDca(s.symbol)));
      setDca(results.filter((d): d is DcaSummary => d !== null));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const generated = payload ? new Date(payload.generated_at) : null;

  return (
    <main>
      <header className="app-header">
        <h1>Buy-the-Dip Signals</h1>
        <button onClick={load} disabled={loading}>{loading ? "Loading…" : "Refresh"}</button>
      </header>

      <nav className="tabs">
        <button
          className={tab === "signals" ? "tab is-active" : "tab"}
          onClick={() => setTab("signals")}
        >
          Signals
        </button>
        <button
          className={tab === "dca" ? "tab is-active" : "tab"}
          onClick={() => setTab("dca")}
        >
          DCA backtest
        </button>
      </nav>

      {error && <p className="error">Error: {error}</p>}

      {generated && (
        <p className="muted">Last updated: {generated.toUTCString()}</p>
      )}

      {tab === "signals" && (
        <section className="grid">
          {payload?.signals.map((s) => (
            <SignalCard key={s.symbol} signal={s} history={history?.assets[s.symbol]} />
          ))}
        </section>
      )}

      {tab === "dca" && (
        <section className="grid">
          {dca.length > 0 ? (
            dca.map((d) => <DcaCard key={d.asset} dca={d} />)
          ) : (
            <p className="muted">
              No DCA results published yet. Run the <code>dca-backtest</code> workflow to
              generate them.
            </p>
          )}
        </section>
      )}

      <footer>
        <p>Educational tool. Not investment advice.</p>
      </footer>
    </main>
  );
}
