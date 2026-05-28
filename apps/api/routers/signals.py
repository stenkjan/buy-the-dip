from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from bot_core.data import YFinanceSource
from bot_core.indicators import ema, resample_ohlc, rsi_wilder
from bot_core.types import AssetData
from strategies.buy_the_dip import get_strategy

from ..schemas import SignalOut

router = APIRouter(prefix="/signals", tags=["signals"])

_DEFAULT_SYMBOLS = ("^NDX", "^GSPC")
_SYMBOLS_QUERY = Query(default=None)


def _evaluate(symbol: str) -> SignalOut:
    src = YFinanceSource()
    daily = src.fetch(symbol, "1d")
    if daily.empty or len(daily) < 250:
        raise HTTPException(status_code=502, detail=f"insufficient data for {symbol}")
    hourly = src.fetch(symbol, "1h")
    weekly = resample_ohlc(daily, "1W")
    h12 = resample_ohlc(hourly, "12h") if not hourly.empty else daily

    data = AssetData(
        symbol=symbol,
        timestamp=daily.index[-1].to_pydatetime(),
        last_close=float(daily["close"].iloc[-1]),
        ema200_daily=float(ema(daily["close"], 200).iloc[-1]),
        ema200_weekly=float(ema(weekly["close"], 200).iloc[-1]),
        rsi_12h=float(rsi_wilder(h12["close"], 14).iloc[-1]),
        rsi_1d=float(rsi_wilder(daily["close"], 14).iloc[-1]),
        rsi_1w=float(rsi_wilder(weekly["close"], 14).iloc[-1]),
    )
    sig = get_strategy().evaluate(data)
    return SignalOut(**sig.to_dict())


@router.get("/{symbol}", response_model=SignalOut)
def get_signal(symbol: str) -> SignalOut:
    return _evaluate(symbol)


@router.get("", response_model=list[SignalOut])
def list_signals(symbols: list[str] | None = _SYMBOLS_QUERY) -> list[SignalOut]:
    syms = symbols or list(_DEFAULT_SYMBOLS)
    return [_evaluate(s) for s in syms]
