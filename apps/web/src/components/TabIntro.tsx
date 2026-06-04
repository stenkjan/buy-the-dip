import { useState } from "react";

type TabId = "signals" | "dca" | "timeline" | "bots" | "tuning";

interface IntroContent {
  /** One-line "what this tab is for". */
  summary: string;
  /** Bullet points: what it can do / how to read it. */
  points: string[];
  /** How it ties back to the buy-the-dip strategy foundation. */
  foundation?: string;
}

// Grounded in docs/strategy.md — the machine-checkable interpretation of the
// buy-the-dip strategy doc. Three market phases (Stufen) are set by where price
// sits relative to its long-term EMAs; a dip triggers when that phase's RSI
// drops to/below its threshold. Keep this copy in sync with the strategy rules.
const INTRO: Record<TabId, IntroContent> = {
  signals: {
    summary:
      "The live dip state for each tracked index (NDX, SPX) right now — a long-term accumulation aid, read-only, not advice.",
    points: [
      "This is a buy-the-dip strategy for slow, long-term accumulation (hold for years/decades) — not mid- or short-term trading. It flags when a strong market is temporarily oversold.",
      "Each card classifies the asset into one of three market phases (Stufen) by where price sits vs its 200-period EMAs: Stufe 1 = above the daily EMA200 (strong uptrend), Stufe 2 = between the weekly and daily EMA200 (uncertain), Stufe 3 = below the weekly EMA200 (deep bear — rare, best opportunities).",
      "A dip TRIGGERS when that phase's RSI falls to/below its threshold — RSI 12H for Stufe 1, RSI 1D for Stufe 2, RSI 1W for Stufe 3. Strict default is ≤ 30; liberal allows Daily ≤ 30.5, Weekly ≤ 32, and 12H ≤ 35 only during a macro-reclaim of both EMAs.",
      "The Tranche row is the strategy's suggested share of capital for that phase — deeper phase, bigger tranche (10–20% / 20–40% / 40–60%; total capital ≤ 50% of your liquidity).",
      "Deeper signals are rarer and get bought up fast (oversold phases last a day to ~3 weeks), so a Stufe 3 trigger is the strongest and most time-sensitive. The bot only surfaces the state — you make the call. Warten > FOMO.",
    ],
    foundation:
      "Foundation: the three-Stufen RSI/EMA rules from the buy-the-dip strategy doc (§11–13).",
  },
  dca: {
    summary:
      "How steady dollar-cost averaging (DCA) would have performed versus a single lump-sum buy, over the available price history.",
    points: [
      "Each card replays a fixed monthly contribution and compares it to investing the same total at once: total return, money-weighted CAGR, max drawdown, and annualised Sharpe.",
      "The chart plots cumulative invested vs the DCA portfolio value vs the lump-sum value over time.",
      "“vs lump-sum” shows whether spreading entries out helped or hurt for that asset.",
      "Results are published by the dca-backtest workflow; if a tab is empty, that workflow hasn't run yet.",
    ],
    foundation:
      "Foundation: the strategy accumulates via DCA (§3). Calendar DCA here is the passive baseline; buying the dips on the Signals/Timeline tabs concentrates those buys into oversold zones to lower the average entry price further.",
  },
  timeline: {
    summary:
      "Every historical dip trigger plotted on the price chart, so you can see how past dips actually played out.",
    points: [
      "Each dot is a past trigger, colored by Stufe (1 green, 2 amber, 3 red) and placed at its price.",
      "Hover a point for the RSI at that moment and the forward return 30 / 90 / 365 days later — i.e. did buying that dip pay off.",
      "Toggle the Stufe chips to filter which phases are shown; the badge notes strict vs liberal thresholds and the trigger count.",
      "Published by the history-timeline workflow; an empty tab means it hasn't run yet.",
    ],
    foundation:
      "Foundation: automates the manual “analyse historical data” workflow (§9–10) — the same Stufen/RSI triggers as Signals, evaluated across ~20 years of history.",
  },
  bots: {
    summary:
      "The control plane — create and manage paper or live bots that watch an asset and record signals using the strategy.",
    points: [
      "Connect with the admin API key first (stored locally in your browser); without it the control plane stays disabled.",
      "Create a bot per asset, then pause/enable it, switch it between paper and live, inspect its recorded signals, or delete it.",
      "Thresholds opens the per-bot editor for the Stufe 1/2/3 strict & liberal RSI values and the liberal toggle — exactly the parameters from the strategy foundation. Preview history replays ~20 years against your edits before you save.",
      "“■ Stop all” is the emergency switch: it pauses every bot and cancels their open orders.",
    ],
    foundation:
      "Foundation: each bot runs the buy-the-dip Stufen rules; its editable thresholds are the strategy's strict/liberal RSI defaults.",
  },
  tuning: {
    summary:
      "Parameter sweep — find which RSI thresholds would have produced the best dips historically.",
    points: [
      "Pick an asset and run; it replays a grid of RSI thresholds across ~20 years and ranks them by mean forward return.",
      "Each row shows the thresholds tried, how many triggers they produced, the mean forward return, and the win rate; the top row is the best-scoring set.",
      "Uses the admin API key set in the Bots tab.",
      "Suggestions only — nothing is applied to any bot automatically. Copy a winning set into a bot's Thresholds editor if you want to use it.",
    ],
    foundation:
      "Foundation: sweeps the same Stufen RSI thresholds the strategy defines, optimising them against historical forward returns.",
  },
};

const STORAGE_PREFIX = "btd_intro_hidden_";

export function TabIntro({ tab }: { tab: TabId }) {
  const storageKey = STORAGE_PREFIX + tab;
  const [open, setOpen] = useState(
    () => localStorage.getItem(storageKey) !== "1",
  );

  function toggle() {
    setOpen((prev) => {
      const next = !prev;
      if (next) localStorage.removeItem(storageKey);
      else localStorage.setItem(storageKey, "1");
      return next;
    });
  }

  const content = INTRO[tab];

  return (
    <section className={open ? "tab-intro is-open" : "tab-intro"} aria-label="What this tab does">
      <div className="tab-intro__head">
        <p className="tab-intro__summary">{content.summary}</p>
        <button
          type="button"
          className="tab-intro__toggle btn-secondary"
          aria-expanded={open}
          onClick={toggle}
        >
          {open ? "Hide" : "What is this?"}
        </button>
      </div>
      {open && (
        <>
          <ul className="tab-intro__points">
            {content.points.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
          {content.foundation && (
            <p className="tab-intro__foundation">{content.foundation}</p>
          )}
        </>
      )}
    </section>
  );
}
