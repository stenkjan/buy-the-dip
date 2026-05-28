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

## Phases

1. Signal/alert bot (this scaffold).
2. FastAPI service consuming the same engine.
3. React dashboard (this scaffold's `apps/web`).
4. Multi-user / auth / broker integration — out of scope.
