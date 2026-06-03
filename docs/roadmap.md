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
| **5c — Historical signal timeline** | `cli.history` replays the real per-bar strategy (same engine as `cli.backtest`, incl. macro-reclaim) over ~20 years and records every triggered bar with Stufe, RSI, threshold, price and forward returns (30/90/180/365d). The manual `history-timeline.yml` workflow publishes `history/<asset>.json`. A "Signal timeline" tab plots triggers over price (one marker per trigger, colored by Stufe, per-Stufe filter, tooltip with RSI + forward returns). |

### Dashboard data files (published to the `data` branch)

| File | Producer | Shape |
| ---- | -------- | ----- |
| `signals.json` | `cli.snapshot --output` | `{schema_version, generated_at, signals[]}` — current Stufe/RSI/trigger per asset. |
| `history.json` | `cli.snapshot --history-output` | `{schema_version, generated_at, assets:{symbol: bar[]}}` — per-bar `timestamp, close, ema200_daily, ema200_weekly, rsi_1d, rsi_1w, stufe, triggered`. |
| `dca/<asset>.json` | `cli.dca` + `dca-backtest.yml` | KPI aggregates + `series[]` of `{month, cum_invested, dca_value, lump_value}`. Published per manual workflow run. |
| `history/<asset>.json` | `cli.history` + `history-timeline.yml` | `{summary, signals[]}` — one record per triggered bar with `timestamp, stufe, rsi_value, rsi_threshold, price, fwd_30d/90d/180d/365d`. Published per manual workflow run. |

The per-bar `triggered` flag in `history.json` is a chart-overlay
approximation: it tests the daily RSI for Stufe 1/2 and weekly RSI for Stufe 3
against the live strategy thresholds, ignoring the contextual macro-reclaim
relaxation. The precise 12H-RSI signal timeline is phase 5c.

## In progress: 6 — DB-backed UI and execution (~2-3 weeks)

This is where the dashboard moves from read-only to control plane. The
foundation (DB schema, broker adapter) is already in place from Phase 4.

### Backend

- **[shipped] Bot control-plane API** — `GET/POST/PATCH/DELETE /bots`,
  `POST /bots/{id}/toggle`, `GET /bots/{id}/signals`, `GET /bots/{id}/positions`.
  Gated behind a single `API_KEY` env (constant-time `X-API-Key` check); when
  `API_KEY` is unset the endpoints return 503 so the public deploy stays
  read-only. CORS now allows the mutating verbs.
- **[shipped] Signal persistence** — `cli.snapshot --persist` writes a
  `SignalRecord` per asset via `repository.record_signal`, attaching to a
  stable bot per asset (`get_or_create_bot`). Opt-in; the static JSON path is
  untouched and the public scheduled run keeps working without a database.
- **[shipped] `POST /backtest`** — admin-gated; replays the strategy for an
  asset + optional partial threshold `config` over history and returns the
  triggered signals with forward returns (powers the threshold preview).
- **[next] `POST /parameter-sweep`** (phase 8 learning loop).
- The API server stays on Vercel serverless for now — cold start is
  acceptable for low-traffic admin use.

### Web

- **[shipped] "Bots" tab**: list/create/enable-pause/switch-mode/delete bots
  and view recent signal records, against the control-plane API. Admin key is
  entered in the UI (stored in localStorage) and sent as `X-API-Key`; base URL
  via `VITE_API_BASE_URL`.
- **[shipped] Threshold editor** in the Bots tab: edits the per-bot
  `config_json` RSI thresholds (strict + liberal, macro-reclaim window, liberal
  toggle) via `PATCH /bots/{id}`. The executor builds the strategy from this
  config. A **"Preview history"** button replays ~20 years via `POST /backtest`
  and shows trigger counts per Stufe + forward-return win rates for the entered
  thresholds.
- Live indicator state still served from the static `signals.json` — the
  CRUD API is only used for configuration writes.

### Broker integration

- **[shipped] Paper-trade end-to-end** via `AlpacaBroker`. `bot_core.execution.execute_signal`
  runs guards → `size_order` → paper order → `OrderRecord` + audit. The
  `cli.trade` CLI (and manual `paper-trade.yml`, dry-run by default) evaluates
  each enabled bot with its own thresholds and places paper buys. **Live mode
  is refused** until the validation prerequisite (phase 7) is met.
- **[shipped] Risk guards** in `bot_core.execution.guards`: max-% per trade,
  cool-down between buys, cash-floor, daily trade cap, drawdown circuit breaker
  (configurable per bot via `config_json.guards`).
- **[shipped] Order-status refresh** — `bot_core.execution.refresh_orders` +
  `cli.refresh` poll open orders, update `OrderRecord` (status/fill) with an
  `order_filled` audit, and sync the bot's `Position` from the broker. Runs
  after a live paper-trade in `paper-trade.yml`.

## Then: 7 — Live trading (~1 week)

- Per-bot `mode = paper | live` field. **[shipped]**
- **[shipped]** Kill-switch endpoint `POST /emergency-stop` (+ "Stop all" button
  in the Bots tab) pauses every bot and best-effort cancels open orders, with a
  mandatory `kill_switch` audit row. Pausing works even when the broker is
  unreachable.
- **[shipped]** Audit rows for order submit/fill/block already written by the
  executor + refresh job.
- **[gated]** Actual live order placement stays refused in the executor until
  the validation prerequisite below is met.
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
