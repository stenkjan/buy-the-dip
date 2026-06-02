from __future__ import annotations


def size_order(
    *,
    account_cash: float,
    asset_allocation_pct: float,
    tranche_pct_range: tuple[float, float],
    last_close: float,
    aggressiveness: float = 0.5,
    min_order_eur: float = 50.0,
) -> tuple[float, float]:
    """Pure sizing: decide how much to buy for one tranche.

    Returns `(qty, target_value)`. `qty` is a float — the broker adapter is
    responsible for rounding to its venue's precision (integer shares for
    equities, fractional for crypto). Returns `(0.0, 0.0)` when the resulting
    notional would be below `min_order_eur` so callers can skip cleanly.
    """
    if account_cash <= 0 or last_close <= 0 or asset_allocation_pct <= 0:
        return (0.0, 0.0)

    lo, hi = tranche_pct_range
    if lo > hi:
        lo, hi = hi, lo
    clamped = min(1.0, max(0.0, aggressiveness))
    tranche_pct = lo + (hi - lo) * clamped

    allocated = account_cash * asset_allocation_pct
    target_value = allocated * tranche_pct
    if target_value < min_order_eur:
        return (0.0, 0.0)

    qty = target_value / last_close
    return (round(qty, 8), round(target_value, 2))
