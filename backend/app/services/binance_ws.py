"""
Binance WebSocket Service
==========================
Connects to Binance WebSocket for real-time kline/candle data.
"""

import asyncio
import json
import logging
import websockets
from typing import Callable, Optional

logger = logging.getLogger(__name__)

BINANCE_WS_BASE = "wss://stream.binance.com:9443/ws"


class BinanceWebSocket:
    """Manages Binance WebSocket stream for real-time candle data."""

    def __init__(self, on_message: Optional[Callable] = None):
        self.on_message = on_message
        self.running = False
        self._ws = None

    async def subscribe_kline(self, symbol: str, interval: str = "1m"):
        """Subscribe to a kline stream."""
        stream = f"{symbol.lower()}@kline_{interval}"
        url = f"{BINANCE_WS_BASE}/{stream}"
        self.running = True

        while self.running:
            try:
                async with websockets.connect(url) as ws:
                    self._ws = ws
                    logger.info(f"Binance WS connected: {stream}")
                    async for msg in ws:
                        data = json.loads(msg)
                        if self.on_message:
                            await self.on_message(self._parse_kline(data))
            except Exception as e:
                logger.error(f"Binance WS error: {e}")
                if self.running:
                    await asyncio.sleep(5)

    def _parse_kline(self, data: dict) -> dict:
        """Parse Binance kline WebSocket message."""
        k = data.get("k", {})
        return {
            "symbol": k.get("s", ""),
            "timeframe": k.get("i", ""),
            "open_time": k.get("t", 0),
            "open": float(k.get("o", 0)),
            "high": float(k.get("h", 0)),
            "low": float(k.get("l", 0)),
            "close": float(k.get("c", 0)),
            "volume": float(k.get("v", 0)),
            "is_closed": k.get("x", False),
        }

    async def stop(self):
        self.running = False
        if self._ws:
            await self._ws.close()
