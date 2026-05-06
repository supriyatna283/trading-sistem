"""Market Intelligence API Router — BTC Dominance, Order Book, S/R, Liquidation, MCap."""

from fastapi import APIRouter, Query
from app.engines.market_intel import MarketIntelEngine
from app.engines.market_data import MarketDataEngine

router = APIRouter(prefix="/api/v1/market-intel", tags=["Market Intelligence"])
intel_engine = MarketIntelEngine()
data_engine = MarketDataEngine()


@router.get("/btc-dominance")
async def get_btc_dominance():
    """Get BTC market dominance percentage and global market data."""
    return await intel_engine.get_btc_dominance()


@router.get("/orderbook/{symbol}")
async def get_orderbook(symbol: str, limit: int = Query(20, ge=5, le=100)):
    """Get order book depth analysis with buy/sell ratio."""
    return await intel_engine.get_order_book_depth(symbol, limit)


@router.get("/support-resistance/{symbol}")
async def get_support_resistance(symbol: str, timeframe: str = Query("1h")):
    """Get Support & Resistance levels from pivot points."""
    df = await data_engine.get_candles(symbol, timeframe, 200)
    return intel_engine.calculate_support_resistance(df, symbol)


@router.get("/liquidation-levels/{symbol}")
async def get_liquidation_levels(symbol: str):
    """Get estimated liquidation level clusters."""
    df = await data_engine.get_candles(symbol, "1h", 1)
    price = float(df.iloc[-1]["close"]) if not df.empty else 0
    return intel_engine.calculate_liquidation_levels(price, symbol)


@router.get("/market-cap/{symbol}")
async def get_market_cap(symbol: str):
    """Get market cap and circulating supply data."""
    return await intel_engine.get_market_cap(symbol)


@router.get("/overview/{symbol}")
async def get_overview(symbol: str, timeframe: str = Query("1h")):
    """Get combined market intelligence overview for one symbol."""
    df = await data_engine.get_candles(symbol, timeframe, 200)
    price = float(df.iloc[-1]["close"]) if not df.empty else 0
    return await intel_engine.get_overview(symbol, df, price)
