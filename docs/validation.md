# Validation: TradingView spot-check

The architecture doc is explicit: **before trusting any backtest output, validate
the indicator engine against TradingView on a handful of historical bars.** This
catches Wilder-vs-Cutler RSI bugs, EMA seeding bugs, and resample/timezone bugs
that are invisible in unit tests but make every signal slightly wrong.

This is a manual checklist. It takes ~15 minutes per asset.

## Procedure

1. Open TradingView, add the asset (`NDX`, `SPX`) to a chart.
2. Apply EMA200 on Daily and EMA200 on Weekly, plus three RSI(14) panels at
   12H / 1D / 1W (settings per `docs/strategy.md`).
3. Pick the dates listed in [`fixtures/tradingview.csv`](../fixtures/tradingview.csv).
4. For each date, hover the daily candle close and read off:
   - close price
   - EMA200 daily, EMA200 weekly
   - RSI 12H / 1D / 1W
5. Fill in the empty cells in `fixtures/tradingview.csv`.
6. Run `python -m cli.validate_tv` (Phase C+). The tool fetches the same dates
   via yfinance, recomputes our indicators, and asserts each value is within
   tolerance (default ±0.5 for RSI, ±1.0% for EMA).

## Suggested dates

- **2008-10-10** Stufe-3 territory (deep below weekly EMA200) during the GFC.
- **2020-03-23** COVID crash bottom; weekly RSI was deeply oversold.
- **2022-06-17** mid-cycle correction, Stufe-2 region.
- **2024-08-05** the yen-carry unwind; brief Stufe-1 dip.
- **2025-04-08** if present — any recent cluster the user wants to test.

Two or three dates per crash is enough — the goal is "the numbers match", not
exhaustive coverage.

## Tolerance & failure modes

| Symptom in mismatch | Likely cause |
| ------------------- | ------------ |
| Constant RSI offset (~5–8 pts) | Smoothing — Wilder vs simple/exponential. We use Wilder. |
| RSI drifts further away at older dates | Seeding — first RSI value computed from too few bars |
| EMA off by a fixed pct | yfinance auto-adjust vs raw close; check `auto_adjust=False` |
| 12H RSI mismatched but 1D matches | Resample boundary — TradingView 12H bars start at session open, ours at 00:00/12:00 UTC |
| All values off, only on some dates | Holidays / weekends — verify the date actually has a daily close |

Document the resolution of any mismatch in the fixture file's `notes` column.

## When to re-run

- Anytime the indicator engine (`bot_core/indicators/`) changes.
- Before bumping `bot_core.__version__`.
- Before flipping the bot from `mode = "scheduled"` (alerts) to anything that
  acts on signals (auto-orders, future Phase 4).
