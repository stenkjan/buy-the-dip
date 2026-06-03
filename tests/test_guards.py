from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bot_core.brokers.base import Account
from bot_core.execution.guards import RiskGuards, evaluate_guards

NOW = datetime(2026, 6, 3, tzinfo=UTC)
ACCT = Account(cash=100_000.0, buying_power=100_000.0, equity=100_000.0, currency="USD")


def test_clear_when_within_limits():
    assert evaluate_guards(
        notional=5_000.0, account=ACCT, recent_buy_times=[], now=NOW, guards=RiskGuards()
    ) == []


def test_max_position_pct():
    reasons = evaluate_guards(
        notional=20_000.0, account=ACCT, recent_buy_times=[], now=NOW,
        guards=RiskGuards(max_position_pct=0.10),
    )
    assert any("exceeds 10%" in r for r in reasons)


def test_cash_floor():
    reasons = evaluate_guards(
        notional=95_000.0, account=ACCT, recent_buy_times=[], now=NOW,
        guards=RiskGuards(max_position_pct=1.0, cash_floor=10_000.0),
    )
    assert any("cash floor" in r for r in reasons)


def test_cooldown():
    reasons = evaluate_guards(
        notional=1_000.0, account=ACCT,
        recent_buy_times=[NOW - timedelta(days=2)], now=NOW,
        guards=RiskGuards(cooldown_days=7, daily_trade_cap=99),
    )
    assert any("cooldown" in r for r in reasons)


def test_daily_cap():
    reasons = evaluate_guards(
        notional=1_000.0, account=ACCT,
        recent_buy_times=[NOW], now=NOW,  # same UTC day
        guards=RiskGuards(cooldown_days=0, daily_trade_cap=1),
    )
    assert any("daily cap" in r for r in reasons)


def test_drawdown_breaker():
    reasons = evaluate_guards(
        notional=1_000.0, account=ACCT, recent_buy_times=[], now=NOW,
        guards=RiskGuards(), drawdown_pct=0.6,
    )
    assert any("drawdown" in r for r in reasons)


def test_from_dict_overrides_and_defaults():
    g = RiskGuards.from_dict({"cooldown_days": 3, "daily_trade_cap": 5})
    assert g.cooldown_days == 3 and g.daily_trade_cap == 5
    assert g.max_position_pct == RiskGuards().max_position_pct
    assert RiskGuards.from_dict(None) == RiskGuards()
