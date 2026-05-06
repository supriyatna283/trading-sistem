"""Market data API endpoints — V2 resilient with auto-fallback."""

from fastapi import APIRouter, Query
from app.engines.market_data import MarketDataEngine

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
    timeframe: str = Query("1h", regex="^(1m|5m|15m|1h|4h|1d)$"),
    limit: int = Query(200, ge=1, le=1000),
):
    """
    Get OHLCV candle data for a symbol.
    Automatically tries Binance → sample data fallback.
    """
    df = await data_engine.get_candles(symbol.upper(), timeframe, limit)

    if df.empty:
        return {"symbol": symbol.upper(), "timeframe": timeframe, "candles": []}

    candles = df.to_dict(orient="records")
    # Convert timestamps to ISO strings
    for c in candles:
        if hasattr(c.get("open_time"), "isoformat"):
            c["open_time"] = c["open_time"].isoformat()

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "count": len(candles),
        "candles": candles,
    }
