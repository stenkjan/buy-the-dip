import { useEffect, useState } from "react";
import { fetchHistory, fetchSignals, type HistoryPayload, type SignalsPayload } from "./api/client";
import { SignalCard } from "./components/SignalCard";

export function App() {
  const [payload, setPayload] = useState<SignalsPayload | null>(null);
  const [history, setHistory] = useState<HistoryPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      // History is best-effort and must not block the signal cards.
      const [signals, hist] = await Promise.all([fetchSignals(), fetchHistory()]);
      setPayload(signals);
      setHistory(hist);
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

      {error && <p className="error">Error: {error}</p>}

      {generated && (
        <p className="muted">Last updated: {generated.toUTCString()}</p>
      )}

      <section className="grid">
        {payload?.signals.map((s) => (
          <SignalCard key={s.symbol} signal={s} history={history?.assets[s.symbol]} />
        ))}
      </section>

      <footer>
        <p>Educational tool. Not investment advice.</p>
      </footer>
    </main>
  );
}
