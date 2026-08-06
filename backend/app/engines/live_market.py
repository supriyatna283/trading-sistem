import asyncio
import json
import logging
import httpx
import websockets
from typing import Dict, Any, List
from datetime import datetime

from app.engines.coingecko import coingecko_engine

logger = logging.getLogger(__name__)

BINANCE_WS_URL = "wss://stream.binance.com:9443/ws/!ticker@arr"
BINANCE_REST_URL = "https://api.binance.com/api/v3/ticker/24hr"
BINANCE_KLINE_URL = "https://api.binance.com/api/v3/klines"

# In-memory store for the latest ticker data
# Format: {"BTCUSDT": {"symbol": "BTCUSDT", "price": 60000.0, "change_24h": 2.5, "volume_24h": 1000000.0, "timestamp": 123456789}}
_in_memory_ticker_state: Dict[str, Dict[str, Any]] = {}
_sparkline_cache: Dict[str, Dict[str, Any]] = {}

class LiveMarketEngine:
    def __init__(self):
        self._running = False
        self._ws_task = None
        self._rest_client = httpx.AsyncClient(timeout=10.0)

    async def start(self):
        """Starts the WebSocket background task."""
        if self._running:
            return
        self._running = True
        self._ws_task = asyncio.create_task(self._ws_manager())
        logger.info("[LiveMarket] WebSocket manager started.")

    async def stop(self):
        """Stops the WebSocket background task."""
        self._running = False
        if self._ws_task:
            self._ws_task.cancel()
        await self._rest_client.aclose()
        logger.info("[LiveMarket] WebSocket manager stopped.")

    async def _ws_manager(self):
        """Maintains persistent WS connection to Binance."""
        retry_delay = 1
        while self._running:
            try:
                # We only care about tracking coins that are in our Top 100 list
                # This list will be refreshed occasionally by Coingecko, but for WS filtering,
                # we don't strictly need to filter here, we can just save everything to dict.
                # Python dict update is O(1) and very fast even for 2000 symbols.
                
                async with websockets.connect(BINANCE_WS_URL, ping_interval=20, ping_timeout=20) as ws:
                    logger.info(f"[LiveMarket] Connected to {BINANCE_WS_URL}")
                    retry_delay = 1  # reset delay on successful connection
                    
                    async for message in ws:
                        if not self._running:
                            break
                        
                        data = json.loads(message)
                        now = datetime.utcnow().timestamp()
                        
                        # !ticker@arr returns a list of dictionaries
                        for item in data:
                            symbol = item.get("s")
                            # Only store USDT pairs to save some memory
                            if not symbol.endswith("USDT"):
                                continue
                                
                            _in_memory_ticker_state[symbol] = {
                                "symbol": symbol,
                                "price": float(item.get("c", 0)),
                                "change_24h": float(item.get("P", 0)), # price change percent
                                "volume_24h": float(item.get("q", 0)), # quote volume
                                "timestamp": now
                            }
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[LiveMarket] WS Disconnected: {e}. Reconnecting in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60) # cap backoff to 60s

    async def get_snapshot(self, limit: int = 100) -> List[Dict]:
        """
        Returns the current market snapshot combining CoinGecko ranking + Live Binance prices.
        If in-memory state is empty (cold boot), triggers REST fallback.
        """
        top_coins = await coingecko_engine.get_top_usdt_pairs(limit=limit)
        
        # Cold Boot Fallback
        if not _in_memory_ticker_state:
            logger.info("[LiveMarket] In-memory state empty. Triggering REST fallback.")
            await self._fetch_rest_snapshot()
            
        result = []
        for coin in top_coins:
            symbol = coin["symbol"]
            ticker = _in_memory_ticker_state.get(symbol)
            if ticker:
                result.append({
                    **coin,
                    "price": ticker["price"],
                    "change_24h": ticker["change_24h"],
                    "volume_24h": ticker["volume_24h"],
                })
            else:
                # If ticker still missing (e.g., binance doesn't have it), just output empty fields
                result.append({
                    **coin,
                    "price": 0.0,
                    "change_24h": 0.0,
                    "volume_24h": 0.0,
                })
                
        return result

    async def _fetch_rest_snapshot(self):
        """Fetches ticker data from Binance REST API as a fallback."""
        try:
            resp = await self._rest_client.get(BINANCE_REST_URL)
            resp.raise_for_status()
            data = resp.json()
            now = datetime.utcnow().timestamp()
            
            for item in data:
                symbol = item.get("symbol")
                if not symbol.endswith("USDT"):
                    continue
                _in_memory_ticker_state[symbol] = {
                    "symbol": symbol,
                    "price": float(item.get("lastPrice", 0)),
                    "change_24h": float(item.get("priceChangePercent", 0)),
                    "volume_24h": float(item.get("quoteVolume", 0)),
                    "timestamp": now
                }
            logger.info("[LiveMarket] REST fallback snapshot successful.")
        except Exception as e:
            logger.error(f"[LiveMarket] REST fallback failed: {e}")

    async def get_sparklines(self, symbols: List[str]) -> Dict[str, List[float]]:
        """
        Fetches 7d historical closing prices for sparklines (4h interval = ~42 data points).
        Cached for 4 hours to prevent spamming Binance API.
        """
        now = datetime.utcnow().timestamp()
        results = {}
        to_fetch = []
        
        # Check cache
        for sym in symbols:
            cached = _sparkline_cache.get(sym)
            if cached and (now - cached["ts"] < 14400): # 4 hours cache
                results[sym] = cached["prices"]
            else:
                to_fetch.append(sym)
                
        if not to_fetch:
            return results
            
        # Concurrently fetch missing sparklines (limit concurrency)
        sem = asyncio.Semaphore(10)
        
        async def fetch_kline(symbol: str):
            async with sem:
                try:
                    resp = await self._rest_client.get(
                        BINANCE_KLINE_URL,
                        params={"symbol": symbol, "interval": "4h", "limit": 42} # 42 * 4h = 7 days
                    )
                    if resp.status_code == 200:
                        klines = resp.json()
                        # Closing price is index 4
                        prices = [float(k[4]) for k in klines]
                        _sparkline_cache[symbol] = {"prices": prices, "ts": now}
                        return symbol, prices
                except Exception as e:
                    logger.debug(f"[LiveMarket] Sparkline fetch failed for {symbol}: {e}")
                return symbol, []
                
        tasks = [fetch_kline(sym) for sym in to_fetch]
        fetched = await asyncio.gather(*tasks)
        
        for sym, prices in fetched:
            if prices:
                results[sym] = prices
                
        return results

live_market_engine = LiveMarketEngine()
