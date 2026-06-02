# Architecture

The repo is structured as a **modular framework + strategy plugin + apps** so the
same engine can drive other indicator-based bots (gold, BTC, world ETFs) by
swapping the strategy plugin.

```
+--------------+    +-------------------+    +---------------+
|  Data Layer  | -> | Indicator Engine  | -> | Signal Logic  |
+--------------+    +-------------------+    +---------------+
                                                    |
                          +-------------------------+
                          v
                   +--------------+    +---------------------------+
                   | Output/Alert | -> | (optional) Broker / Order |
                   +--------------+    +---------------------------+
        ^ Backtest module reuses Data Layer + Indicator Engine + Signal Logic
          offline against history (from year 2000).
```

## Layers (all in `src/bot_core/`)

| Layer       | Module                  | Responsibility                                  | Pluggable via    |
| ----------- | ----------------------- | ----------------------------------------------- | ---------------- |
| Data        | `bot_core.data`         | Fetch OHLCV (yfinance / Polygon / …)            | `DataSource` protocol |
| Indicators  | `bot_core.indicators`   | Wilder RSI, EMA, OHLC resampling                | Pure functions    |
| Signals     | `bot_core.signals.base` | Strategy contract                               | `Strategy` protocol |
| Alerts      | `bot_core.alerts`       | Telegram, console, …                            | `Notifier` protocol |
| State       | `bot_core.state`        | Idempotency (avoid duplicate alerts)            | `StateStore` protocol |
| Backtest    | `bot_core.backtest`     | Replay strategy over history                    | —                |

## Strategy plugins (`src/strategies/`)

A strategy is anything that implements `Strategy.evaluate(AssetData) -> Signal`.
`buy_the_dip` is the first; adding another (e.g. `dca_gold`) means a new
subpackage exporting `get_strategy()`. The CLI and API select strategies by
name from `config/default.toml`.

## Apps

| App             | Path        | Purpose                                                  |
| --------------- | ----------- | -------------------------------------------------------- |
| CLI             | `src/cli/`  | Entrypoint for GitHub Actions (scheduled + manual runs)  |
| FastAPI service | `apps/api/` | HTTP API exposing `/signals` for the web app             |
| React frontend  | `apps/web/` | Standalone web dashboard                                 |

## Configuration

- Behavioural settings: `config/default.toml` (committed, no secrets).
- Secrets: environment variables only — `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`,
  `DATA_API_KEY`. In CI these come from `Settings → Secrets and variables →
  Actions`. The repo is public — never commit them.

## Persistence layer (`src/bot_core/db/`)

Introduced in Phase 4 as additive scaffolding — no existing module imports it
yet. Models use SQLModel (Pydantic v2 + SQLAlchemy 2.0) and JSON columns for
flexible payloads.

| Table           | Purpose                                                   |
| --------------- | --------------------------------------------------------- |
| `bot`           | One row per running strategy instance (paper or live).    |
| `signal_record` | Every evaluation, triggered or not — append-only audit.   |
| `order_record`  | Submitted orders + their broker-side lifecycle.           |
| `position`      | Latest broker-reported position per (bot, symbol).        |
| `audit_log`     | Free-form event log (`event_type`, `message`, `context`). |
| `parameter_run` | Backtest results for one (strategy, params) tuple.        |

Engine resolution: `POSTGRES_URL` is the pooled URL for app traffic,
`POSTGRES_URL_NON_POOLING` is the direct URL used by Alembic. Both are
optional — without them a local SQLite file (`buythedip.db`) is used.

Repository helpers in `bot_core.db.repository` are top-level functions
(`create_bot`, `record_signal`, `record_order`, `upsert_position`, `audit`, …)
so no DAO class boilerplate is needed.

Schema migrations live in `migrations/` (Alembic, initial revision
`0001_initial`). The scheduled GitHub Action runs `alembic upgrade head` when
either Postgres secret is set, and silently skips otherwise.

## Broker abstraction (`src/bot_core/brokers/`)

A `Broker` Protocol with frozen `Account`, `BrokerPosition`, `BrokerOrder`
dataclasses. The first implementation, `AlpacaBroker`, lazily imports
`alpaca-py` and accepts `mode: Literal["paper", "live"]`. Credentials come
from `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` (constructor args override).
Alpaca exceptions are wrapped in `BrokerError`. No CLI / API wiring yet —
that's Phase 5.

`bot_core.execution.size_order` is a pure helper that picks a notional within
the strategy's tranche range based on an `aggressiveness` parameter and
returns `(qty, target_value)` for the broker adapter to execute.

## Phases

1. Signal/alert bot (this scaffold).
2. FastAPI service consuming the same engine.
3. React dashboard (this scaffold's `apps/web`).
4. **DB persistence + broker abstraction (additive scaffold — Phase 4).**
5. CRUD API + wire DB/broker into CLI/API — next.
6. Live broker integration, multi-user / auth — later.
