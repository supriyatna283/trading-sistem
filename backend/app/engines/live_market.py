import asyncio
import json
import logging
import httpx
import websockets
from typing import Dict, Any, List
from datetime import datetime

from app.engines.coingecko import coingecko_engine

logger = logging.getLogger(__name__)

# Using data-stream.binance.vision and data-api.binance.vision to bypass US IP blocks on HuggingFace
BINANCE_WS_URL = "wss://data-stream.binance.vision:9443/ws/!ticker@arr"
BINANCE_REST_URL = "https://data-api.binance.vision/api/v3/ticker/24hr"
BINANCE_KLINE_URL = "https://data-api.binance.vision/api/v3/klines"

# In-memory store for the latest ticker data
# Format: {"BTCUSDT": {"symbol": "BTCUSDT", "price": 60000.0, "change_24h": 2.5, "volume_24h": 1000000.0, "timestamp": 123456789}}
_in_memory_ticker_state: Dict[str, Dict[str, Any]] = {}
_sparkline_cache: Dict[str, Dict[str, Any]] = {}

class LiveMarketEngine:
    def __init__(self):
        self._running = False
        self._ws_task = None
        self._rest_client = httpx.AsyncClient(timeout=10.0)
        
        # Pub/Sub system
        self._subscribers: List[asyncio.Queue] = []
        self.status = "DEGRADED"  # Start degraded until WS connects
        self._last_rest_poll = 0

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
        
        # Cleanup subscribers
        for q in self._subscribers:
            await q.put(None) # Sentinel to stop generators
        self._subscribers.clear()
        logger.info("[LiveMarket] WebSocket manager stopped.")

    def subscribe(self) -> asyncio.Queue:
        """Returns a queue to listen for price updates."""
        q = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        """Removes a subscriber queue."""
        if q in self._subscribers:
            self._subscribers.remove(q)

    def _broadcast(self, updates: List[Dict]):
        """Sends updates to all subscribers."""
        if not updates and self.status == "LIVE":
            return
            
        # We also want to broadcast status changes, so we package the payload
        payload = {
            "status": self.status,
            "updates": updates
        }
        
        for q in self._subscribers:
            # Non-blocking put, if queue is full (client too slow), we could drop, but asyncio.Queue is unbounded by default
            q.put_nowait(payload)

    async def _ws_manager(self):
        """Maintains persistent WS connection to Binance, with fallback REST polling."""
        retry_delay = 1
        
        while self._running:
            try:
                # If we are reconnecting, we are in degraded mode
                if self.status != "DEGRADED":
                    self.status = "DEGRADED"
                    self._broadcast([]) # Broadcast status change
                
                async with websockets.connect(BINANCE_WS_URL, ping_interval=20, ping_timeout=20) as ws:
                    logger.info(f"[LiveMarket] Connected to {BINANCE_WS_URL}")
                    retry_delay = 1  # reset delay on successful connection
                    self.status = "LIVE"
                    self._broadcast([]) # Broadcast status change
                    
                    async for message in ws:
                        if not self._running:
                            break
                        
                        data = json.loads(message)
                        now = datetime.utcnow().timestamp()
                        updates = []
                        
                        for item in data:
                            symbol = item.get("s")
                            if not symbol.endswith("USDT"):
                                continue
                                
                            new_price = float(item.get("c", 0))
                            new_volume = float(item.get("q", 0))
                            
                            # Determine if price actually changed to prevent broadcast spam
                            old_state = _in_memory_ticker_state.get(symbol)
                            
                            # Spike detection
                            spike_type = None
                            spike_vol = 0
                            
                            if old_state:
                                vol_diff = new_volume - old_state["volume_24h"]
                                # Lowered threshold to 5k USDT for more frequent visual feedback
                                if vol_diff > 5000 and vol_diff < new_volume: # avoid cold boot spikes
                                    spike_vol = vol_diff
                                    if new_price > old_state["price"]:
                                        spike_type = "buy"
                                    elif new_price < old_state["price"]:
                                        spike_type = "sell"
                                    else:
                                        spike_type = "neutral"
                            
                            if not old_state or old_state["price"] != new_price or spike_type:
                                _in_memory_ticker_state[symbol] = {
                                    "symbol": symbol,
                                    "price": new_price,
                                    "change_24h": float(item.get("P", 0)),
                                    "volume_24h": new_volume,
                                    "timestamp": now,
                                    # Temporary fields for SSE payload, will be cleared by frontend
                                    "spike": spike_type,
                                    "spike_vol": spike_vol
                                }
                                updates.append(_in_memory_ticker_state[symbol])
                        
                        # Throttle broadcasts slightly to prevent overwhelming the event loop if there are huge bursts
                        if updates:
                            self._broadcast(updates)
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[LiveMarket] WS Disconnected: {e}. Reconnecting in {retry_delay}s...")
                
                # Degraded Mode REST Polling
                # If we wait a long time, poll REST to keep data fresh
                self.status = "DEGRADED"
                self._broadcast([])
                
                waited = 0
                while waited < retry_delay and self._running:
                    now = datetime.utcnow().timestamp()
                    # Poll every 30 seconds while degraded
                    if now - self._last_rest_poll > 30:
                        logger.info("[LiveMarket] WS is down. Polling REST API...")
                        await self._fetch_rest_snapshot()
                        self._last_rest_poll = now
                        
                    await asyncio.sleep(1)
                    waited += 1
                    
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
            
            updates = []
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
                updates.append(_in_memory_ticker_state[symbol])
                
            self._broadcast(updates)
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
