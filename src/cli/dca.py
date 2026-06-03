"""Dollar Cost Averaging backtest CLI.

Fetches monthly bars (default: Alpaca) for an asset, simulates a monthly buy
of ``--monthly`` USD on each bar, then writes a per-month CSV and an
aggregate summary JSON. Also reports the lump-sum buy-and-hold benchmark.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from bot_core.data import to_alpaca_symbol
from bot_core.data.base import DataSourceError

_MIN_BARS = 12
DASHBOARD_SCHEMA_VERSION = 1


def _json_safe(value: Any) -> Any:
    """Replace non-finite floats (NaN/inf) with None so the payload is valid
    JSON (browsers' JSON.parse rejects literal NaN)."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _parse_date(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _build_source(name: str) -> Any:
    if name != "alpaca":
        raise SystemExit(
            f"error: --source {name!r} is not supported; only 'alpaca' is implemented"
        )
    # Local import so `python -m cli.dca --help` works without alpaca-py.
    from bot_core.data.alpaca_source import AlpacaSource

    return AlpacaSource()


def _irr_bisect(cashflows: np.ndarray, *, low: float = -0.99, high: float = 1.0) -> float | None:
    """Solve for periodic IRR using bisection. Returns None if no sign change.

    Cashflow convention: contributions negative, terminal value positive.
    NPV at rate r = sum(cf[t] / (1+r)**t).
    """

    def npv(r: float) -> float:
        return float(sum(cf / (1.0 + r) ** t for t, cf in enumerate(cashflows)))

    # Expand the bracket if needed.
    lo, hi = low, high
    f_lo, f_hi = npv(lo), npv(hi)
    expand = 0
    while f_lo * f_hi > 0 and expand < 8:
        if abs(f_hi) < abs(f_lo):
            hi = hi * 2 if hi > 0 else 0.5
            f_hi = npv(hi)
        else:
            lo = max(lo - 0.1, -0.999999)
            f_lo = npv(lo)
        expand += 1
    if f_lo * f_hi > 0:
        return None

    for _ in range(200):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid)
        if abs(f_mid) < 1e-9 or (hi - lo) < 1e-12:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0


def _max_drawdown(series: pd.Series) -> float:
    running_max = series.cummax()
    drawdown = series / running_max - 1.0
    return float(drawdown.min()) if not drawdown.empty else 0.0


