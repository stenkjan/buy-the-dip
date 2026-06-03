from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from bot_core.db import repository as repo
from bot_core.db.session import get_session

from ..auth import require_api_key
from ..schemas import BotCreate, BotOut, BotUpdate, PositionOut, SignalRecordOut

# The whole control plane is gated behind the admin key (see auth.require_api_key).
router = APIRouter(prefix="/bots", tags=["bots"], dependencies=[Depends(require_api_key)])

# Module-level singletons so the Depends() call isn't evaluated in a default
# argument expression (ruff B008), matching the pattern in signals.py.
_SESSION = Depends(get_session)


def _require_bot(session: Session, bot_id: str):
    bot = repo.get_bot(session, bot_id)
    if bot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"bot {bot_id} not found")
    return bot


@router.get("", response_model=list[BotOut])
def list_bots(
    enabled_only: bool = False,
    session: Session = _SESSION,
) -> list[BotOut]:
    bots = repo.list_bots(session, enabled_only=enabled_only)
    return [BotOut.model_validate(b, from_attributes=True) for b in bots]


@router.post("", response_model=BotOut, status_code=status.HTTP_201_CREATED)
def create_bot(body: BotCreate, session: Session = _SESSION) -> BotOut:
    bot = repo.create_bot(
        session,
        name=body.name,
        strategy_name=body.strategy_name,
        asset_symbol=body.asset_symbol,
        mode=body.mode,
        enabled=body.enabled,
        broker_name=body.broker_name,
        config_json=body.config_json,
    )
    return BotOut.model_validate(bot, from_attributes=True)


@router.get("/{bot_id}", response_model=BotOut)
def get_bot(bot_id: str, session: Session = _SESSION) -> BotOut:
    return BotOut.model_validate(_require_bot(session, bot_id), from_attributes=True)


@router.patch("/{bot_id}", response_model=BotOut)
def update_bot(bot_id: str, body: BotUpdate, session: Session = _SESSION) -> BotOut:
    _require_bot(session, bot_id)
    bot = repo.update_bot(
        session,
        bot_id,
        name=body.name,
        mode=body.mode,
        enabled=body.enabled,
        config_json=body.config_json,
    )
    return BotOut.model_validate(bot, from_attributes=True)


@router.post("/{bot_id}/toggle", response_model=BotOut)
def toggle_bot(bot_id: str, session: Session = _SESSION) -> BotOut:
    bot = _require_bot(session, bot_id)
    bot = repo.set_bot_enabled(session, bot_id, not bot.enabled)
    return BotOut.model_validate(bot, from_attributes=True)


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bot(bot_id: str, session: Session = _SESSION) -> None:
    if not repo.delete_bot(session, bot_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"bot {bot_id} not found")


@router.get("/{bot_id}/signals", response_model=list[SignalRecordOut])
def bot_signals(
    bot_id: str,
    limit: int = 100,
    session: Session = _SESSION,
) -> list[SignalRecordOut]:
    _require_bot(session, bot_id)
    rows = repo.list_recent_signals(session, bot_id, limit=limit)
    return [SignalRecordOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/{bot_id}/positions", response_model=list[PositionOut])
def bot_positions(bot_id: str, session: Session = _SESSION) -> list[PositionOut]:
    _require_bot(session, bot_id)
    rows = repo.list_positions(session, bot_id)
    return [PositionOut.model_validate(r, from_attributes=True) for r in rows]
