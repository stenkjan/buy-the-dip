from __future__ import annotations

from bot_core.execution import size_order


def test_aggressiveness_zero_picks_low_end_of_range():
    qty, value = size_order(
        account_cash=10_000,
        asset_allocation_pct=0.5,
        tranche_pct_range=(0.10, 0.20),
        last_close=100.0,
        aggressiveness=0.0,
    )
    # 10000 * 0.5 * 0.10 = 500 → 5 units at $100
    assert value == 500.0
    assert qty == 5.0


def test_aggressiveness_one_picks_high_end_of_range():
    qty, value = size_order(
        account_cash=10_000,
        asset_allocation_pct=0.5,
        tranche_pct_range=(0.10, 0.20),
        last_close=100.0,
        aggressiveness=1.0,
    )
    assert value == 1000.0
    assert qty == 10.0


def test_aggressiveness_midpoint_interpolates():
    qty, value = size_order(
        account_cash=10_000,
        asset_allocation_pct=0.5,
        tranche_pct_range=(0.10, 0.20),
        last_close=100.0,
        aggressiveness=0.5,
    )
    # 10000 * 0.5 * 0.15 = 750
    assert value == 750.0
    assert qty == 7.5


def test_too_small_allocation_returns_zero():
    qty, value = size_order(
        account_cash=100.0,
        asset_allocation_pct=0.05,
        tranche_pct_range=(0.10, 0.20),
        last_close=50.0,
        aggressiveness=0.5,
        min_order_eur=50.0,
    )
    # 100 * 0.05 * 0.15 = 0.75 → below min
    assert (qty, value) == (0.0, 0.0)


def test_zero_cash_returns_zero():
    qty, value = size_order(
        account_cash=0.0,
        asset_allocation_pct=0.5,
        tranche_pct_range=(0.10, 0.20),
        last_close=100.0,
    )
    assert (qty, value) == (0.0, 0.0)


def test_inverted_range_is_normalised():
    qty_lo, _ = size_order(
        account_cash=10_000,
        asset_allocation_pct=0.5,
        tranche_pct_range=(0.20, 0.10),
        last_close=100.0,
        aggressiveness=0.0,
    )
    qty_hi, _ = size_order(
        account_cash=10_000,
        asset_allocation_pct=0.5,
        tranche_pct_range=(0.20, 0.10),
        last_close=100.0,
        aggressiveness=1.0,
    )
    assert qty_lo < qty_hi


def test_qty_rounding_precision():
    qty, _ = size_order(
        account_cash=1_000,
        asset_allocation_pct=1.0,
        tranche_pct_range=(0.123456789, 0.123456789),
        last_close=7.0,
        aggressiveness=0.5,
    )
    # qty should be rounded to 8 dp
    assert len(str(qty).split(".")[-1]) <= 8
