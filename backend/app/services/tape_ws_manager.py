"""
Smart Tape WebSocket Manager — OKX Edition
==========================================
Subscribes to OKX trades streams for multiple symbols
and broadcasts whale/large trade events to connected frontend clients.
Replaces Binance aggTrade (blocked on HuggingFace with 451 error).
"""

import asyncio
import json
import logging
import websockets
from typing import Set, Optional
from app.engines.order_flow_engine import WhaleTrade, order_flow_engine, FISH_THRESHOLD_USDT

logger = logging.getLogger(__name__)

# Symbols to monitor (OKX SWAP format: BTC-USDT-SWAP)
TAPE_SYMBOLS = [
    "BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "BNB-USDT-SWAP",
    "XRP-USDT-SWAP", "ADA-USDT-SWAP", "AVAX-USDT-SWAP", "DOT-USDT-SWAP",
    "LINK-USDT-SWAP", "DOGE-USDT-SWAP", "LTC-USDT-SWAP", "UNI-USDT-SWAP",
    "AAVE-USDT-SWAP", "NEAR-USDT-SWAP", "MATIC-USDT-SWAP", "ARB-USDT-SWAP",
    "OP-USDT-SWAP", "INJ-USDT-SWAP", "SUI-USDT-SWAP", "APT-USDT-SWAP",
]

OKX_WS_PUBLIC = "wss://ws.okx.com:8443/ws/v5/public"


class SmartTapeWSManager:
    """
    Manages OKX trades WebSocket connections
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
        """Start the OKX trades WebSocket listener."""
        if self._running:
            return
        self._running = True
        self._ws_task = asyncio.create_task(self._run_tape())
        logger.info("🎬 Smart Tape WebSocket manager started (OKX)")

    async def stop(self):
        self._running = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass

    async def _run_tape(self):
        """Main loop: connect to OKX public WebSocket and process trades."""
        # Build subscription args for OKX trades channel
        args = [{"channel": "trades", "instId": sym} for sym in TAPE_SYMBOLS]
        subscribe_msg = json.dumps({"op": "subscribe", "args": args})

        while self._running:
            try:
                logger.info(f"🔌 Connecting to OKX trades stream ({len(TAPE_SYMBOLS)} symbols)...")
                async with websockets.connect(
                    OKX_WS_PUBLIC,
                    ping_interval=20,
                    ping_timeout=10,
                    open_timeout=15,
                ) as ws:
                    # Subscribe to trades channels
                    await ws.send(subscribe_msg)
                    logger.info("✅ Smart Tape connected to OKX streams")

                    async for raw_msg in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(raw_msg)
                            # OKX sends: {"arg": {...}, "data": [{...}]}
                            if data.get("event") in ("subscribe", "error"):
                                continue
                            for trade in data.get("data", []):
                                await self._process_trade(trade, data.get("arg", {}).get("instId", ""))
                        except Exception as e:
                            logger.debug(f"Parse error: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                err_str = str(e)
                if "451" in err_str or "403" in err_str:
                    logger.error(f"🚫 OKX WebSocket BLOCKED ({err_str}). Stopping tape.")
                    self._running = False
                    break
                logger.warning(f"Smart Tape WS error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    async def _process_trade(self, trade: dict, inst_id: str):
        """Process a single OKX trade event and broadcast if whale."""
        # OKX trade format: {tradeId, instId, side, sz, px, ts}
        try:
            price = float(trade.get("px", 0))
            qty = float(trade.get("sz", 0))
            notional = price * qty

            if notional < self._threshold_usdt:
                return

            # Convert OKX instId (BTC-USDT-SWAP) to standard symbol (BTCUSDT)
            raw_inst = trade.get("instId", inst_id)
            symbol = raw_inst.replace("-USDT-SWAP", "USDT").replace("-USDT", "USDT")

            side = trade.get("side", "buy").upper()  # "buy" or "sell"
            ts = int(trade.get("ts", 0))

            whale = WhaleTrade(
                symbol=symbol,
                price=price,
                qty=qty,
                notional=notional,
                side=side,
                timestamp=ts,
                agg_trade_id=int(trade.get("tradeId", 0)),
            )

            # Cache it
            order_flow_engine.cache_whale(symbol, whale)

            # Broadcast to connected UI clients
            await self.broadcast({
                "type": "trade",
                "data": whale.to_dict(),
            })
        except Exception as e:
            logger.debug(f"Trade process error: {e}")


# Singleton
smart_tape_manager = SmartTapeWSManager()
