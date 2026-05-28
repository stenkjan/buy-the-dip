import { useEffect, useState } from "react";
import { fetchSignals, type SignalsPayload } from "./api/client";
import { SignalCard } from "./components/SignalCard";

export function App() {
  const [payload, setPayload] = useState<SignalsPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setPayload(await fetchSignals());
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
        {payload?.signals.map((s) => <SignalCard key={s.symbol} signal={s} />)}
      </section>

      <footer>
        <p>Educational tool. Not investment advice.</p>
      </footer>
    </main>
  );
}
