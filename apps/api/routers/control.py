from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from bot_core.brokers.base import Broker
from bot_core.db import repository as repo
from bot_core.db.session import get_session
from bot_core.execution import emergency_stop

from ..auth import require_api_key
from ..schemas import EmergencyStopOut

router = APIRouter(tags=["control"], dependencies=[Depends(require_api_key)])

_SESSION = Depends(get_session)


def _broker_factory(mode: str) -> Broker:
    from bot_core.brokers.alpaca import AlpacaBroker

    return AlpacaBroker(mode=mode)  # type: ignore[arg-type]


@router.post("/emergency-stop", response_model=EmergencyStopOut)
def emergency_stop_endpoint(session: Session = _SESSION) -> EmergencyStopOut:
    """Kill switch: pause every bot and best-effort cancel their open orders.

    Pausing always succeeds (DB-only); order cancellation is attempted via the
    broker and any failure is reported rather than fatal.
    """
    bots = repo.list_bots(session)
    result = emergency_stop(session, bots, _broker_factory)
    return EmergencyStopOut(
        bots_paused=result.bots_paused,
        orders_cancelled=result.orders_cancelled,
        errors=result.errors,
    )
