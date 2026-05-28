from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class AssetData:
    """Snapshot of one asset at evaluation time. All fields are last-bar values."""

    symbol: str
    timestamp: datetime
    last_close: float
    ema200_daily: float
    ema200_weekly: float
    rsi_12h: float
    rsi_1d: float
    rsi_1w: float
    history: pd.DataFrame | None = None  # optional: full OHLCV for backtest


@dataclass(frozen=True)
class Signal:
    """Result of evaluating a Strategy against AssetData."""

    symbol: str
    timestamp: datetime
    triggered: bool
    stufe: int                       # 1, 2, or 3 (strategy-specific concept)
    rsi_value: float
    rsi_threshold: float
    price: float
    tranche_pct_range: tuple[float, float] | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "triggered": self.triggered,
            "stufe": self.stufe,
            "rsi_value": self.rsi_value,
            "rsi_threshold": self.rsi_threshold,
            "price": self.price,
            "tranche_pct_range": list(self.tranche_pct_range) if self.tranche_pct_range else None,
            "extras": self.extras,
        }
