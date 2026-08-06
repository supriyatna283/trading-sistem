import httpx
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Cache state
_mcap_cache: Optional[Dict] = None
_CACHE_TTL_SECONDS = 3600  # 1 hour

class CoinGeckoEngine:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=15.0)

    async def get_top_usdt_pairs(self, limit: int = 150) -> List[Dict]:
        """
        Fetches the top coins by market cap from CoinGecko and formats them as Binance USDT pairs.
        Returns a list of dicts: {"symbol": "BTCUSDT", "market_cap_rank": 1, "market_cap": 1000000000, "name": "Bitcoin"}
        """
        global _mcap_cache
        now = datetime.now(timezone.utc).timestamp()

        # Return from cache if valid
        if _mcap_cache and now - _mcap_cache["ts"] < _CACHE_TTL_SECONDS:
            return _mcap_cache["data"]

        try:
            # We fetch up to 200 to ensure we have enough after filtering out stablecoins/non-binance pairs if needed
            resp = await self.client.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 200,
                    "page": 1,
                    "sparkline": "false"
                }
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            # Common stablecoins or tokens that don't have a direct USDT pair or are redundant
            ignore_symbols = {"usdt", "usdc", "fdusd", "tusd", "busd", "dai", "wbtc", "steth"}

            for item in data:
                cg_symbol = item.get("symbol", "").lower()
                if cg_symbol in ignore_symbols:
                    continue

                binance_symbol = f"{cg_symbol.upper()}USDT"
                
                results.append({
                    "symbol": binance_symbol,
                    "market_cap_rank": item.get("market_cap_rank"),
                    "market_cap": item.get("market_cap"),
                    "name": item.get("name"),
                    "image": item.get("image")
                })
                
                if len(results) >= limit:
                    break

            # Cache the results
            _mcap_cache = {"data": results, "ts": now}
            logger.info(f"[CoinGecko] Fetched top {len(results)} pairs by market cap.")
            return results

        except Exception as e:
            logger.error(f"[CoinGecko] Error fetching market cap data: {e}")
            if _mcap_cache:
                return _mcap_cache["data"]
            return []

    async def close(self):
        await self.client.aclose()

coingecko_engine = CoinGeckoEngine()
