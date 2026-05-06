"""Sentiment API Router."""

from fastapi import APIRouter
from app.engines.sentiment import SentimentEngine

router = APIRouter(prefix="/api/v1/sentiment", tags=["Market Sentiment"])
engine = SentimentEngine()

@router.get("/")
async def get_market_sentiment():
    """Fetch aggregated Fear & Greed, Funding Rates, and Open Interest."""
    # We'll use 8 top liquidity coins for the dashboard
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT"]
    data = await engine.get_full_sentiment(top_symbols=symbols)
    return data
