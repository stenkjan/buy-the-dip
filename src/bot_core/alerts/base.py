from __future__ import annotations

from typing import Protocol

from bot_core.types import Signal


class Notifier(Protocol):
    name: str

    def send(self, signal: Signal) -> None: ...
