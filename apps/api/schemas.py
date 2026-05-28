from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


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
