from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SignalOut(BaseModel):
    symbol: str
    timestamp: datetime
    triggered: bool
    stufe: int
    rsi_value: float
    rsi_threshold: float
    price: float
    tranche_pct_range: tuple[float, float] | None = None
    extras: dict = {}


class HealthOut(BaseModel):
    status: str
    version: str


# --- Bot control plane (Phase 6) -------------------------------------------


class BotCreate(BaseModel):
    name: str
    asset_symbol: str
    strategy_name: str = "buy_the_dip"
    mode: str = Field(default="paper", pattern="^(paper|live)$")
    enabled: bool = False
    broker_name: str = "alpaca"
    config_json: dict[str, Any] = Field(default_factory=dict)


class BotUpdate(BaseModel):
    name: str | None = None
    mode: str | None = Field(default=None, pattern="^(paper|live)$")
    enabled: bool | None = None
    config_json: dict[str, Any] | None = None


class BotOut(BaseModel):
    id: str
    name: str
    strategy_name: str
    asset_symbol: str
    mode: str
    enabled: bool
    broker_name: str
    config_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SignalRecordOut(BaseModel):
    id: str
    bot_id: str
    timestamp: datetime
    stufe: int
    rsi_value: float
    rsi_threshold: float
    price: float
    triggered: bool
    created_at: datetime


class PositionOut(BaseModel):
    id: str
    bot_id: str
    symbol: str
    qty: float
    avg_entry_price: float
    market_value: float
    unrealized_pl: float
    updated_at: datetime
