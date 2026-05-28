# Buy-the-Dip Strategy — formal rules

Source: `Buy_the_Dip_Strategie.docx` (manual TradingView workflow).
This is the machine-checkable interpretation used by `strategies.buy_the_dip`.

## Three market phases (Stufen)

| Stufe | Price condition                         | RSI used | Strict threshold | Liberal threshold |
| ----- | --------------------------------------- | -------- | ---------------- | ----------------- |
| 1     | `close > EMA200_daily`                  | RSI 12H  | ≤ 30             | ≤ 35*             |
| 2     | `EMA200_weekly < close ≤ EMA200_daily`  | RSI 1D   | ≤ 30             | ≤ 30.5            |
| 3     | `close ≤ EMA200_weekly`                 | RSI 1W   | ≤ 30             | ≤ 32              |

\* Stufe-1 liberal threshold (35) applies only inside a **macro reclaim**:
price comes from below the weekly EMA200 and reclaims both EMAs within
~8 weeks. Heuristic — keep configurable.

## Tranche recommendation (informational)

| Stufe | Tranche of total capital |
| ----- | ------------------------ |
| 1     | 10–20 %                  |
| 2     | 20–40 %                  |
| 3     | 40–60 %                  |

Total capital ≤ 50 % of overall liquidity. Diversification % is split per
the asset allocation table in the strategy document.

## Assumptions (not specified in source doc)

| Item               | Assumption                                  |
| ------------------ | ------------------------------------------- |
| RSI length         | 14 (TradingView default)                    |
| RSI smoothing      | Wilder (RMA) — required to match TradingView |
| 12H candle start   | 00:00 / 12:00 UTC                           |
| Macro-reclaim window | 8 weeks (configurable)                    |

## Disclaimer

This is an educational/analysis tool. It surfaces indicator states; it does
not provide buy/sell recommendations and is not investment advice. The bot
is a signal generator — the human makes the final decision.
