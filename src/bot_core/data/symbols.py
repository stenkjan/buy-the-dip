"""Symbol mapping between Yahoo-style tickers and Alpaca tradeable tickers.

Indices like ^NDX / ^GSPC are not directly tradeable on Alpaca; the standard
ETF proxies (QQQ, SPY, ...) track them within a small annual difference.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parents[3] / "config" / "alpaca_symbols.toml"
_cache: dict[Path, dict[str, str]] = {}


def _resolve_path(mapping_path: Path | None) -> Path:
    if mapping_path is not None:
        return mapping_path
    env = os.getenv("BTD_ALPACA_SYMBOLS")
    if env:
        return Path(env)
    return _DEFAULT_PATH


def _load(path: Path) -> dict[str, str]:
    if path in _cache:
        return _cache[path]
    if not path.is_file():
        _cache[path] = {}
        return _cache[path]
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    mapping = {str(k): str(v) for k, v in (data.get("map") or {}).items()}
    _cache[path] = mapping
    return mapping


def to_alpaca_symbol(symbol: str, mapping_path: Path | None = None) -> str:
    """Return the Alpaca ticker for ``symbol``; unmapped inputs pass through.

    Lookup order: explicit ``mapping_path`` > ``BTD_ALPACA_SYMBOLS`` env >
    ``config/alpaca_symbols.toml``. The parsed mapping is cached per-path.
    """
    mapping = _load(_resolve_path(mapping_path))
    return mapping.get(symbol, symbol)


def clear_cache() -> None:
    """Drop the cached mappings — primarily for tests."""
    _cache.clear()
