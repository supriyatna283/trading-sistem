import asyncio
import json
import logging
from typing import Dict, Set, List
import websockets
import httpx

from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

class BinanceWebsocketClient:
    """Connects to Binance WebSocket and proxies data to FastAPI clients."""
    
    WS_URL_SPOT = "wss://stream.binance.com:9443/ws"
    WS_URL_FUTURES = "wss://fstream.binance.com/ws"
    
    def __init__(self):
        self.spot_channels: Set[str] = set()
        self.futures_channels: Set[str] = set()
        self.ws_spot = None
        self.ws_futures = None
        self.reconnect_delay = 3
        self._running = False
        self._tasks = []
        self._connected = asyncio.Event()  # Signals when at least one WS is connected
        self._msg_count = 0
        self.spot_symbols = set()
        self._fetched_spot = False

    async def _fetch_spot_symbols(self):
        try:
            async with httpx.AsyncClient(verify=False) as client:
                res = await client.get("https://api.binance.com/api/v3/exchangeInfo")
                data = res.json()
                for s in data.get("symbols", []):
                    if s["status"] == "TRADING":
                        self.spot_symbols.add(s["symbol"].lower())
            self._fetched_spot = True
        except Exception as e:
            logger.error(f"Failed to fetch spot symbols: {e}")

    async def start(self):
        """Starts the background connections to Binance."""
        if self._running:
            return
        self._running = True
        self._connected.clear()
        self._tasks = [
            asyncio.create_task(self._connect_and_listen(self.WS_URL_SPOT, True)),
            asyncio.create_task(self._connect_and_listen(self.WS_URL_FUTURES, False))
        ]
        logger.info("Binance WebSocket Proxy clients started (Spot + Futures).")

    async def stop(self):
        """Stops the Binance proxies."""
        self._running = False
        self._connected.set()  # Unblock any waiting subscribe calls
        for t in self._tasks:
            t.cancel()
        if self.ws_spot:
            await self.ws_spot.close()
        if self.ws_futures:
            await self.ws_futures.close()
        logger.info("Binance WebSocket Proxy clients stopped.")

    async def subscribe(self, symbol: str, interval: str):
        """Subscribe to a specific symbol and timeframe."""
        if not self._fetched_spot:
            await self._fetch_spot_symbols()

        symbol = symbol.lower()
        interval = interval.lower()
        stream_name = f"{symbol}@kline_{interval}"
        is_futures = symbol not in self.spot_symbols

        try:
            await asyncio.wait_for(self._connected.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning(f"Timed out waiting for Binance WS connection to subscribe {stream_name}")
            return
        
        req = {"method": "SUBSCRIBE", "params": [stream_name], "id": 1}

        if is_futures:
            if stream_name not in self.futures_channels:
                self.futures_channels.add(stream_name)
                if self.ws_futures and self.ws_futures.open:
                    await self.ws_futures.send(json.dumps(req))
                    logger.info(f"✅ Binance Futures WS Subscribed: {stream_name}")
        else:
            if stream_name not in self.spot_channels:
                self.spot_channels.add(stream_name)
                if self.ws_spot and self.ws_spot.open:
                    await self.ws_spot.send(json.dumps(req))
                    logger.info(f"✅ Binance Spot WS Subscribed: {stream_name}")

    async def subscribe_tickers(self, symbols: List[str]):
        """Subscribe to tickers channel for multiple symbols."""
        if not self._fetched_spot:
            await self._fetch_spot_symbols()

        spot_params = []
        futures_params = []
        
        for sym in symbols:
            sym_lower = sym.lower()
            stream_name = f"{sym_lower}@ticker"
            if sym_lower not in self.spot_symbols:
                if stream_name not in self.futures_channels:
                    self.futures_channels.add(stream_name)
                    futures_params.append(stream_name)
            else:
                if stream_name not in self.spot_channels:
                    self.spot_channels.add(stream_name)
                    spot_params.append(stream_name)

        if not spot_params and not futures_params:
            return
                
        try:
            await asyncio.wait_for(self._connected.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning(f"Timed out waiting for Binance WS for tickers subscription")
            return
        
        if spot_params and self.ws_spot and self.ws_spot.open:
            req = {"method": "SUBSCRIBE", "params": spot_params, "id": 2}
            await self.ws_spot.send(json.dumps(req))
            logger.info(f"🚀 Binance Spot WS Subscribed Tickers: {len(spot_params)} symbols")
            
        if futures_params and self.ws_futures and self.ws_futures.open:
            req = {"method": "SUBSCRIBE", "params": futures_params, "id": 2}
            await self.ws_futures.send(json.dumps(req))
            logger.info(f"🚀 Binance Futures WS Subscribed Tickers: {len(futures_params)} symbols")

    async def _connect_and_listen(self, url: str, is_spot: bool):
        """Main loop handling connection, receiving, and reconnecting."""
        while self._running:
            try:
                async with websockets.connect(url, open_timeout=10, ping_interval=20) as ws:
                    if is_spot:
                        self.ws_spot = ws
                    else:
                        self.ws_futures = ws
                        
                    self._connected.set()  # Signal that connection is ready
                    self._msg_count = 0
                    logger.info(f"✅ Connected to Binance WebSocket: {url}")
                    
                    channels = self.spot_channels if is_spot else self.futures_channels
                    if channels:
                        req = {
                            "method": "SUBSCRIBE",
                            "params": list(channels),
                            "id": 3
                        }
                        await ws.send(json.dumps(req))
                        logger.info(f"📡 Re-subscribed to {len(channels)} Binance channels on {url}")

                    async for message in ws:
                        if not self._running:
                            break
                        await self._handle_message(message)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"⚠️ Binance WebSocket Connection Error ({url}): {e}")
                if is_spot:
                    self.ws_spot = None
                else:
                    self.ws_futures = None
                    
                if self._running:
                    logger.info(f"Retrying Binance connection in {self.reconnect_delay}s...")
                    await asyncio.sleep(self.reconnect_delay)

    async def _handle_message(self, message: str):
        """Parse Binance message and broadcast to local clients."""
        try:
            data = json.loads(message)
            
            # Handle subscription response or pong
            if "result" in data or "id" in data:
                return

            event_type = data.get("e")
            symbol = data.get("s", "").upper()
            
            if event_type == "kline":
                k = data["k"]
                interval = k["i"]
                mapped_data = [
                    str(k["t"]),    # Timestamp
                    k["o"],         # Open
                    k["h"],         # High
                    k["l"],         # Low
                    k["c"],         # Close
                    k["v"]          # Volume
                ]
                
                local_channel_name = f"market:{symbol}:{interval}"
                await ws_manager.send_to_channel(
                    local_channel_name, 
                    {"data": [mapped_data]} 
                )
                
                # Log first few messages for debugging
                self._msg_count += 1
                if self._msg_count <= 3:
                    logger.info(f"📊 Binance kline → {symbol}/{interval}: close={k['c']}")
                
            elif event_type == "24hrTicker":
                mapped_ticker = {
                    "instId": symbol,
                    "last": data["c"],
                    "open24h": data["o"]
                }
                
                await ws_manager.send_to_channel(
                    "tickers", 
                    {"data": [mapped_ticker]} 
                )
                
        except Exception as e:
            logger.exception(f"Error handling Binance WS message: {e}")

# Global instance
binance_proxy = BinanceWebsocketClient()
