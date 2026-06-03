from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from bot_core.backtest import forward_returns, run_backtest, summarize
from bot_core.data import YFinanceSource
from strategies.buy_the_dip import BuyTheDipConfig, get_strategy

from ..auth import require_api_key
from ..schemas import BacktestOut, BacktestRequest

# Compute-heavy + hits the data provider, so gate it behind the admin key like
# the rest of the control plane.
router = APIRouter(tags=["backtest"], dependencies=[Depends(require_api_key)])

_DEFAULT_START = datetime(2005, 1, 1)


def _json_safe(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


@router.post("/backtest", response_model=BacktestOut)
def run_bt(body: BacktestRequest) -> BacktestOut:
    """Replay the strategy over history for an asset + (optional) thresholds.

    Powers the threshold editor's "preview at this threshold" view: pass a
    partial `config` of RSI thresholds and get back the triggered signals with
    forward returns.
    """
    try:
        start = datetime.fromisoformat(body.start) if body.start else _DEFAULT_START
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"bad start date: {exc}") from exc

    cfg = (
        BuyTheDipConfig.from_dict(body.config)
        if body.config is not None
        else BuyTheDipConfig(liberal=not body.strict)
    )

    daily = YFinanceSource().fetch(body.asset, "1d", start=start)
    if daily.empty or len(daily) < 250:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"insufficient daily history for {body.asset}",
        )

    result = run_backtest(body.asset, daily, get_strategy(cfg), hourly=None)
    signals_df = forward_returns(result.signals, result.indicators)
    stats = summarize(signals_df)
    signals = [] if signals_df.empty else signals_df.to_dict(orient="records")

    return BacktestOut(
        asset=body.asset,
        n_bars=len(result.indicators),
        liberal=cfg.liberal,
        summary=_json_safe(stats),
        signals=_json_safe(signals),
    )
