from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from bot_core.backtest import run_sweep
from bot_core.data import YFinanceSource
from bot_core.db import repository as repo
from bot_core.db.session import get_session

from ..auth import require_api_key
from ..schemas import ParameterSweepOut, ParameterSweepRequest

router = APIRouter(tags=["sweep"], dependencies=[Depends(require_api_key)])

_SESSION = Depends(get_session)
_DEFAULT_START = datetime(2005, 1, 1)


@router.post("/parameter-sweep", response_model=ParameterSweepOut)
def parameter_sweep(body: ParameterSweepRequest, session: Session = _SESSION) -> ParameterSweepOut:
    """Replay the strategy over a grid of threshold variations and rank them by
    historical forward return. Suggestions only — never mutates a bot."""
    try:
        start = datetime.fromisoformat(body.start) if body.start else _DEFAULT_START
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"bad start date: {exc}") from exc

    daily = YFinanceSource().fetch(body.asset, "1d", start=start)
    if daily.empty or len(daily) < 250:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"insufficient daily history for {body.asset}"
        )

    results = run_sweep(body.asset, daily, body.grid)

    if body.persist:
        window = {
            "window_start": daily.index[0].to_pydatetime(),
            "window_end": daily.index[-1].to_pydatetime(),
        }
        for r in results:
            repo.record_parameter_run(
                session, "buy_the_dip", r["params"],
                {
                    **window,
                    "total_signals": r["total_signals"],
                    "win_rate": r["win_rate"],
                    "mean_forward_return": r["mean_forward_return"],
                },
                bot_id=body.bot_id,
            )

    horizon = results[0]["horizon"] if results else "fwd_90d"
    return ParameterSweepOut(asset=body.asset, horizon=horizon, results=results)
