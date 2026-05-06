"""
OKX WebSocket Service
======================
Connects to OKX v5 Public WebSocket for real-time kline/candle data.
"""

import asyncio
import json
import logging
import websockets
from typing import Callable, Optional

logger = logging.getLogger(__name__)

OKX_WS_PUBLIC = "wss://ws.okx.com:8443/ws/v5/public"


class OKXWebSocket:
    """Manages OKX WebSocket stream for real-time candle data."""

    def __init__(self, on_message: Optional[Callable] = None):
        self.on_message = on_message
        self.running = False
        self._ws = None

    async def subscribe_kline(self, symbol: str, interval: str = "1m"):
        """Subscribe to an OKX kline (candle) channel."""
        # Convert BTCUSDT -> BTC-USDT
        inst_id = symbol.upper()
        if "USDT" in inst_id and "-" not in inst_id:
            inst_id = inst_id.replace("USDT", "-USDT")

        okx_interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m",
            "1h": "1H", "4h": "4H", "1d": "1D",
        }
        bar = okx_interval_map.get(interval, "1m")

        self.running = True

        while self.running:
            try:
                async with websockets.connect(OKX_WS_PUBLIC) as ws:
                    self._ws = ws
                    sub_msg = {
                        "op": "subscribe",
                        "args": [{"channel": f"candle{bar}", "instId": inst_id}]
                    }
                    await ws.send(json.dumps(sub_msg))
                    logger.info(f"OKX WS subscribed: candle{bar}.{inst_id}")

                    async for msg in ws:
                        data = json.loads(msg)
                        if "data" in data and data["data"]:
                            parsed = self._parse_kline(data, inst_id, interval)
                            if parsed and self.on_message:
                                await self.on_message(parsed)
            except Exception as e:
                logger.error(f"OKX WS error: {e}")
                if self.running:
                    await asyncio.sleep(5)

    def _parse_kline(self, data: dict, inst_id: str, interval: str) -> Optional[dict]:
        """Parse OKX candle WebSocket message.
        OKX candle data: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
        """
        items = data.get("data", [])
        if not items:
            return None
        k = items[0]
        # Convert BTC-USDT back to BTCUSDT
        symbol = inst_id.replace("-", "")
        return {
            "symbol": symbol,
            "timeframe": interval,
            "open_time": int(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "is_closed": k[8] == "1" if len(k) > 8 else False,
        }

    async def stop(self):
        self.running = False
        if self._ws:
            await self._ws.close()
