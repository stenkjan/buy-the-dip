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

    @classmethod
    def from_dict(cls, d: dict | None) -> BuyTheDipConfig:
        """Build a config from a (partial) dict, falling back to defaults for
        any unset field. Used for per-bot config_json and the backtest API."""
        if not d:
            return cls()
        f = cls()
        return cls(
            rsi_threshold_stufe1=float(d.get("rsi_threshold_stufe1", f.rsi_threshold_stufe1)),
            rsi_threshold_stufe2=float(d.get("rsi_threshold_stufe2", f.rsi_threshold_stufe2)),
            rsi_threshold_stufe3=float(d.get("rsi_threshold_stufe3", f.rsi_threshold_stufe3)),
            rsi_threshold_stufe1_liberal=float(
                d.get("rsi_threshold_stufe1_liberal", f.rsi_threshold_stufe1_liberal)
            ),
            rsi_threshold_stufe2_liberal=float(
                d.get("rsi_threshold_stufe2_liberal", f.rsi_threshold_stufe2_liberal)
            ),
            rsi_threshold_stufe3_liberal=float(
                d.get("rsi_threshold_stufe3_liberal", f.rsi_threshold_stufe3_liberal)
            ),
            liberal=bool(d.get("liberal", f.liberal)),
            macro_reclaim_window_weeks=int(
                d.get("macro_reclaim_window_weeks", f.macro_reclaim_window_weeks)
            ),
        )
