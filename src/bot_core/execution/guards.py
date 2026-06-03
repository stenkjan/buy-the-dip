"""Risk guards for order execution.

Pure, side-effect-free checks evaluated before an order is placed. The
executor collects the violation reasons and refuses to trade if any fire.
Keeping these pure makes the risk policy trivially unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bot_core.brokers.base import Account


@dataclass(frozen=True)
class RiskGuards:
    max_position_pct: float = 0.10   # a single order must be ≤ this share of equity
    cash_floor: float = 0.0          # keep at least this much cash after the buy
    cooldown_days: float = 7.0       # minimum days between buys for one bot
    daily_trade_cap: int = 1         # max buys per UTC day for one bot
    max_drawdown_pct: float = 0.50   # halt new buys past this account drawdown

    @classmethod
    def from_dict(cls, d: dict | None) -> RiskGuards:
        if not d:
            return cls()
        f = cls()
        return cls(
            max_position_pct=float(d.get("max_position_pct", f.max_position_pct)),
            cash_floor=float(d.get("cash_floor", f.cash_floor)),
            cooldown_days=float(d.get("cooldown_days", f.cooldown_days)),
            daily_trade_cap=int(d.get("daily_trade_cap", f.daily_trade_cap)),
            max_drawdown_pct=float(d.get("max_drawdown_pct", f.max_drawdown_pct)),
        )


def evaluate_guards(
    *,
    notional: float,
    account: Account,
    recent_buy_times: list[datetime],
    now: datetime,
    guards: RiskGuards,
    drawdown_pct: float | None = None,
) -> list[str]:
    """Return a list of human-readable violation reasons (empty = clear to trade).

    ``recent_buy_times`` are the submit timestamps of prior buys for this bot
    (used for cooldown + daily cap). ``drawdown_pct`` is the account's current
    drawdown from peak as a positive fraction, when the caller can compute it.
    """
    reasons: list[str] = []

    if account.equity > 0 and notional / account.equity > guards.max_position_pct:
        reasons.append(
            f"order ${notional:,.0f} exceeds {guards.max_position_pct:.0%} of equity "
            f"${account.equity:,.0f}"
        )

    if account.cash - notional < guards.cash_floor:
        reasons.append(
            f"cash floor: ${account.cash:,.0f} - ${notional:,.0f} would fall below "
            f"${guards.cash_floor:,.0f}"
        )

    if recent_buy_times:
        last = max(recent_buy_times)
        days_since = (now - last).total_seconds() / 86_400.0
        if days_since < guards.cooldown_days:
            reasons.append(
                f"cooldown: last buy {days_since:.1f}d ago < {guards.cooldown_days:g}d"
            )

    today = sum(1 for t in recent_buy_times if t.date() == now.date())
    if today >= guards.daily_trade_cap:
        reasons.append(f"daily cap: {today} buy(s) today ≥ {guards.daily_trade_cap}")

    if drawdown_pct is not None and drawdown_pct > guards.max_drawdown_pct:
        reasons.append(
            f"drawdown circuit breaker: {drawdown_pct:.0%} > {guards.max_drawdown_pct:.0%}"
        )

    return reasons
