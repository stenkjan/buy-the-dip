# Roadmap

Where the project stands today and what the natural next steps are. Phases
4 and 5 are scaffolded but not user-visible yet; the rest of this doc is the
plan for getting them onto the dashboard and then into autonomous execution.

## Shipped

| Phase | Summary |
| ----- | ------- |
| 1 — Engine + alerts | `bot_core` framework (Data / Indicator / Signal / Alert / State / Backtest), `strategies.buy_the_dip`, Telegram alerts, idempotent state. |
| 2 — API | FastAPI service exposing `/health` and `/signals` (currently optional — dashboard uses static JSON). |
| 3 — Static dashboard | React 19 + Vite 6 deployment that reads `signals.json` from the `data` branch via raw.githubusercontent.com. |
| 4 — DB + broker scaffold | SQLModel tables (`bot`, `signal_record`, `order_record`, `position`, `audit_log`, `parameter_run`), Alembic migrations on Vercel Postgres, `AlpacaBroker` adapter (paper default). Schema is live but not written to yet. |
| 5a-prep — Historical data | `AlpacaSource` (StockHistoricalDataClient), `^NDX→QQQ` / `^GSPC→SPY` symbol mapping, `cli.dca` backtest CLI with IRR / Sharpe / max-DD / lump-sum benchmark, manual `dca-backtest.yml` workflow. |

## Next: 5a — Charts in the dashboard (~1-2 days)

Goal: make the existing signal cards interpretable at a glance by adding
the same view a trader has in TradingView, but read-only and auto-refreshed.

### Engine

- Extend `cli.snapshot` so that it also writes `history.json` per asset to
  the `data` branch — last ~500 daily bars with columns:
  `timestamp, close, ema200_daily, ema200_weekly, rsi_1d, rsi_1w`.
- Adds ~2 seconds to the scheduled run; storage cost on the `data` branch
  is negligible (~50 KB per asset per snapshot).

### Web (`apps/web`)

- `npm i recharts` — small, React-native, free for commercial use.
- For each asset card add two stacked panels:
  - **Price panel**: candles or close-only line + EMA200 daily (thin red) +
    EMA200 weekly (thick red). Horizontal lines at recent high/low.
  - **RSI panel**: RSI 1D line + horizontal line at 30 (and at 70 if we want
    to show overbought too).
- Overlay historical Stufe triggers as colored markers on the price line
  (Stufe 1 green, Stufe 2 yellow, Stufe 3 red).
- Mobile-responsive — the existing grid already handles stacking; the chart
  components use percentage widths.

### Acceptance

- Refreshing the dashboard shows price + EMAs + RSI per asset for the
  visible window.
- A historic Stufe-1 trigger from 2024 is visible as a marker.
- Web build stays under the current bundle-size budget (~200 KB gzipped
  acceptable).

## Then: 5b — DCA results on the dashboard (~1 day)

Goal: the DCA backtest results land in the UI instead of staying as an
Actions artifact.

- Modify `dca-backtest.yml` to push the summary JSON to the `data` branch
  under `dca/<asset>.json` after the run (same publish pattern used by the
  scheduled signal check).
- New web route `/dca` (or a tab inside the main view) showing:
  - KPIs: total invested, final value, total return %, money-weighted CAGR,
    max drawdown, Sharpe (annualised).
  - Two-line chart: DCA equity curve vs lump-sum invested at start.
  - Free-tier disclaimer when `history_truncation_warning` is present.
- Optional: a &#34;Recompute&#34; button in the UI that triggers the workflow via
  the GitHub Actions REST API (`POST /repos/.../actions/workflows/.../dispatches`)
  using a `repository_dispatch` token stored in `apps/web` as a Vercel
  env var.

## Then: 5c — Historical signal timeline (~1 day, optional)

Goal: show what the strategy would have flagged historically — directly
relevant to validating the engine before any autonomous execution.

- New `cli.history` that runs the backtest over the last ~20 years and
  records each triggered bar with `timestamp, stufe, rsi, threshold, price,
  forward_30d, forward_90d, forward_365d`.
- Push result as `data/history/<asset>.json`.
- Web timeline view per asset: one marker per trigger, tooltip with all
  fields above. Filter by Stufe.

## Then: 6 — DB-backed UI and execution (~2-3 weeks)

This is where the dashboard moves from read-only to control plane. The
foundation (DB schema, broker adapter) is already in place from Phase 4.

### Backend

- Wire `cli.snapshot` and `cli.main` to **also** write `SignalRecord` rows
  via `bot_core.db.repository.record_signal`. Static JSON keeps being
  produced for the dashboard.
- Build the CRUD API on top of the DB:
  `GET/POST/PATCH /bots`, `POST /bots/{id}/toggle`, `GET /bots/{id}/positions`,
  `POST /backtest`, `POST /parameter-sweep`.
- Single-user JWT auth (single `API_KEY` env). Sufficient for solo use
  until distribution becomes a thing.
- The API server stays on Vercel serverless for now — cold start is
  acceptable for low-traffic admin use.

### Web

- New &#34;Bots&#34; section: list of configured bots, create/edit/pause from the UI.
- Threshold editor with a &#34;preview historical signals filtered by this
  threshold&#34; chart.
- Live indicator state still served from the static `signals.json` — the
  CRUD API is only used for configuration writes.

### Broker integration

- Paper-trade end-to-end via `AlpacaBroker`. Sizing comes from
  `bot_core.execution.size_order` with allocation from the strategy doc
  table.
- Persist every `place_order` call as `OrderRecord` with the broker
  response payload. Schedule a status-refresh job that polls open orders.
- Risk guards in `bot_core.execution.guards`: max-% per trade, cool-down
  between buys, cash-floor, daily trade cap, drawdown circuit breaker.

## Then: 7 — Live trading (~1 week)

- Per-bot `mode = paper | live` field.
- Kill-switch endpoint `/emergency-stop` that pauses all bots and cancels
  open orders.
- Mandatory audit-log row for every order regardless of fill state.
- **Required prerequisite**: TradingView spot-check in
  [`docs/validation.md`](validation.md) completed; backtest hit-rate
  against historical crashes within ±0.5 RSI of TradingView numbers.

## Then: 8 — Learning loop (~3-5 days)

- Scheduled job runs `parameter_run` rows for a grid of threshold and EMA
  variations on the latest history.
- Web surface: &#34;Threshold 28 instead of 30 would have produced X% more
  return with Y% less drawdown over the last 5 years.&#34;
- Suggestions only — humans accept/reject. The bot never auto-mutates its
  own config.

## Out of scope (for now)

- Multi-user / sharing — regulatory implications in EU under MiFID II.
- Live equity trading via Alpaca for AT/EU residents — Alpaca only supports
  US equities for US-tax-resident accounts. Either stick to paper or swap
  the broker adapter for IBKR (the same `Broker` Protocol works without
  engine changes).
- IBKR adapter — only when live trading is needed.
- Crypto trading via Alpaca Crypto LLC — interesting because it's the only
  Alpaca path live-tradable from AT, but would require a new strategy plug
  (the current `buy_the_dip` thresholds were tuned to equity indices).
