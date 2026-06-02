# buy-the-dip

A modular signal-bot framework with a **buy-the-dip RSI/EMA strategy** for NDX
and SPX, plus a standalone web app (FastAPI + React) to view live indicator
state.

> Educational tool. Not investment advice. No buy/sell recommendations.

## What it does

Automates the manual TradingView workflow described in
[`docs/strategy.md`](docs/strategy.md): computes Wilder RSI on 12H / 1D / 1W
and EMA200 on daily/weekly closes for `^NDX` and `^GSPC`, then evaluates the
three-Stufen rule set. When a Stufe's RSI hits its threshold, it emits a
**signal** — surfaced via Telegram, console, or the web UI.

## Repo layout

```
src/
  bot_core/                # reusable framework (data, indicators, signals, alerts, state, backtest)
  strategies/buy_the_dip/  # the strategy plugin (implements bot_core.signals.Strategy)
  cli/                     # entrypoint for scheduled + manual GitHub Actions runs
apps/
  api/                     # FastAPI HTTP API around the engine
  web/                     # React + Vite dashboard
.github/workflows/         # ci.yml, scheduled.yml, manual.yml
config/default.toml        # behavioural config (no secrets)
docs/                      # architecture + strategy
tests/                     # pytest
```

Adding another bot (gold, BTC, world ETF) means a new subpackage under
`src/strategies/`, not a rewrite. See [`docs/architecture.md`](docs/architecture.md).

## Quick start

### Engine + CLI

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
python -m cli.main --mode manual --asset both
```

### Backtest

```bash
python -m cli.backtest --asset ^NDX --start 2000-01-01
# writes backtest/ndx.csv (one row per triggered signal with forward returns
# at 30/90/180/365 days) and backtest/ndx.summary.json
python -m cli.backtest --asset ^GSPC --strict   # strict thresholds only
```

### Indicator validation (TradingView spot-check)

Pre-flight before trusting backtest output — see [`docs/validation.md`](docs/validation.md).
Fill in the expected RSI/EMA values from TradingView for a handful of historic
dates in `fixtures/tradingview.csv`, then:

```bash
python -m cli.validate_tv
# RSI within ±0.5 absolute, EMA within ±1% — exits non-zero on mismatch.
```

### API

```bash
uvicorn apps.api.main:app --reload
# open http://localhost:8000/docs
```

### Web

```bash
cd apps/web
npm install
npm run dev
# open http://localhost:5173
```

By default the dashboard fetches `https://raw.githubusercontent.com/<owner>/<repo>/data/signals.json`,
the static snapshot produced 2× daily by the scheduled GitHub Action. For local
dev against the FastAPI server set `VITE_SIGNALS_URL=http://localhost:8000/signals`.

## Architecture: static-JSON dashboard

The scheduled workflow runs `cli.snapshot` after the alert pass and force-pushes
the resulting `signals.json` to the `data` branch. The deployed dashboard is a
static Vite build that fetches that JSON directly from GitHub's raw CDN. This
keeps the React app fully static (deployable to Vercel/Netlify/GH Pages with no
serverless function) and avoids running pandas + yfinance on every page load.
The FastAPI server in `apps/api/` stays available for local dev and is the
forward-compat path to dynamic queries.

## GitHub Actions

| Workflow        | Trigger                              | Purpose                                   |
| --------------- | ------------------------------------ | ----------------------------------------- |
| `ci.yml`        | push / PR to `main`                  | Lint, typecheck, pytest, web build        |
| `scheduled.yml` | cron `0 6,18 * * *` UTC (12H rhythm) | Run signal check, push alert on trigger   |
| `manual.yml`    | `workflow_dispatch`                  | One-off run from Actions tab              |

## Secrets — DO NOT COMMIT

This repo is public. All secrets come from environment variables; in CI from
`Settings → Secrets and variables → Actions`:

