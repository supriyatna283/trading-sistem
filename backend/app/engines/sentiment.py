"""
Sentiment Analysis Engine (V2 - Binance)
==========================================
Fetches and aggregates macro sentiment data:
1. Fear & Greed Index (Alternative.me)
2. Funding Rates (Binance Futures)
3. Open Interest (Binance Futures)

All exchange data now uses Binance API instead of OKX.
"""

import httpx
import logging
from typing import Dict, Any, List
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class SentimentEngine:
    def __init__(self):
        self.fng_url = "https://api.alternative.me/fng/"
        self.binance_futures_base = "https://fapi.binance.com"
        self.client = httpx.AsyncClient(
            timeout=10.0,
            verify=False,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )

    async def get_fear_and_greed(self) -> Dict[str, Any]:
        """Fetch Crypto Fear & Greed Index."""
        try:
            response = await self.client.get(f"{self.fng_url}?limit=2")
            response.raise_for_status()
            data = response.json()
            if data and "data" in data and len(data["data"]) > 0:
                current = data["data"][0]
                previous = data["data"][1] if len(data["data"]) > 1 else None
                return {
                    "value": int(current["value"]),
                    "classification": current["value_classification"],
                    "timestamp": int(current["timestamp"]),
                    "previous_value": int(previous["value"]) if previous else None,
                    "previous_classification": previous["value_classification"] if previous else None,
                }
        except Exception as e:
            logger.error(f"Error fetching Fear & Greed Index: {e}")
        return {
            "value": 50,
            "classification": "Neutral",
            "timestamp": int(datetime.now().timestamp()),
            "previous_value": 50,
            "previous_classification": "Neutral"
        }

    async def get_funding_rates(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Fetch funding rates from Binance Futures /fapi/v1/premiumIndex."""
        results = []
        for symbol in symbols:
            try:
                url = f"{self.binance_futures_base}/fapi/v1/premiumIndex"
                response = await self.client.get(url, params={"symbol": symbol.upper()})
                response.raise_for_status()
                data = response.json()

                if data:
                    results.append({
                        "symbol": symbol,
                        "funding_rate": float(data.get("lastFundingRate", 0)),
                        "mark_price": float(data.get("markPrice", 0)),
                        "index_price": float(data.get("indexPrice", 0)),
                        "next_funding_time": int(data.get("nextFundingTime", 0)),
                        "timestamp": int(datetime.now().timestamp() * 1000),
                    })
            except Exception as e:
                logger.debug(f"Could not fetch Binance funding rate for {symbol}: {e}")
        return results

    async def get_open_interest(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Fetch open interest from Binance Futures /fapi/v1/openInterest."""
        results = []
        for symbol in symbols:
            try:
                url = f"{self.binance_futures_base}/fapi/v1/openInterest"
                response = await self.client.get(url, params={"symbol": symbol.upper()})
                response.raise_for_status()
                data = response.json()

                if data:
                    results.append({
                        "symbol": symbol,
                        "open_interest": float(data.get("openInterest", 0)),
                        "open_interest_coin": float(data.get("openInterest", 0)),
                        "timestamp": int(datetime.now().timestamp() * 1000),
                    })
            except Exception as e:
                logger.debug(f"Could not fetch Binance open interest for {symbol}: {e}")
        return results

    async def get_full_sentiment(self, top_symbols: List[str] = None) -> Dict[str, Any]:
        """Aggregate F&G, Funding Rates, and Open Interest from Binance."""
        if top_symbols is None:
            top_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]

        fng_task = self.get_fear_and_greed()
        funding_task = self.get_funding_rates(top_symbols)
        oi_task = self.get_open_interest(top_symbols)

        fng, funding, oi = await asyncio.gather(fng_task, funding_task, oi_task, return_exceptions=True)

        if isinstance(fng, Exception): fng = {}
        if isinstance(funding, Exception): funding = []
        if isinstance(oi, Exception): oi = []

        # Merge funding and oi by symbol
        market_metrics = []
        for symbol in top_symbols:
            f_data = next((item for item in funding if item["symbol"] == symbol), {})
            o_data = next((item for item in oi if item["symbol"] == symbol), {})

            if f_data or o_data:
                market_metrics.append({
                    "symbol": symbol,
                    "funding_rate": f_data.get("funding_rate", 0.0),
                    "mark_price": f_data.get("mark_price", 0.0),
                    "index_price": f_data.get("index_price", 0.0),
                    "next_funding_time": f_data.get("next_funding_time"),
                    "open_interest": o_data.get("open_interest", 0.0),
                    "open_interest_coin": o_data.get("open_interest_coin", 0.0),
                })

        return {
            "fear_and_greed": fng,
            "market_metrics": market_metrics,
            "timestamp": datetime.now().isoformat()
        }

    async def close(self):
        await self.client.aclose()
