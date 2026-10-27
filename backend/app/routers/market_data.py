"""Market data API endpoints — V2 resilient with auto-fallback."""

from fastapi import APIRouter, Query
from app.engines.market_data import (
    MarketDataEngine,
    TIMEFRAME_REGEX,
    SOURCE_SYNTHETIC,
)

router = APIRouter(prefix="/api/v1/market", tags=["Market Data"])

data_engine = MarketDataEngine()


@router.get("/symbols")
async def list_symbols():
    """List available trading symbols dynamically from Binance."""
    symbols = await data_engine.fetch_symbols()
    return {"symbols": symbols}


@router.get("/candles/{symbol}")
async def get_candles(
    symbol: str,
    timeframe: str = Query("1h", pattern=TIMEFRAME_REGEX),
    limit: int = Query(200, ge=1, le=1000),
):
    """
    Get OHLCV candle data for a symbol.
    Automatically tries OKX → Binance → sample data fallback.
    open_time is always returned as a UTC ISO-8601 string (with 'Z' suffix)
    so browsers always parse it as UTC, avoiding local-timezone offset bugs
    that cause duplicate / misplaced candles on the chart.

    The response always carries `source` ("okx" | "binance" | "synthetic" | "none")
    and `is_synthetic`. When `is_synthetic` is true every real source failed and the
    candles are a random walk — clients must warn the user and must not trade on it.
    """
    df, source = await data_engine.get_candles_with_source(symbol.upper(), timeframe, limit)

    if df.empty:
        return {
            "symbol": symbol.upper(), "timeframe": timeframe,
            "source": "none", "is_synthetic": False,
            "count": 0, "candles": [],
        }

    candles = df.to_dict(orient="records")
    # Convert pandas Timestamps → UTC ISO strings (always append 'Z')
    for c in candles:
        ot = c.get("open_time")
        if hasattr(ot, "isoformat"):
            c["open_time"] = ot.isoformat() + "Z"
        elif isinstance(ot, (int, float)):
            # Fallback: already a unix-ms integer → keep as-is
            pass

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "source": source,
        "is_synthetic": source == SOURCE_SYNTHETIC,
        "count": len(candles),
        "candles": candles,
    }
