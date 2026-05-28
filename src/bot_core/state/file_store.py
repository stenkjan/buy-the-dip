from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol


class StateStore(Protocol):
    def already_alerted(self, key: str) -> bool: ...
    def mark_alerted(self, key: str) -> None: ...


class FileStateStore:
    """JSON-on-disk idempotency. Good for GitHub Actions artifacts; swap for DB later."""

    def __init__(self, path: str | Path = "state/alerts.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seen: set[str] = set(self._load())

    def _load(self) -> list[str]:
        if not self.path.exists():
            return []
        try:
            return list(json.loads(self.path.read_text()))
        except (json.JSONDecodeError, OSError):
            return []

    def already_alerted(self, key: str) -> bool:
        return key in self._seen

    def mark_alerted(self, key: str) -> None:
        self._seen.add(key)
        self.path.write_text(json.dumps(sorted(self._seen)))
