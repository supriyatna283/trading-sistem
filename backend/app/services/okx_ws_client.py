import asyncio
import json
import logging
from typing import Dict, Set
import websockets

from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

class OKXWebsocketClient:
    """Connects to OKX WebSocket and proxies data to FastAPI clients."""
    
    # Use standard 443 port for better firewall bypass, or 8443 if needed
    WS_URL = "wss://ws.okx.com:443/ws/v5/public"
    
    def __init__(self):
        self.active_channels: Set[str] = set() # Set of "candle1H:BTC-USDT" strings
        self.ws_connection = None
        self.reconnect_delay = 3
        self._running = False
        self._task = None

    async def start(self):
        """Starts the background connection to OKX."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._connect_and_listen())
        logger.info("OKX WebSocket Proxy client started.")

    async def stop(self):
        """Stops the OKX proxy."""
        self._running = False
        if self._task:
            self._task.cancel()
        if self.ws_connection:
            await self.ws_connection.close()
        logger.info("OKX WebSocket Proxy client stopped.")

    async def subscribe(self, symbol: str, interval: str):
        """Subscribe to a specific symbol and timeframe."""
        okx_symbol = symbol.upper()
        if "USDT" in okx_symbol and "-" not in okx_symbol:
            okx_symbol = okx_symbol.replace("USDT", "-USDT")
            
        okx_interval_map = {
            "1m": "candle1m", "5m": "candle5m", "15m": "candle15m",
            "1h": "candle1H", "4h": "candle4H", "1d": "candle1D",
        }
        channel = okx_interval_map.get(interval, "candle1H")
        sub_key = f"{channel}:{okx_symbol}"
        
        if sub_key not in self.active_channels:
            self.active_channels.add(sub_key)
            if self.ws_connection and self.ws_connection.open:
                req = {
                    "op": "subscribe",
                    "args": [{"channel": channel, "instId": okx_symbol}]
                }
                await self.ws_connection.send(json.dumps(req))
                logger.debug(f"OKX WS Subscribed: {sub_key}")

    async def subscribe_tickers(self, symbols: list[str]):
        """Subscribe to tickers channel for multiple symbols."""
        args = []
        for sym in symbols:
            okx_symbol = sym.upper()
            if "USDT" in okx_symbol and "-" not in okx_symbol:
                okx_symbol = okx_symbol.replace("USDT", "-USDT")
            
            sub_key = f"tickers:{okx_symbol}"
            if sub_key not in self.active_channels:
                self.active_channels.add(sub_key)
                args.append({"channel": "tickers", "instId": okx_symbol})
                
        if args and self.ws_connection and self.ws_connection.open:
            req = {"op": "subscribe", "args": args}
            await self.ws_connection.send(json.dumps(req))
            logger.debug(f"OKX WS Subscribed Tickers: {args}")

    async def _connect_and_listen(self):
        """Main loop handling connection, receiving, and reconnecting."""
        while self._running:
            try:
                async with websockets.connect(self.WS_URL) as ws:
                    self.ws_connection = ws
                    logger.info("✅ OKX WebSocket connected (Proxy).")
                    
                    # Resubscribe to all active channels on reconnect
                    if self.active_channels:
                        args = []
                        for ch in self.active_channels:
                            parts = ch.split(":")
                            if len(parts) == 2:
                                args.append({"channel": parts[0], "instId": parts[1]})
                        if args:
                            req = {"op": "subscribe", "args": args}
                            await ws.send(json.dumps(req))

                    while self._running:
                        msg = await ws.recv()
                        await self._handle_message(msg)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"⚠️ OKX WebSocket Error: {e}. Reconnecting in {self.reconnect_delay}s...")
                self.ws_connection = None
                if self._running:
                    await asyncio.sleep(self.reconnect_delay)

    async def _handle_message(self, message: str):
        """Parse OKX message and broadcast to local FastAPI clients."""
        try:
            data = json.loads(message)
            if "arg" in data and "data" in data and data["data"]:
                arg = data["arg"]
                channel = arg.get("channel", "")  # e.g., "candle1H"
                instId = arg.get("instId", "")    # e.g., "BTC-USDT"
                
                # Reverse mapping: candle1H -> 1h, BTC-USDT -> BTCUSDT
                interval_reverse_map = {
                    "candle1m": "1m", "candle5m": "5m", "candle15m": "15m",
                    "candle1H": "1h", "candle4H": "4h", "candle1D": "1d",
                }
                interval = interval_reverse_map.get(channel, "1h")
                local_symbol = instId.replace("-", "")
                
                # The format we expect in frontend: 
                # [ts, open, high, low, close, vol, volCcy, volCcyQuote, confirm]
                # OKX already sends this in data["data"][0].
                
                # Broadcast the raw parsed data to the specific local channel
                if channel.startswith("candle"):
                    local_channel_name = f"market:{local_symbol}:{interval}"
                    await ws_manager.send_to_channel(
                        local_channel_name, 
                        {"data": data["data"]} 
                    )
                elif channel == "tickers":
                    # Tickers go to the general "tickers" channel 
                    # so Scanner/Dashboard can read them all from one connection
                    await ws_manager.send_to_channel(
                        "tickers", 
                        {"data": data["data"]} 
                    )
        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.exception(f"Error handling OKX WS message: {e}")

# Global instance
okx_proxy = OKXWebsocketClient()
