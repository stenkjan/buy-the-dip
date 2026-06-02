"""Strategy-vs-dollar-cost-averaging comparison with Sharpe ratio.

The buy-the-dip strategy is, at heart, a *timing* overlay: instead of putting
every incoming dollar to work immediately, it parks cash and deploys it in
tranches when a Stufe signal fires. The natural benchmark is therefore plain
**dollar-cost averaging (DCA)** — invest a fixed amount on the first trading day
of every month, regardless of indicators.

Both accounts receive the *identical* external cashflow (the same fixed
contribution on the same dates), so their terminal values are directly
comparable: the only difference is *when* the money is put to work.

All risk statistics (Sharpe, volatility, max drawdown) are computed on a
**time-weighted return** series, which strips out the distortion that periodic
contributions would otherwise inject into a raw equity curve.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from bot_core.types import Signal

_TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class AccountResult:
    """Outcome of one simulated account (strategy or DCA baseline)."""

    final_value: float
    total_invested: float
    profit: float
    total_return: float  # final_value / total_invested - 1
    irr_annual: float  # money-weighted annual return (XIRR)
    cagr_twr: float  # time-weighted annualized return
    sharpe: float  # annualized, on time-weighted daily returns
    volatility_annual: float
    max_drawdown: float  # most negative peak-to-trough on the TWR index
    n_buys: int
    ending_cash: float
    equity: pd.Series  # daily portfolio value (holdings + cash)

    def to_dict(self) -> dict[str, float | int]:
        return {
            "final_value": round(self.final_value, 2),
            "total_invested": round(self.total_invested, 2),
            "profit": round(self.profit, 2),
            "total_return": round(self.total_return, 6),
            "irr_annual": round(self.irr_annual, 6),
            "cagr_twr": round(self.cagr_twr, 6),
            "sharpe": round(self.sharpe, 4),
            "volatility_annual": round(self.volatility_annual, 6),
            "max_drawdown": round(self.max_drawdown, 6),
            "n_buys": self.n_buys,
            "ending_cash": round(self.ending_cash, 2),
        }


def first_trading_day_of_month(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """First available bar in each calendar month — the DCA contribution dates."""
    if len(index) == 0:
        return index
    s = pd.Series(index, index=index)
    firsts = s.groupby([index.year, index.month]).first()
    return pd.DatetimeIndex(firsts.to_numpy())


def _xirr(dates: list[pd.Timestamp], amounts: list[float]) -> float:
    """Money-weighted annual return solving sum(cf / (1+r)^(years)) = 0.

    Contributions are negative (cash leaves the pocket); the terminal account
    value is the final positive cashflow. Solved by bisection over a wide,
    bounded rate range so it never diverges. Returns NaN if it can't bracket.
    """
    if len(dates) < 2:
        return float("nan")
    t0 = dates[0]
    years = np.array([(d - t0).days / 365.0 for d in dates], dtype=float)
    cf = np.array(amounts, dtype=float)

    def npv(rate: float) -> float:
        return float(np.sum(cf / np.power(1.0 + rate, years)))

    lo, hi = -0.9999, 10.0
    f_lo, f_hi = npv(lo), npv(hi)
    if np.isnan(f_lo) or np.isnan(f_hi) or f_lo * f_hi > 0:
        return float("nan")
    for _ in range(200):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid)
        if abs(f_mid) < 1e-7:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0


def _time_weighted_returns(value: pd.Series, contributions: pd.Series) -> pd.Series:
    """Daily time-weighted returns: r_t = V_t / (V_{t-1} + F_t) - 1.

    Contributions F_t are treated as added at the start of the day (before the
    market moves), so they don't show up as investment "gains".
    """
    prev = value.shift(1)
    invested_base = prev + contributions
    r = value / invested_base - 1.0
    return r.iloc[1:].replace([np.inf, -np.inf], np.nan).dropna()


def _sharpe(returns: pd.Series, risk_free_annual: float) -> tuple[float, float]:
    """(annualized Sharpe, annualized volatility) from daily TWR returns."""
    if len(returns) < 2 or returns.std(ddof=1) == 0:
        return float("nan"), 0.0
    rf_daily = risk_free_annual / _TRADING_DAYS_PER_YEAR
    excess = returns - rf_daily
    sharpe = float(excess.mean() / returns.std(ddof=1) * np.sqrt(_TRADING_DAYS_PER_YEAR))
    vol = float(returns.std(ddof=1) * np.sqrt(_TRADING_DAYS_PER_YEAR))
    return sharpe, vol


def _cagr_and_drawdown(returns: pd.Series) -> tuple[float, float]:
    """Time-weighted CAGR and max drawdown from the compounded $1 growth index."""
    if returns.empty:
        return float("nan"), 0.0
    growth = (1.0 + returns).cumprod()
    n = len(returns)
    cagr = float(growth.iloc[-1] ** (_TRADING_DAYS_PER_YEAR / n) - 1.0)
    running_max = growth.cummax()
    drawdown = growth / running_max - 1.0
    return cagr, float(drawdown.min())


def _finalize(
    value: pd.Series,
    contributions: pd.Series,
    n_buys: int,
    ending_cash: float,
    risk_free_annual: float,
) -> AccountResult:
    total_invested = float(contributions.sum())
    final_value = float(value.iloc[-1])
    twr = _time_weighted_returns(value, contributions)
    sharpe, vol = _sharpe(twr, risk_free_annual)
    cagr, mdd = _cagr_and_drawdown(twr)

    # XIRR: each contribution is a negative cashflow on its date; terminal value
    # is the final positive cashflow on the last bar.
    contrib_days = contributions[contributions > 0]
    cf_dates = [pd.Timestamp(d) for d in contrib_days.index] + [pd.Timestamp(value.index[-1])]
    cf_amounts = [-float(a) for a in contrib_days.to_numpy()] + [final_value]
    irr = _xirr(cf_dates, cf_amounts)

    return AccountResult(
        final_value=final_value,
        total_invested=total_invested,
        profit=final_value - total_invested,
        total_return=final_value / total_invested - 1.0 if total_invested else float("nan"),
        irr_annual=irr,
        cagr_twr=cagr,
        sharpe=sharpe,
        volatility_annual=vol,
        max_drawdown=mdd,
        n_buys=n_buys,
        ending_cash=ending_cash,
        equity=value,
    )


def simulate_dca(
    closes: pd.Series,
    contribution_dates: pd.DatetimeIndex,
    monthly_contribution: float,
    risk_free_annual: float = 0.0,
) -> AccountResult:
    """Always-invested baseline: buy `monthly_contribution` worth on each date."""
    contrib = pd.Series(0.0, index=closes.index)
    contrib.loc[contribution_dates] = monthly_contribution

    units = (contrib / closes).cumsum()
    value = units * closes
    return _finalize(value, contrib, int((contrib > 0).sum()), 0.0, risk_free_annual)


def simulate_strategy(
    closes: pd.Series,
    signals: list[Signal],
    contribution_dates: pd.DatetimeIndex,
    monthly_contribution: float,
    risk_free_annual: float = 0.0,
) -> AccountResult:
    """Buy-the-dip overlay: contributions accumulate as cash; on each triggered
    signal, deploy the midpoint of that Stufe's tranche range (% of *current
    cash*) into the asset at that day's close.
    """
    contrib = pd.Series(0.0, index=closes.index)
    contrib.loc[contribution_dates] = monthly_contribution

    # Map each signal to the deployable fraction of available cash.
    deploy_frac: dict[pd.Timestamp, float] = {}
    for s in signals:
        if not s.triggered or not s.tranche_pct_range:
            continue
        ts = pd.Timestamp(s.timestamp)
        # Snap the signal timestamp to the matching bar in `closes`.
        loc = closes.index.get_indexer([ts], method="nearest")[0]
        bar = closes.index[loc]
        frac = (s.tranche_pct_range[0] + s.tranche_pct_range[1]) / 200.0  # midpoint /100
        deploy_frac[bar] = max(deploy_frac.get(bar, 0.0), frac)

    cash = 0.0
    units = 0.0
    n_buys = 0
    values: list[float] = []
    for ts, price in closes.items():
        cash += float(contrib.loc[ts])
        frac_today = deploy_frac.get(ts)
        if frac_today and cash > 0:
            spend = cash * frac_today
            units += spend / float(price)
            cash -= spend
            n_buys += 1
        values.append(units * float(price) + cash)

    value = pd.Series(values, index=closes.index)
    return _finalize(value, contrib, n_buys, cash, risk_free_annual)


def compare_dca(
    symbol: str,
    closes: pd.Series,
    signals: list[Signal],
    monthly_contribution: float = 1000.0,
    risk_free_annual: float = 0.0,
) -> dict[str, object]:
    """Run both accounts over the same period and return a JSON-ready comparison.

    `closes` should be the daily close series from a `BacktestResult` (already
    warmed up past the EMA200 window), and `signals` its triggered signals.
    """
    closes = closes.dropna()
    if len(closes) < 2:
        return {"error": "insufficient price history", "symbol": symbol}

    contribution_dates = first_trading_day_of_month(closes.index)
    strat = simulate_strategy(
        closes, signals, contribution_dates, monthly_contribution, risk_free_annual
    )
    dca = simulate_dca(closes, contribution_dates, monthly_contribution, risk_free_annual)

    start, end = closes.index[0], closes.index[-1]
    years = (end - start).days / 365.25

    return {
        "symbol": symbol,
        "period": {
            "start": start.date().isoformat(),
            "end": end.date().isoformat(),
            "years": round(years, 2),
            "trading_days": len(closes),
        },
        "monthly_contribution": monthly_contribution,
        "n_contributions": len(contribution_dates),
        "total_invested": round(float(monthly_contribution * len(contribution_dates)), 2),
        "risk_free_annual": risk_free_annual,
        "strategy": strat.to_dict(),
        "dca": dca.to_dict(),
        "delta": {
            "final_value": round(strat.final_value - dca.final_value, 2),
            "total_return_pct_points": round((strat.total_return - dca.total_return) * 100, 2),
            "sharpe": round(strat.sharpe - dca.sharpe, 4),
        },
    }
