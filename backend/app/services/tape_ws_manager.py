"""
Smart Tape WebSocket Manager
==============================
Subscribes to Binance aggTrade streams for multiple symbols
and broadcasts whale/large trade events to connected frontend clients.
"""

import asyncio
import json
import logging
import websockets
from typing import Set, Dict, Optional
from app.engines.order_flow_engine import WhaleTrade, order_flow_engine, FISH_THRESHOLD_USDT

logger = logging.getLogger(__name__)

# Symbols to monitor (same as main watchlist)
TAPE_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT", "DOGEUSDT",
    "LTCUSDT", "UNIUSDT", "AAVEUSDT", "NEARUSDT", "MATICUSDT",
    "ARBUSDT", "OPUSDT", "INJUSDT", "SUIUSDT", "APTUSDT",
]

BINANCE_FUTURES_WS = "wss://fstream.binance.com/stream"


class SmartTapeWSManager:
    """
    Manages aggTrade WebSocket connections from Binance Futures
    and broadcasts whale trades to connected UI clients.
    """

    def __init__(self):
        self._clients: Set = set()
        self._running = False
        self._ws_task: Optional[asyncio.Task] = None
        self._threshold_usdt = FISH_THRESHOLD_USDT  # $1k minimum

    def set_threshold(self, usdt: float):
        self._threshold_usdt = usdt

    async def connect_client(self, websocket):
        """Register a new UI client connection."""
        self._clients.add(websocket)
        logger.info(f"📱 Smart Tape client connected (total: {len(self._clients)})")
        try:
            await websocket.wait_closed()
        finally:
            self._clients.discard(websocket)
            logger.info(f"📴 Smart Tape client disconnected (total: {len(self._clients)})")

    async def broadcast(self, data: dict):
        """Send a message to all connected UI clients."""
        if not self._clients:
            return
        msg = json.dumps(data)
        dead = set()
        for ws in self._clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)
        self._clients -= dead

    async def start(self):
        """Start the Binance aggTrade WebSocket listener."""
        if self._running:
            return
        self._running = True
        self._ws_task = asyncio.create_task(self._run_tape())
        logger.info("🎬 Smart Tape WebSocket manager started")

    async def stop(self):
        self._running = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass

    async def _run_tape(self):
        """Main loop: connect to Binance combined stream and process trades."""
        streams = "/".join(f"{s.lower()}@aggTrade" for s in TAPE_SYMBOLS)
        url = f"{BINANCE_FUTURES_WS}?streams={streams}"

        while self._running:
            try:
                logger.info(f"🔌 Connecting to Binance aggTrade stream ({len(TAPE_SYMBOLS)} symbols)...")
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("✅ Smart Tape connected to Binance streams")
                    async for raw_msg in ws:
                        if not self._running:
                            break
                        try:
                            envelope = json.loads(raw_msg)
                            data = envelope.get("data", {})
                            await self._process_trade(data)
                        except Exception as e:
                            logger.debug(f"Parse error: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Smart Tape WS error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    async def _process_trade(self, trade: dict):
        """Process a single aggTrade event and broadcast if whale."""
        if trade.get("e") != "aggTrade":
            return

        price = float(trade.get("p", 0))
        qty = float(trade.get("q", 0))
        notional = price * qty

        if notional < self._threshold_usdt:
            return

        symbol = trade.get("s", "")
        is_buyer_maker = trade.get("m", False)
        side = "SELL" if is_buyer_maker else "BUY"
        ts = int(trade.get("T", 0))

        whale = WhaleTrade(
            symbol=symbol,
            price=price,
            qty=qty,
            notional=notional,
            side=side,
            timestamp=ts,
            agg_trade_id=int(trade.get("a", 0)),
        )

        # Cache it
        order_flow_engine.cache_whale(symbol, whale)

        # Broadcast to connected UI clients
        await self.broadcast({
            "type": "trade",
            "data": whale.to_dict(),
        })


# Singleton
smart_tape_manager = SmartTapeWSManager()
