"""
Bybit WebSocket Service
========================
Connects to Bybit WebSocket for real-time kline/candle data.
"""

import asyncio
import json
import logging
import websockets
from typing import Callable, Optional

logger = logging.getLogger(__name__)

BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/linear"


class BybitWebSocket:
    """Manages Bybit WebSocket stream for real-time candle data."""

    def __init__(self, on_message: Optional[Callable] = None):
        self.on_message = on_message
        self.running = False
        self._ws = None

    async def subscribe_kline(self, symbol: str, interval: str = "1"):
        """Subscribe to a Bybit kline stream."""
        self.running = True

        while self.running:
            try:
                async with websockets.connect(BYBIT_WS_URL) as ws:
                    self._ws = ws
                    sub_msg = {
                        "op": "subscribe",
                        "args": [f"kline.{interval}.{symbol.upper()}"]
                    }
                    await ws.send(json.dumps(sub_msg))
                    logger.info(f"Bybit WS subscribed: kline.{interval}.{symbol}")

                    async for msg in ws:
                        data = json.loads(msg)
                        if data.get("topic", "").startswith("kline"):
                            parsed = self._parse_kline(data)
                            if parsed and self.on_message:
                                await self.on_message(parsed)
            except Exception as e:
                logger.error(f"Bybit WS error: {e}")
                if self.running:
                    await asyncio.sleep(5)

    def _parse_kline(self, data: dict) -> Optional[dict]:
        """Parse Bybit kline WebSocket message."""
        items = data.get("data", [])
        if not items:
            return None
        k = items[0]
        return {
            "symbol": data.get("topic", "").split(".")[-1],
            "timeframe": data.get("topic", "").split(".")[1],
            "open_time": int(k.get("start", 0)),
            "open": float(k.get("open", 0)),
            "high": float(k.get("high", 0)),
            "low": float(k.get("low", 0)),
            "close": float(k.get("close", 0)),
            "volume": float(k.get("volume", 0)),
            "is_closed": k.get("confirm", False),
        }

    async def stop(self):
        self.running = False
        if self._ws:
            await self._ws.close()
