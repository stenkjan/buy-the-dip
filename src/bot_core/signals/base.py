from __future__ import annotations

from typing import Protocol

from bot_core.types import AssetData, Signal


class Strategy(Protocol):
    """Pure function: AssetData -> Signal. Stateless, side-effect-free, unit-testable."""

    name: str

    def evaluate(self, data: AssetData) -> Signal: ...
