from __future__ import annotations

import textwrap

from bot_core.data import to_alpaca_symbol
from bot_core.data.symbols import clear_cache


def test_default_mapping_ndx_to_qqq():
    clear_cache()
    assert to_alpaca_symbol("^NDX") == "QQQ"
    assert to_alpaca_symbol("^GSPC") == "SPY"


def test_passthrough_for_already_tradeable_ticker():
    clear_cache()
    assert to_alpaca_symbol("QQQ") == "QQQ"
    assert to_alpaca_symbol("AAPL") == "AAPL"


def test_unknown_index_passes_through():
    clear_cache()
    assert to_alpaca_symbol("^FAKEIDX") == "^FAKEIDX"


def test_custom_mapping_path(tmp_path):
    clear_cache()
    p = tmp_path / "custom.toml"
    p.write_text(textwrap.dedent("""
        [map]
        "^FOO" = "BAR"
    """))
    assert to_alpaca_symbol("^FOO", mapping_path=p) == "BAR"
    # falls back to passthrough for symbols not in this mapping
    assert to_alpaca_symbol("^NDX", mapping_path=p) == "^NDX"


def test_env_override(tmp_path, monkeypatch):
    clear_cache()
    p = tmp_path / "env.toml"
    p.write_text('[map]\n"^X" = "Y"\n')
    monkeypatch.setenv("BTD_ALPACA_SYMBOLS", str(p))
    assert to_alpaca_symbol("^X") == "Y"
