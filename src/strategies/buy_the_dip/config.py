from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BuyTheDipConfig:
    rsi_threshold_stufe1: float = 30.0
    rsi_threshold_stufe2: float = 30.0
    rsi_threshold_stufe3: float = 30.0

    rsi_threshold_stufe1_liberal: float = 35.0  # only inside macro_reclaim
    rsi_threshold_stufe2_liberal: float = 30.5
    rsi_threshold_stufe3_liberal: float = 32.0

    liberal: bool = True
    macro_reclaim_window_weeks: int = 8

    tranche_stufe1: tuple[float, float] = (10.0, 20.0)
    tranche_stufe2: tuple[float, float] = (20.0, 40.0)
    tranche_stufe3: tuple[float, float] = (40.0, 60.0)
