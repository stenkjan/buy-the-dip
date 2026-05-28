from __future__ import annotations

import os

import httpx

from bot_core.types import Signal


class TelegramNotifier:
    name = "telegram"

    def __init__(self, token: str | None = None, chat_id: str | None = None) -> None:
        self.token = token or os.environ.get("TELEGRAM_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        if not self.token or not self.chat_id:
            raise RuntimeError(
                "TELEGRAM_TOKEN and TELEGRAM_CHAT_ID must be set in the environment."
            )

    def send(self, signal: Signal) -> None:
        msg = self._format(signal)
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": msg, "parse_mode": "Markdown"}
        r = httpx.post(url, json=payload, timeout=15.0)
        r.raise_for_status()

    @staticmethod
    def _format(s: Signal) -> str:
        tr = (
            f"{s.tranche_pct_range[0]:.0f}-{s.tranche_pct_range[1]:.0f}%"
            if s.tranche_pct_range
            else "n/a"
        )
        return (
            f"*Signal* `{s.symbol}` — Stufe {s.stufe}\n"
            f"Trigger: {'YES' if s.triggered else 'no'}\n"
            f"Time: {s.timestamp.isoformat()}\n"
            f"Price: {s.price:.2f}\n"
            f"RSI: {s.rsi_value:.2f} (thr ≤ {s.rsi_threshold:.2f})\n"
            f"Suggested tranche: {tr}\n"
            "_Educational tool — not investment advice._"
        )