- `TELEGRAM_TOKEN` — Telegram bot token (optional)
- `TELEGRAM_CHAT_ID` — Telegram chat to send to (optional)
- `DATA_API_KEY` — production data provider key (Polygon / Tiingo)
- `POSTGRES_URL` / `POSTGRES_URL_NON_POOLING` — Vercel Postgres connection
  strings (optional, used by the DB layer + alembic). Fall back to local SQLite
  (`buythedip.db`) when unset so local dev and CI keep working.
- `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` — Alpaca credentials (paper or
  live). Required only when instantiating `AlpacaBroker`.

`.env.example` lists every variable. `.gitignore` blocks `.env`, `.env.*`,
`secrets/`, `*.pem`, `*.key`. If you ever paste a token, rotate it
immediately — never commit and `git revert`.

## Persistence & broker scaffolding (Phase 4)

The `bot_core.db` package adds SQLModel tables for bots, signals, orders,
positions, audit log and parameter-search runs, plus a thin functional
repository in `bot_core.db.repository`. The engine prefers `POSTGRES_URL` for
app traffic and `POSTGRES_URL_NON_POOLING` for migrations; both are optional —
without them everything falls back to a local SQLite file.

Schema migrations are managed with Alembic:

```bash
alembic upgrade head      # apply all migrations
alembic downgrade -1      # roll back one
alembic revision -m "msg" # author a new revision
```

The broker abstraction lives in `bot_core.brokers`: a `Broker` Protocol with
frozen `Account` / `BrokerPosition` / `BrokerOrder` dataclasses, and an
`AlpacaBroker` implementation that lazily imports `alpaca-py` and supports
both `mode="paper"` and `mode="live"`. Sizing is a pure helper in
`bot_core.execution.size_order`. No code path wires the broker into the CLI
or API yet — that lands in Phase 5.

## Historical data + DCA

`bot_core.data.AlpacaSource` implements the `DataSource` Protocol against the
Alpaca Market Data API and is the recommended source for monthly / daily
backtests when you have Alpaca credentials. It auto-maps the Yahoo-style
index symbols used elsewhere in the repo (`^NDX`, `^GSPC`, `^IXIC`, `^DJI`)
to the corresponding ETF proxies (`QQQ`, `SPY`, `ONEQ`, `DIA`) via
`config/alpaca_symbols.toml` — Alpaca only trades equities/ETFs, not indices
directly, and the ETFs track 1:1 within <0.05% p.a.

```bash
python -m cli.dca --asset ^NDX  --start 1996-01-01 --monthly 1000 --risk-free 0.02
python -m cli.dca --asset ^GSPC --start 1996-01-01 --monthly 1000 --risk-free 0.02
```

Output: `backtest/dca-<asset>.csv` with one row per month
(`month_close`, `shares_bought_this_month`, `cum_shares`, `cum_invested`,
`portfolio_value`) plus a `.summary.json` carrying aggregates (total invested,
final value, money-weighted CAGR via bisected IRR, max drawdown, annualised
Sharpe, and a lump-sum buy-and-hold benchmark for comparison).

**Free-tier caveat:** Alpaca's free IEX feed returns roughly 2016+ history for
most ETFs and is delayed ~15 minutes. Algo Trader Plus (currently $99/mo, SIP
feed) returns inception-to-present. When the request's `start` predates what
the endpoint can serve, the CLI logs a warning and proceeds with the
available range — the truncation is also recorded in the summary JSON.

The `dca-backtest` GitHub Actions workflow (`workflow_dispatch`) runs the same
CLI from CI using `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` repo secrets and
uploads the CSV + summary as an artifact.

## Tech stack

- Python 3.13, pandas, FastAPI, pydantic v2, yfinance, httpx, pytest, ruff
- React 19, TypeScript 5, Vite 6
- GitHub Actions (Node 24, setup-python@v6, checkout@v6, cache@v5, upload-artifact@v7)

## License

MIT. See [LICENSE](LICENSE). Educational use; no warranty.