def simulate_dca(
    bars: pd.DataFrame,
    *,
    monthly: float,
    risk_free_annual: float,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Pure-pandas DCA simulation. Returns (per-month DataFrame, aggregates)."""
    close = bars["close"].astype(float)
    shares_bought = monthly / close
    cum_shares = shares_bought.cumsum()
    cum_invested = pd.Series(
        np.arange(1, len(close) + 1) * monthly, index=close.index, dtype=float
    )
    portfolio_value = cum_shares * close

    per_month = pd.DataFrame(
        {
            "month_close": close,
            "shares_bought_this_month": shares_bought,
            "cum_shares": cum_shares,
            "month_invested": monthly,
            "cum_invested": cum_invested,
            "portfolio_value": portfolio_value,
        }
    )

    total_invested = float(cum_invested.iloc[-1])
    final_value = float(portfolio_value.iloc[-1])
    total_return_pct = final_value / total_invested - 1.0 if total_invested > 0 else 0.0

    # Money-weighted IRR via the cashflow sequence (-monthly, ..., -monthly, +final_value).
    cashflows = np.array([-monthly] * len(close), dtype=float)
    # Terminal value happens at the same period as the last contribution: subtract
    # the contribution and add the final portfolio value to that last period.
    cashflows[-1] += final_value
    monthly_irr = _irr_bisect(cashflows)
    cagr = ((1.0 + monthly_irr) ** 12 - 1.0) if monthly_irr is not None else None

    # Sharpe: annualize monthly portfolio-value returns, subtract risk-free annual.
    monthly_returns = portfolio_value.pct_change().dropna()
    if len(monthly_returns) > 1 and monthly_returns.std(ddof=1) > 0:
        sharpe_annual = (
            monthly_returns.mean() * 12 - risk_free_annual
        ) / (monthly_returns.std(ddof=1) * math.sqrt(12))
        sharpe_annual = float(sharpe_annual)
    else:
        sharpe_annual = None

    max_dd = _max_drawdown(portfolio_value)

    # Lump-sum buy-and-hold of `total_invested` at the first bar.
    first_close = float(close.iloc[0])
    last_close = float(close.iloc[-1])
    lump_shares = total_invested / first_close
    lump_final = lump_shares * last_close
    lump_return_pct = lump_final / total_invested - 1.0
    # Equity curve for the lump-sum benchmark (for the dashboard chart).
    per_month["lump_sum_value"] = lump_shares * close
    years = (close.index[-1] - close.index[0]).days / 365.25
    lump_cagr = ((lump_final / total_invested) ** (1.0 / years) - 1.0) if years > 0 else None

    aggregates: dict[str, Any] = {
        "n_months": len(close),
        "first_bar": close.index[0].isoformat(),
        "last_bar": close.index[-1].isoformat(),
        "total_invested": total_invested,
        "final_value": final_value,
        "total_return_pct": total_return_pct,
        "cagr": cagr,
        "max_drawdown_pct": max_dd,
        "sharpe_annual": sharpe_annual,
        "risk_free_annual": risk_free_annual,
        "benchmark_lump_sum": {
            "invested_at_first_bar": total_invested,
            "final_value": lump_final,
            "total_return_pct": lump_return_pct,
            "cagr": lump_cagr,
        },
        "dca_vs_lump_sum_delta_pct": total_return_pct - lump_return_pct,
    }
    return per_month, aggregates


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="btd-dca",
        description="Dollar-cost averaging backtest with lump-sum benchmark",
    )
    p.add_argument("--asset", required=True, help="symbol, e.g. ^NDX, ^GSPC, QQQ")
    p.add_argument("--start", type=_parse_date, required=True)
    p.add_argument("--end", type=_parse_date, default=None)
    p.add_argument("--monthly", type=float, default=1000.0, help="USD invested each month")
    p.add_argument(
        "--risk-free",
        type=float,
        default=0.02,
        help="annual risk-free rate as a decimal (0.02 = 2%%)",
    )
    p.add_argument("--source", default="alpaca", help="data source (only 'alpaca' supported)")
    p.add_argument("--output-dir", type=Path, default=Path("backtest"))
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="explicit CSV path; otherwise <output-dir>/dca-<asset>.csv",
    )
    args = p.parse_args(argv)

    end = args.end or datetime.now(tz=UTC)
    mapped = to_alpaca_symbol(args.asset)
    label = f"{args.asset} (Alpaca: {mapped})" if mapped != args.asset else args.asset

    try:
        source = _build_source(args.source)
    except DataSourceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    # Capture stderr warnings emitted by the source so we can stash them in the JSON.
    truncation_warning: str | None = None
    try:
        bars = source.fetch(args.asset, "1mo", start=args.start, end=end)
    except DataSourceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if bars.empty or len(bars) < _MIN_BARS:
        print(
            f"error: insufficient monthly history for {label}: got {len(bars)} bars "
            f"(need at least {_MIN_BARS})",
            file=sys.stderr,
        )
        return 2

    first_bar_dt = bars.index[0]
    requested_start = pd.Timestamp(args.start)
    if requested_start.tzinfo is None:
        requested_start = requested_start.tz_localize("UTC")
    else:
        requested_start = requested_start.tz_convert("UTC")
    if first_bar_dt - requested_start > pd.Timedelta(days=35):
        truncation_warning = (
            f"requested start {args.start.date()} but earliest bar available is "
            f"{first_bar_dt.date()}"
        )

    per_month, aggregates = simulate_dca(
        bars, monthly=args.monthly, risk_free_annual=args.risk_free
    )
    aggregates["asset"] = args.asset
    aggregates["alpaca_symbol"] = mapped
    aggregates["source"] = args.source
    aggregates["monthly_contribution"] = args.monthly
    if truncation_warning is not None:
        aggregates["history_truncation_warning"] = truncation_warning

    args.output_dir.mkdir(parents=True, exist_ok=True)
    safe = args.asset.lstrip("^").lower()
    csv_path = args.output if args.output is not None else args.output_dir / f"dca-{safe}.csv"
    summary_path = csv_path.with_suffix(".summary.json")
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    per_month_out = per_month.copy()
    per_month_out.index.name = "month"
    per_month_out.to_csv(csv_path)
    summary_path.write_text(json.dumps(aggregates, indent=2, default=str))

    # Dashboard payload: aggregates (KPIs) + the equity-curve series so the web
    # app can render DCA vs lump-sum without re-running the backtest.
    series = [
        {
            "month": ts.isoformat(),
            "cum_invested": float(row["cum_invested"]),
            "dca_value": float(row["portfolio_value"]),
            "lump_value": float(row["lump_sum_value"]),
        }
        for ts, row in per_month.iterrows()
    ]
    dashboard = {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        **aggregates,
        "series": series,
    }
    dashboard_path = csv_path.with_name(f"{csv_path.stem}.dashboard.json")
    dashboard_path.write_text(json.dumps(_json_safe(dashboard), indent=2, allow_nan=False))

    cagr = aggregates["cagr"]
    sharpe = aggregates["sharpe_annual"]
    lump = aggregates["benchmark_lump_sum"]
    print(f"{label}: {aggregates['n_months']} monthly bars "
          f"({aggregates['first_bar'][:10]} → {aggregates['last_bar'][:10]})")
    cagr_str = f"{cagr:+.2%}" if cagr is not None else "n/a"
    print(f"  invested ${aggregates['total_invested']:,.0f}  "
          f"final ${aggregates['final_value']:,.0f}  "
          f"return {aggregates['total_return_pct']:+.1%}  cagr {cagr_str}")
    print(f"  max drawdown {aggregates['max_drawdown_pct']:+.1%}  "
          f"sharpe {'n/a' if sharpe is None else f'{sharpe:+.2f}'}")
    lump_cagr_str = "n/a" if lump["cagr"] is None else f"{lump['cagr']:+.2%}"
    print(f"  lump-sum benchmark: final ${lump['final_value']:,.0f}  "
          f"return {lump['total_return_pct']:+.1%}  cagr {lump_cagr_str}")
    print(f"  dca vs lump delta {aggregates['dca_vs_lump_sum_delta_pct']:+.1%}")
    if truncation_warning is not None:
        print(f"  note: {truncation_warning}")
    print(f"wrote {csv_path}, {summary_path} and {dashboard_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
