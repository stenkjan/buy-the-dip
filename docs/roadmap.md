# Roadmap

Where the project stands today and what the natural next steps are. The DB +
broker scaffold (phase 4) is in place but not yet user-visible; the rest of
this doc is the plan for getting it onto the dashboard and then into autonomous
execution.

## Shipped

| Phase | Summary |
| ----- | ------- |
| 1 — Engine + alerts | `bot_core` framework (Data / Indicator / Signal / Alert / State / Backtest), `strategies.buy_the_dip`, Telegram alerts, idempotent state. |
| 2 — API | FastAPI service exposing `/health` and `/signals` (currently optional — dashboard uses static JSON). |
| 3 — Static dashboard | React 19 + Vite 6 deployment that reads `signals.json` from the `data` branch via raw.githubusercontent.com. |
| 4 — DB + broker scaffold | SQLModel tables (`bot`, `signal_record`, `order_record`, `position`, `audit_log`, `parameter_run`), Alembic migrations on Vercel Postgres, `AlpacaBroker` adapter (paper default). Schema is live but not written to yet. |
| 5a-prep — Historical data | `AlpacaSource` (StockHistoricalDataClient), `^NDX→QQQ` / `^GSPC→SPY` symbol mapping, `cli.dca` backtest CLI with IRR / Sharpe / max-DD / lump-sum benchmark, manual `dca-backtest.yml` workflow. |
| **5a — Charts in the dashboard** | `cli.snapshot --history-output` publishes `history.json` (last ~500 daily bars: close, EMA200 1D/1W, RSI 1D/1W, per-bar Stufe + trigger flag) to the `data` branch alongside `signals.json`. Each web signal card renders a price panel (close + both EMA200s, colored Stufe-trigger markers) and an RSI panel (RSI 1D with 30/70 reference lines) via recharts. |
| **5b — DCA results in the dashboard** | `cli.dca` writes `dca-<asset>.dashboard.json` (KPIs + monthly DCA / lump-sum / invested equity series); the manual `dca-backtest.yml` workflow publishes it to the `data` branch under `dca/<asset>.json`. A "DCA backtest" tab in the web app shows per-asset KPIs (invested, final value, return, money-weighted CAGR, max-DD, Sharpe, vs lump-sum) plus a DCA-vs-lump-sum equity chart, with a free-tier disclaimer when `history_truncation_warning` is present. |

### Dashboard data files (published to the `data` branch)

| File | Producer | Shape |
| ---- | -------- | ----- |
| `signals.json` | `cli.snapshot --output` | `{schema_version, generated_at, signals[]}` — current Stufe/RSI/trigger per asset. |
| `history.json` | `cli.snapshot --history-output` | `{schema_version, generated_at, assets:{symbol: bar[]}}` — per-bar `timestamp, close, ema200_daily, ema200_weekly, rsi_1d, rsi_1w, stufe, triggered`. |
| `dca/<asset>.json` | `cli.dca` + `dca-backtest.yml` | KPI aggregates + `series[]` of `{month, cum_invested, dca_value, lump_value}`. Published per manual workflow run. |

The per-bar `triggered` flag in `history.json` is a chart-overlay
approximation: it tests the daily RSI for Stufe 1/2 and weekly RSI for Stufe 3
against the live strategy thresholds, ignoring the contextual macro-reclaim
relaxation. The precise 12H-RSI signal timeline is phase 5c.

## Next: 5c — Historical signal timeline (~1 day, optional)

Goal: show what the strategy would have flagged historically — directly
relevant to validating the engine before any autonomous execution. Unlike the
5a chart overlay, this uses the real 12H-RSI evaluation.

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

- New "Bots" section: list of configured bots, create/edit/pause from the UI.
- Threshold editor with a "preview historical signals filtered by this
  threshold" chart.
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
- Web surface: "Threshold 28 instead of 30 would have produced X% more
  return with Y% less drawdown over the last 5 years."
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
