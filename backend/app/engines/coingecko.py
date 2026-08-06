import httpx
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Cache state
_mcap_cache: Optional[Dict] = None
_valid_symbols_cache: Optional[set] = None
_valid_symbols_ts: float = 0
_CACHE_TTL_SECONDS = 3600  # 1 hour

class CoinGeckoEngine:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=15.0)

    async def _get_valid_binance_symbols(self) -> set:
        """Fetch and cache all valid USDT symbols from Binance."""
        global _valid_symbols_cache, _valid_symbols_ts
        now = datetime.now(timezone.utc).timestamp()
        
        if _valid_symbols_cache and now - _valid_symbols_ts < 86400: # 24h cache
            return _valid_symbols_cache
            
        try:
            # Using data-api.binance.vision to bypass US geo-blocking on cloud servers (e.g. HuggingFace)
            resp = await self.client.get("https://data-api.binance.vision/api/v3/exchangeInfo")
            resp.raise_for_status()
            data = resp.json()
            
            valid_symbols = set()
            for s in data.get("symbols", []):
                if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT":
                    valid_symbols.add(s.get("symbol"))
                    
            _valid_symbols_cache = valid_symbols
            _valid_symbols_ts = now
            logger.info(f"[CoinGecko] Cached {len(valid_symbols)} valid Binance USDT symbols.")
            return valid_symbols
        except Exception as e:
            logger.error(f"[CoinGecko] Failed to fetch exchangeInfo: {e}")
            return _valid_symbols_cache or set()

    async def get_top_usdt_pairs(self, limit: int = 150) -> List[Dict]:
        """
        Fetches the top coins by market cap from CoinGecko and formats them as Binance USDT pairs.
        Validates against Binance exchangeInfo so dead/non-listed coins are excluded.
        Returns a list of dicts.
        """
        global _mcap_cache
        now = datetime.now(timezone.utc).timestamp()

        # Return from cache if valid
        if _mcap_cache and now - _mcap_cache["ts"] < _CACHE_TTL_SECONDS:
            return _mcap_cache["data"][:limit]

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

            valid_binance_symbols = await self._get_valid_binance_symbols()

            results = []
            # Common stablecoins or tokens that don't have a direct USDT pair or are redundant
            ignore_symbols = {"usdt", "usdc", "fdusd", "tusd", "busd", "dai", "wbtc", "steth"}

            for item in data:
                cg_symbol = item.get("symbol", "").lower()
                if cg_symbol in ignore_symbols:
                    continue

                binance_symbol = f"{cg_symbol.upper()}USDT"
                
                # Validation: Skip if not a valid trading pair on Binance
                if valid_binance_symbols and binance_symbol not in valid_binance_symbols:
                    continue
                
                results.append({
                    "symbol": binance_symbol,
                    "market_cap_rank": item.get("market_cap_rank"),
                    "market_cap": item.get("market_cap"),
                    "name": item.get("name"),
                    "image": item.get("image")
                })
                # Removed break on limit so we cache everything

            # Cache the full results
            _mcap_cache = {"data": results, "ts": now}
            logger.info(f"[CoinGecko] Cached top {len(results)} pairs by market cap.")
            return results[:limit]

        except Exception as e:
            logger.error(f"[CoinGecko] Error fetching market cap data: {e}")
            if _mcap_cache:
                return _mcap_cache["data"][:limit]
            return []

    async def close(self):
        await self.client.aclose()

coingecko_engine = CoinGeckoEngine()
