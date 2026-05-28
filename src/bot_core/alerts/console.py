from __future__ import annotations

import json
import sys

from bot_core.types import Signal


class ConsoleNotifier:
    name = "console"

    def send(self, signal: Signal) -> None:
        json.dump(signal.to_dict(), sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
