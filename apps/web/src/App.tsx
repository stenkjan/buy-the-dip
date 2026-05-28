import { useEffect, useState } from "react";
import { fetchSignals, type Signal } from "./api/client";
import { SignalCard } from "./components/SignalCard";

export function App() {
  const [signals, setSignals] = useState<Signal[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setSignals(await fetchSignals());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <main>
      <header className="app-header">
        <h1>Buy-the-Dip Signals</h1>
        <button onClick={load} disabled={loading}>{loading ? "Loading…" : "Refresh"}</button>
      </header>

      {error && <p className="error">Error: {error}</p>}

      <section className="grid">
        {signals?.map((s) => <SignalCard key={s.symbol} signal={s} />)}
      </section>

      <footer>
        <p>Educational tool. Not investment advice.</p>
      </footer>
    </main>
  );
}
