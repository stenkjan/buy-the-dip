import { useEffect, useState } from "react";
import {
  fetchDca,
  fetchHistory,
  fetchSignals,
  fetchTimeline,
  type DcaSummary,
  type HistoryPayload,
  type SignalsPayload,
  type TimelinePayload,
} from "./api/client";
import { BotsPanel } from "./components/BotsPanel";
import { DcaCard } from "./components/DcaCard";
import { SignalCard } from "./components/SignalCard";
import { SignalTimeline } from "./components/SignalTimeline";
import { SweepPanel } from "./components/SweepPanel";
import { TabIntro } from "./components/TabIntro";
import { relativeTime } from "./format";

type Tab = "signals" | "dca" | "timeline" | "bots" | "tuning";

const TABS: { id: Tab; label: string }[] = [
  { id: "signals", label: "Signals" },
  { id: "dca", label: "DCA backtest" },
  { id: "timeline", label: "Signal timeline" },
  { id: "bots", label: "Bots" },
  { id: "tuning", label: "Tuning" },
];

export function App() {
  const [payload, setPayload] = useState<SignalsPayload | null>(null);
  const [history, setHistory] = useState<HistoryPayload | null>(null);
  const [dca, setDca] = useState<DcaSummary[]>([]);
  const [timelines, setTimelines] = useState<TimelinePayload[]>([]);
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
      // DCA + timelines are opt-in (manual workflows); fetch per asset, keep hits.
      const [dcaResults, timelineResults] = await Promise.all([
        Promise.all(signals.signals.map((s) => fetchDca(s.symbol))),
        Promise.all(signals.signals.map((s) => fetchTimeline(s.symbol))),
      ]);
      setDca(dcaResults.filter((d): d is DcaSummary => d !== null));
      setTimelines(timelineResults.filter((t): t is TimelinePayload => t !== null));
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
  const signals = payload?.signals ?? [];
  const triggeredCount = signals.filter((s) => s.triggered).length;
  const initialLoading = loading && !payload;

  return (
    <main>
      <header className="app-header">
        <div>
          <h1>Buy-the-Dip Signals</h1>
          <p className="tagline">RSI/EMA dip signals for NDX &amp; SPX — read-only, not advice.</p>
        </div>
        <button onClick={load} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
      </header>

      <nav className="tabs" role="tablist" aria-label="Dashboard views">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            className={tab === t.id ? "tab is-active" : "tab"}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {error && <p className="error" role="alert">Error: {error}</p>}

      {generated && (
        <p className="status-line">
          {tab === "signals" && signals.length > 0 && (
            <span className={triggeredCount > 0 ? "pill pill--on" : "pill"}>
              {triggeredCount > 0
                ? `${triggeredCount} of ${signals.length} triggered`
                : "no active triggers"}
            </span>
          )}
          <span className="muted" title={generated.toUTCString()}>
            updated {relativeTime(generated)}
          </span>
        </p>
      )}

      {!initialLoading && <TabIntro tab={tab} />}

      {initialLoading && (
        <section className="grid" aria-busy="true">
          <div className="card skeleton" />
          <div className="card skeleton" />
        </section>
      )}

      {!initialLoading && tab === "signals" && (
        <section className="grid">
          {signals.map((s) => (
            <SignalCard key={s.symbol} signal={s} history={history?.assets[s.symbol]} />
          ))}
        </section>
      )}

      {!initialLoading && tab === "dca" && (
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

      {!initialLoading && tab === "timeline" && (
        <section className="grid">
          {timelines.length > 0 ? (
            timelines.map((t) => <SignalTimeline key={t.asset} timeline={t} />)
          ) : (
            <p className="muted">
              No signal timeline published yet. Run the <code>history-timeline</code> workflow
              to generate them.
            </p>
          )}
        </section>
      )}

      {!initialLoading && tab === "bots" && <BotsPanel />}

      {!initialLoading && tab === "tuning" && <SweepPanel />}

      <footer>
        <p>Educational tool. Not investment advice. No buy/sell recommendations.</p>
      </footer>
    </main>
  );
}
