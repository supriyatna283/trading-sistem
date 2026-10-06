"""
AutoBot — Binance Futures Auto-Trader
=====================================
Features:
  • Auto-entry: buka LONG/SHORT dari sinyal chart
  • Auto-TP : close posisi saat unrealized PnL >= target ($10 default)
  • Trailing TP: geser peak, close saat profit turun > 30% dari peak
  • Auto-SL : close saat loss >= sl_usd ($3 default)
  • Telegram notif setiap entry / exit
  • Background async monitor loop (asyncio)
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
import httpx
from binance import AsyncClient, BinanceAPIException
from binance.enums import (
    SIDE_BUY, SIDE_SELL,
    ORDER_TYPE_MARKET,
    FUTURE_ORDER_TYPE_MARKET,
)

logger = logging.getLogger("autobot")

# ──────────────────────────────────────────────────────────────────────────────
# Config (overridden by AutoBotManager)
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_TP_USD     = 10.0    # close when profit >= $10
DEFAULT_SL_USD     = 3.0     # close when loss >= $3
DEFAULT_LEVERAGE   = 10
DEFAULT_MARGIN_USD = 20.0    # USDT collateral per trade
TRAILING_PULLBACK  = 0.30    # close when profit drops 30% from peak
MONITOR_INTERVAL   = 5       # seconds between position checks


# ──────────────────────────────────────────────────────────────────────────────
# Position state tracker
# ──────────────────────────────────────────────────────────────────────────────
class PositionState:
    def __init__(self, symbol: str, side: str, entry_price: float,
                 qty: float, order_id: str):
        self.symbol      = symbol
        self.side        = side          # "LONG" | "SHORT"
        self.entry_price = entry_price
        self.qty         = qty
        self.order_id    = order_id
        self.peak_pnl    = 0.0
        self.opened_at   = datetime.now(timezone.utc)

    def calc_pnl(self, mark_price: float) -> float:
        """Unrealized PnL in USDT"""
        if self.side == "LONG":
            return (mark_price - self.entry_price) * self.qty
        else:
            return (self.entry_price - mark_price) * self.qty


# ──────────────────────────────────────────────────────────────────────────────
# Telegram notification helper
# ──────────────────────────────────────────────────────────────────────────────
async def _send_telegram(token: str, chat_id: str, text: str) -> None:
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
            })
    except Exception as e:
        logger.warning(f"Telegram notify failed: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Main AutoBot Manager
# ──────────────────────────────────────────────────────────────────────────────
class AutoBotManager:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        telegram_token: str = "",
        telegram_chat_id: str = "",
        tp_usd: float = DEFAULT_TP_USD,
        sl_usd: float = DEFAULT_SL_USD,
        leverage: int = DEFAULT_LEVERAGE,
        margin_usd: float = DEFAULT_MARGIN_USD,
    ):
        self.api_key          = api_key
        self.api_secret       = api_secret
        self.telegram_token   = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.tp_usd           = tp_usd
        self.sl_usd           = sl_usd
        self.leverage         = leverage
        self.margin_usd       = margin_usd

        self._client: Optional[AsyncClient] = None
        self._positions: dict[str, PositionState] = {}  # symbol -> PositionState
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        self._trade_log: list[dict] = []   # in-memory trade history (last 200)
        self.enabled = False               # global kill-switch

    # ── lifecycle ──────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Initialize Binance client and start monitor loop."""
        if self._running:
            return
        self._client = await AsyncClient.create(self.api_key, self.api_secret)
        self._running = True
        self.enabled = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("AutoBot started")

    async def stop(self) -> None:
        """Gracefully stop the bot (does NOT close open positions)."""
        self._running = False
        self.enabled = False
        if self._monitor_task:
            self._monitor_task.cancel()
        if self._client:
            await self._client.close_connection()
        logger.info("AutoBot stopped")

    # ── entry ──────────────────────────────────────────────────────────────────

    async def open_position(
        self,
        symbol: str,
        direction: str,       # "BUY" | "SELL"
        margin_usd: Optional[float] = None,
    ) -> dict:
        """
        Open a Binance Futures MARKET order.
        Returns order info dict.
        """
        if not self.enabled:
            return {"error": "AutoBot is disabled"}
        if not self._client:
            return {"error": "Client not initialized — call start() first"}

        symbol  = symbol.upper().replace("/", "")
        if not symbol.endswith("USDT"):
            symbol += "USDT"

        # Already tracking this symbol?
        if symbol in self._positions:
            return {"error": f"Already in position for {symbol}"}

        margin = margin_usd or self.margin_usd
        side   = SIDE_BUY if direction.upper() == "BUY" else SIDE_SELL

        try:
            # 1. Set leverage
            await self._client.futures_change_leverage(
                symbol=symbol, leverage=self.leverage
            )

            # 2. Get current mark price to calc qty
            ticker = await self._client.futures_mark_price(symbol=symbol)
            mark   = float(ticker["markPrice"])

            # qty = notional / mark  (leverage already handled by margin)
            notional = margin * self.leverage
            qty      = round(notional / mark, 3)

            # 3. Place MARKET order
            order = await self._client.futures_create_order(
                symbol    = symbol,
                side      = side,
                type      = FUTURE_ORDER_TYPE_MARKET,
                quantity  = qty,
            )

            entry_price = float(order.get("avgPrice") or mark)
            order_id    = str(order["orderId"])
            pos_side    = "LONG" if direction.upper() == "BUY" else "SHORT"

            state = PositionState(symbol, pos_side, entry_price, qty, order_id)
            self._positions[symbol] = state

            msg = (
                f"🤖 <b>AutoBot ENTRY</b>\n"
                f"📌 {symbol} {pos_side}\n"
                f"💰 Entry: <code>{entry_price:.4f}</code>\n"
                f"📦 Qty: <code>{qty}</code>  Lev: <code>{self.leverage}x</code>\n"
                f"🎯 TP: +${self.tp_usd}  🛑 SL: -${self.sl_usd}"
            )
            await self._notify(msg)
            logger.info(f"Opened {pos_side} {symbol} @ {entry_price} qty={qty}")

            result = {
                "status": "opened",
                "symbol": symbol,
                "direction": pos_side,
                "entry_price": entry_price,
                "qty": qty,
                "leverage": self.leverage,
                "order_id": order_id,
                "tp_usd": self.tp_usd,
                "sl_usd": self.sl_usd,
            }
            self._log_trade({**result, "event": "ENTRY", "time": datetime.now(timezone.utc).isoformat()})
            return result

        except BinanceAPIException as e:
            logger.error(f"Binance API error on entry {symbol}: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error on entry {symbol}: {e}")
            return {"error": str(e)}

    # ── close ──────────────────────────────────────────────────────────────────

    async def close_position(self, symbol: str, reason: str = "manual") -> dict:
        """Close an open position by symbol."""
        symbol = symbol.upper().replace("/", "")
        if not symbol.endswith("USDT"):
            symbol += "USDT"

        state = self._positions.get(symbol)
        if not state:
            return {"error": f"No open position for {symbol}"}

        close_side = SIDE_SELL if state.side == "LONG" else SIDE_BUY

        try:
            order = await self._client.futures_create_order(
                symbol    = symbol,
                side      = close_side,
                type      = FUTURE_ORDER_TYPE_MARKET,
                quantity  = state.qty,
                reduceOnly= True,
            )
            close_price = float(order.get("avgPrice") or 0)
            pnl         = state.calc_pnl(close_price) if close_price else None

            del self._positions[symbol]

            emoji = "✅" if (pnl or 0) >= 0 else "❌"
            pnl_str = f"${pnl:+.2f}" if pnl is not None else "N/A"
            msg = (
                f"{emoji} <b>AutoBot EXIT</b> [{reason.upper()}]\n"
                f"📌 {symbol} closed\n"
                f"💸 PnL: <code>{pnl_str}</code>\n"
                f"🔒 Close @ <code>{close_price:.4f}</code>"
            )
            await self._notify(msg)
            logger.info(f"Closed {symbol} reason={reason} pnl={pnl_str}")

            result = {
                "status": "closed",
                "symbol": symbol,
                "reason": reason,
                "close_price": close_price,
                "pnl_usd": pnl,
            }
            self._log_trade({**result, "event": "EXIT", "time": datetime.now(timezone.utc).isoformat()})
            return result

        except BinanceAPIException as e:
            logger.error(f"Binance API error on close {symbol}: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error on close {symbol}: {e}")
            return {"error": str(e)}

    # ── monitor loop ───────────────────────────────────────────────────────────

    async def _monitor_loop(self) -> None:
        """
        Runs every MONITOR_INTERVAL seconds.
        Checks each tracked position's unrealized PnL and applies:
          • Auto-TP  : pnl >= tp_usd
          • Trailing : pnl >= tp_usd/2 AND drops 30% from peak
          • Auto-SL  : pnl <= -sl_usd
        """
        logger.info("Monitor loop started")
        while self._running:
            await asyncio.sleep(MONITOR_INTERVAL)
            if not self._positions or not self.enabled:
                continue

            # Fetch all mark prices in one call
            try:
                tickers = await self._client.futures_symbol_ticker()
                price_map = {t["symbol"]: float(t["price"]) for t in tickers}
            except Exception as e:
                logger.warning(f"Monitor fetch prices failed: {e}")
                continue

            for symbol, state in list(self._positions.items()):
                mark = price_map.get(symbol)
                if mark is None:
                    continue

                pnl = state.calc_pnl(mark)

                # Update trailing peak
                if pnl > state.peak_pnl:
                    state.peak_pnl = pnl

                # ── Decision logic ────────────────────────────────────────
                reason = None

                if pnl >= self.tp_usd:
                    # Hard TP hit
                    reason = "take_profit"

                elif (
                    state.peak_pnl >= self.tp_usd * 0.5
                    and pnl < state.peak_pnl * (1 - TRAILING_PULLBACK)
                ):
                    # Trailing TP: once we've seen ≥50% of TP, protect gains
                    reason = "trailing_tp"

                elif pnl <= -self.sl_usd:
                    # Stop-loss
                    reason = "stop_loss"

                if reason:
                    logger.info(
                        f"Closing {symbol}: reason={reason} "
                        f"pnl={pnl:+.2f} peak={state.peak_pnl:+.2f}"
                    )
                    await self.close_position(symbol, reason=reason)

    # ── helpers ────────────────────────────────────────────────────────────────

    async def _notify(self, text: str) -> None:
        await _send_telegram(self.telegram_token, self.telegram_chat_id, text)

    def _log_trade(self, entry: dict) -> None:
        self._trade_log.append(entry)
        if len(self._trade_log) > 200:
            self._trade_log = self._trade_log[-200:]

    # ── status / info ──────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        positions = []
        for sym, s in self._positions.items():
            positions.append({
                "symbol":      sym,
                "side":        s.side,
                "entry_price": s.entry_price,
                "qty":         s.qty,
                "peak_pnl":    round(s.peak_pnl, 3),
                "opened_at":   s.opened_at.isoformat(),
            })
        return {
            "enabled":       self.enabled,
            "running":       self._running,
            "open_positions": positions,
            "tp_usd":        self.tp_usd,
            "sl_usd":        self.sl_usd,
            "leverage":      self.leverage,
            "margin_usd":    self.margin_usd,
        }

    def get_trade_log(self, limit: int = 50) -> list:
        return list(reversed(self._trade_log[-limit:]))

    async def update_config(
        self,
        tp_usd: Optional[float] = None,
        sl_usd: Optional[float] = None,
        leverage: Optional[int] = None,
        margin_usd: Optional[float] = None,
        enabled: Optional[bool] = None,
    ) -> dict:
        if tp_usd is not None:
            self.tp_usd = tp_usd
        if sl_usd is not None:
            self.sl_usd = sl_usd
        if leverage is not None:
            self.leverage = leverage
        if margin_usd is not None:
            self.margin_usd = margin_usd
        if enabled is not None:
            self.enabled = enabled
        return self.get_status()


# ──────────────────────────────────────────────────────────────────────────────
# Singleton — initialized in main.py lifespan
# ──────────────────────────────────────────────────────────────────────────────
_bot_instance: Optional[AutoBotManager] = None


def get_bot() -> Optional[AutoBotManager]:
    return _bot_instance


def init_bot(
    api_key: str,
    api_secret: str,
    telegram_token: str = "",
    telegram_chat_id: str = "",
    tp_usd: float = DEFAULT_TP_USD,
    sl_usd: float = DEFAULT_SL_USD,
    leverage: int = DEFAULT_LEVERAGE,
    margin_usd: float = DEFAULT_MARGIN_USD,
) -> AutoBotManager:
    global _bot_instance
    _bot_instance = AutoBotManager(
        api_key=api_key,
        api_secret=api_secret,
        telegram_token=telegram_token,
        telegram_chat_id=telegram_chat_id,
        tp_usd=tp_usd,
        sl_usd=sl_usd,
        leverage=leverage,
        margin_usd=margin_usd,
    )
    return _bot_instance
