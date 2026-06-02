from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from strategies.buy_the_dip import get_strategy

from ._common import build_strategy_config, load_config, snapshot_asset

SCHEMA_VERSION = 1


def _json_safe(value: Any) -> Any:
    """Recursively replace non-finite floats (NaN/inf) with None so the payload
    is valid JSON. Browsers' JSON.parse rejects literal NaN, which would break
    the web dashboard's fetch."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="btd-snapshot",
        description="Compute current indicator/signal snapshot for all configured assets",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    cfg = load_config()
    strategy = get_strategy(build_strategy_config(cfg))

    signals: list[dict] = []
    for symbol in cfg["data"]["assets"]:
        data = snapshot_asset(symbol)
        if data is None:
            continue
        signals.append(strategy.evaluate(data).to_dict())

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "signals": signals,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(_json_safe(payload), indent=2, allow_nan=False))
    print(f"wrote {args.output} ({len(signals)} signals)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
