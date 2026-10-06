"""
AutoBot — Binance Futures Auto-Trader
=====================================
Features:
  • Auto-entry: buka LONG/SHORT dari sinyal chart (SMC setup cache)
  • Auto-TP : close posisi saat unrealized PnL >= target ($10 default)
  • Trailing TP: geser peak, close saat profit turun > 30% dari peak
  • Auto-SL : close saat loss >= sl_usd ($3 default)
  • Structure SL: close bila harga menembus SL struktur dari setup
  • Telegram notif setiap entry / exit
  • Background async monitor loop (asyncio)

Auto-Entry flow:
  auto_scheduler → push setup ke live_alert_scanner cache
  AutoBot._auto_entry_loop (tiap 20 detik):
      filter skor/RR/umur setup → cek harga Binance Futures
      harga masuk zona entry & belum tembus SL → MARKET order
  Guard: max posisi, cooldown per pair, daily loss limit,
         skip pair dengan sinyal BUY & SELL bertabrakan.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Optional
import httpx

try:
    from binance.client import AsyncClient
    from binance.exceptions import BinanceAPIException
    BINANCE_AVAILABLE = True
except ImportError:
    AsyncClient = None  # type: ignore
    BinanceAPIException = Exception  # type: ignore
    BINANCE_AVAILABLE = False

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
SYNC_EVERY_N_LOOPS = 12      # sync with exchange every ~60s

# Auto-entry defaults
AUTO_ENTRY_INTERVAL      = 20     # seconds between auto-entry scans
DEFAULT_MIN_SCORE        = 18.0   # confluence score (out of 30)
DEFAULT_MIN_RR           = 1.8
DEFAULT_MAX_POSITIONS    = 3
DEFAULT_COOLDOWN_MIN     = 120    # per-symbol cooldown after exit
DEFAULT_MAX_SETUP_AGE_H  = 6.0    # ignore setups older than this
DEFAULT_MAX_DAILY_LOSS   = 10.0   # pause auto-entry after -$10 realized/day
ENTRY_TOLERANCE          = 0.002  # 0.2% around entry zone
CLIENT_ID_PREFIX         = "autobot_"


def _round_step(value: float, step: float) -> float:
    """Floor value to exchange step size."""
    if not step or step <= 0:
        return value
    d_step = Decimal(str(step))
    d = (Decimal(str(value)) / d_step).to_integral_value(rounding=ROUND_DOWN) * d_step
    return float(d)


# ──────────────────────────────────────────────────────────────────────────────
# Position state tracker
# ──────────────────────────────────────────────────────────────────────────────
class PositionState:
    def __init__(self, symbol: str, side: str, entry_price: float,
                 qty: float, order_id: str, setup_sl: Optional[float] = None,
                 source: str = "manual", setup_info: Optional[dict] = None):
        self.symbol      = symbol
        self.side        = side          # "LONG" | "SHORT"
        self.entry_price = entry_price
        self.qty         = qty
        self.order_id    = order_id
        self.peak_pnl    = 0.0
        self.last_pnl    = 0.0
        self.last_mark   = entry_price
        self.setup_sl    = setup_sl      # structural invalidation level
        self.source      = source        # "auto" | "manual" | "synced"
        self.setup_info  = setup_info or {}
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
        auto_entry: bool = True,
    ):
        self.api_key          = api_key
        self.api_secret       = api_secret
        self.telegram_token   = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.tp_usd           = tp_usd
        self.sl_usd           = sl_usd
        self.leverage         = leverage
        self.margin_usd       = margin_usd

        # Auto-entry settings
        self.auto_entry       = auto_entry
        self.min_score        = DEFAULT_MIN_SCORE
        self.min_rr           = DEFAULT_MIN_RR
        self.max_positions    = DEFAULT_MAX_POSITIONS
        self.cooldown_min     = DEFAULT_COOLDOWN_MIN
        self.max_setup_age_h  = DEFAULT_MAX_SETUP_AGE_H
        self.max_daily_loss   = DEFAULT_MAX_DAILY_LOSS
        self.timeframes       = ["1h", "4h"]

        self._client: Optional[AsyncClient] = None
        self._positions: dict[str, PositionState] = {}  # symbol -> PositionState
        self._monitor_task: Optional[asyncio.Task] = None
        self._auto_task: Optional[asyncio.Task] = None
        self._running = False
        self._trade_log: list[dict] = []   # in-memory trade history (last 200)
        self.enabled = False               # global kill-switch

        self._entry_lock = asyncio.Lock()
        self._symbol_filters: dict[str, dict] = {}  # symbol -> {step, min_qty, min_notional}
        self._hedge_mode = False
        self._cooldowns: dict[str, datetime] = {}   # symbol -> cooldown until
        self._traded_setups: set[str] = set()       # setup keys already executed
        self._daily_pnl = 0.0
        self._daily_date = datetime.now(timezone.utc).date()
        self._external_positions: list[str] = []    # positions not opened by bot
        self._auto_state: dict = {
            "last_scan_at": None,
            "setups_in_cache": 0,
            "candidates": 0,
            "watchlist": [],
            "last_action": None,
            "paused_reason": None,
            "total_auto_entries": 0,
        }

    # ── lifecycle ──────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Initialize Binance client and start monitor + auto-entry loops."""
        if self._running:
            return
        if not BINANCE_AVAILABLE or AsyncClient is None:
            raise RuntimeError("python-binance not available")
        self._client = await AsyncClient.create(self.api_key, self.api_secret)
        self._running = True
        self.enabled = True

        await self._load_exchange_info()
        await self._detect_position_mode()
        await self._sync_positions(initial=True)

        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self._auto_task = asyncio.create_task(self._auto_entry_loop())
        logger.info(f"AutoBot started (auto_entry={self.auto_entry})")

    async def stop(self) -> None:
        """Gracefully stop the bot (does NOT close open positions)."""
        self._running = False
        self.enabled = False
        for task in (self._monitor_task, self._auto_task):
            if task:
                task.cancel()
        if self._client:
            await self._client.close_connection()
            self._client = None
        logger.info("AutoBot stopped")

    # ── exchange metadata ──────────────────────────────────────────────────────

    async def _load_exchange_info(self) -> None:
        try:
            info = await self._client.futures_exchange_info()
            filters = {}
            for s in info.get("symbols", []):
                if s.get("quoteAsset") != "USDT" or s.get("status") != "TRADING":
                    continue
                if s.get("contractType") not in (None, "PERPETUAL"):
                    continue
                f = {"step": 0.001, "min_qty": 0.0, "min_notional": 5.0}
                for flt in s.get("filters", []):
                    t = flt.get("filterType")
                    if t == "MARKET_LOT_SIZE" or (t == "LOT_SIZE" and "step" not in f.get("_set", "")):
                        f["step"] = float(flt.get("stepSize", f["step"]))
                        f["min_qty"] = float(flt.get("minQty", f["min_qty"]))
                        if t == "MARKET_LOT_SIZE":
                            f["_set"] = "step"
                    elif t == "MIN_NOTIONAL":
                        f["min_notional"] = float(flt.get("notional", flt.get("minNotional", 5.0)))
                f.pop("_set", None)
                filters[s["symbol"]] = f
            self._symbol_filters = filters
            logger.info(f"AutoBot loaded {len(filters)} Binance USDT-M perpetual symbols")
        except Exception as e:
            logger.warning(f"Failed to load exchange info: {e}")

    async def _detect_position_mode(self) -> None:
        try:
            res = await self._client.futures_get_position_mode()
            self._hedge_mode = bool(res.get("dualSidePosition"))
            logger.info(f"AutoBot position mode: {'HEDGE' if self._hedge_mode else 'ONE-WAY'}")
        except Exception as e:
            logger.warning(f"Failed to detect position mode: {e}")

    async def _is_bot_position(self, symbol: str) -> bool:
        """Check whether the latest filled order on symbol was created by the bot."""
        try:
            orders = await self._client.futures_get_all_orders(symbol=symbol, limit=10)
            filled = [o for o in orders if o.get("status") == "FILLED"]
            if not filled:
                return False
            last = max(filled, key=lambda o: o.get("updateTime", 0))
            return str(last.get("clientOrderId", "")).startswith(CLIENT_ID_PREFIX)
        except Exception:
            return False

    async def _sync_positions(self, initial: bool = False) -> None:
        """
        Reconcile in-memory state with real Binance positions.
          • Adopt bot-created positions after a restart (HF Space restarts wipe memory)
          • Drop tracked positions that were closed outside the bot
        """
        if not self._client:
            return
        try:
            info = await self._client.futures_position_information()
        except Exception as e:
            logger.warning(f"Position sync failed: {e}")
            return

        live: dict[str, dict] = {}
        for p in info:
            amt = float(p.get("positionAmt", 0) or 0)
            if amt != 0:
                live[p["symbol"]] = p

        # Removed externally
        for sym in list(self._positions.keys()):
            if sym not in live:
                logger.info(f"{sym} closed outside AutoBot — removing from tracking")
                del self._positions[sym]
                self._cooldowns[sym] = datetime.now(timezone.utc)
                self._log_trade({
                    "event": "EXIT", "symbol": sym, "reason": "closed_externally",
                    "time": datetime.now(timezone.utc).isoformat(),
                })

        # Adopt untracked bot positions
        external = []
        for sym, p in live.items():
            if sym in self._positions:
                continue
            if await self._is_bot_position(sym):
                amt = float(p["positionAmt"])
                side = "LONG" if amt > 0 else "SHORT"
                st = PositionState(sym, side, float(p.get("entryPrice", 0)), abs(amt),
                                   "synced", source="synced")
                self._positions[sym] = st
                logger.info(f"Adopted bot position {sym} {side} qty={abs(amt)}")
            else:
                external.append(sym)
        self._external_positions = external

    # ── entry ──────────────────────────────────────────────────────────────────

    async def open_position(
        self,
        symbol: str,
        direction: str,       # "BUY" | "SELL"
        margin_usd: Optional[float] = None,
        setup_sl: Optional[float] = None,
        source: str = "manual",
        setup_info: Optional[dict] = None,
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

        async with self._entry_lock:
            # Already tracking this symbol?
            if symbol in self._positions:
                return {"error": f"Already in position for {symbol}"}
            if symbol in self._external_positions:
                return {"error": f"{symbol} has a manual (non-bot) position open"}
            if len(self._positions) >= self.max_positions and source == "auto":
                return {"error": f"Max positions reached ({self.max_positions})"}

            margin = margin_usd or self.margin_usd
            side   = "BUY" if direction.upper() == "BUY" else "SELL"
            pos_side = "LONG" if side == "BUY" else "SHORT"

            try:
                if not BINANCE_AVAILABLE:
                    return {"error": "python-binance not properly installed"}
                if self._symbol_filters and symbol not in self._symbol_filters:
                    return {"error": f"{symbol} not tradable on Binance USDT-M Futures"}

                # 1. Set leverage
                await self._client.futures_change_leverage(
                    symbol=symbol, leverage=self.leverage
                )

                # 2. Get current mark price to calc qty
                ticker = await self._client.futures_mark_price(symbol=symbol)
                mark   = float(ticker["markPrice"])

                # qty = notional / mark  (leverage already handled by margin)
                notional = margin * self.leverage
                flt = self._symbol_filters.get(symbol, {"step": 0.001, "min_qty": 0.0, "min_notional": 5.0})
                qty = _round_step(notional / mark, flt["step"])
                if qty <= 0 or qty < flt["min_qty"]:
                    return {"error": f"Qty {qty} below min qty {flt['min_qty']} for {symbol}"}
                if qty * mark < flt["min_notional"]:
                    return {"error": f"Notional ${qty * mark:.2f} below min ${flt['min_notional']}"}

                # 3. Place MARKET order
                params = dict(
                    symbol   = symbol,
                    side     = side,
                    type     = "MARKET",
                    quantity = qty,
                    newOrderRespType = "RESULT",
                    newClientOrderId = f"{CLIENT_ID_PREFIX}{int(datetime.now().timestamp() * 1000)}",
                )
                if self._hedge_mode:
                    params["positionSide"] = pos_side
                order = await self._client.futures_create_order(**params)

                entry_price = float(order.get("avgPrice") or 0) or mark
                order_id    = str(order["orderId"])

                state = PositionState(symbol, pos_side, entry_price, qty, order_id,
                                      setup_sl=setup_sl, source=source, setup_info=setup_info)
                self._positions[symbol] = state

                tag = "🤖 AUTO" if source == "auto" else "👤 MANUAL"
                extra = ""
                if setup_info:
                    extra = (
                        f"\n🧠 Setup: {setup_info.get('timeframe', '')} · "
                        f"Score {setup_info.get('score', '?')}/30 · RR {setup_info.get('rr', '?')}"
                    )
                if setup_sl:
                    extra += f"\n🧱 Structure SL: <code>{setup_sl}</code>"
                msg = (
                    f"{tag} <b>AutoBot ENTRY</b>\n"
                    f"📌 {symbol} {pos_side}\n"
                    f"💰 Entry: <code>{entry_price:.4f}</code>\n"
                    f"📦 Qty: <code>{qty}</code>  Lev: <code>{self.leverage}x</code>\n"
                    f"🎯 TP: +${self.tp_usd}  🛑 SL: -${self.sl_usd}{extra}"
                )
                await self._notify(msg)
                logger.info(f"Opened {pos_side} {symbol} @ {entry_price} qty={qty} source={source}")

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
                    "source": source,
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

        close_side = "SELL" if state.side == "LONG" else "BUY"

        try:
            params = dict(
                symbol     = symbol,
                side       = close_side,
                type       = "MARKET",
                quantity   = state.qty,
                newOrderRespType = "RESULT",
                newClientOrderId = f"{CLIENT_ID_PREFIX}x{int(datetime.now().timestamp() * 1000)}",
            )
            if self._hedge_mode:
                params["positionSide"] = state.side
            else:
                params["reduceOnly"] = True
            order = await self._client.futures_create_order(**params)
            close_price = float(order.get("avgPrice") or 0) or state.last_mark
            pnl         = state.calc_pnl(close_price) if close_price else None

            self._positions.pop(symbol, None)
            self._cooldowns[symbol] = datetime.now(timezone.utc)
            self._add_daily_pnl(pnl or 0.0)

            emoji = "✅" if (pnl or 0) >= 0 else "❌"
            pnl_str = f"${pnl:+.2f}" if pnl is not None else "N/A"
            msg = (
                f"{emoji} <b>AutoBot EXIT</b> [{reason.upper()}]\n"
                f"📌 {symbol} closed\n"
                f"💸 PnL: <code>{pnl_str}</code>\n"
                f"🔒 Close @ <code>{close_price:.4f}</code>\n"
                f"📅 Today: <code>${self._daily_pnl:+.2f}</code>"
            )
            await self._notify(msg)
            logger.info(f"Closed {symbol} reason={reason} pnl={pnl_str}")

            result = {
                "status": "closed",
                "symbol": symbol,
                "side": state.side,
                "reason": reason,
                "close_price": close_price,
                "pnl_usd": pnl,
                "qty": state.qty,
            }
            self._log_trade({**result, "event": "EXIT", "time": datetime.now(timezone.utc).isoformat()})
            return result

        except BinanceAPIException as e:
            logger.error(f"Binance API error on close {symbol}: {e}")
            # -2022 ReduceOnly rejected → position no longer exists on exchange
            if getattr(e, "code", None) == -2022:
                self._positions.pop(symbol, None)
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
          • Structure SL : price breaks setup stop-loss level
        """
        logger.info("Monitor loop started")
        loops = 0
        while self._running:
            await asyncio.sleep(MONITOR_INTERVAL)
            loops += 1
            if loops % SYNC_EVERY_N_LOOPS == 0:
                await self._sync_positions()
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
                state.last_pnl = pnl
                state.last_mark = mark

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

                elif state.setup_sl and (
                    (state.side == "LONG" and mark <= state.setup_sl)
                    or (state.side == "SHORT" and mark >= state.setup_sl)
                ):
                    # Setup invalidated by structure break
                    reason = "structure_sl"

                if reason:
                    logger.info(
                        f"Closing {symbol}: reason={reason} "
                        f"pnl={pnl:+.2f} peak={state.peak_pnl:+.2f}"
                    )
                    await self.close_position(symbol, reason=reason)

    # ── auto-entry loop ────────────────────────────────────────────────────────

    async def _auto_entry_loop(self) -> None:
        logger.info("Auto-entry loop started")
        await asyncio.sleep(10)
        while self._running:
            try:
                await self._auto_entry_cycle()
            except Exception as e:
                logger.warning(f"Auto-entry cycle error: {e}")
                self._auto_state["paused_reason"] = f"error: {e}"
            await asyncio.sleep(AUTO_ENTRY_INTERVAL)

    def _pause(self, reason: Optional[str]) -> None:
        self._auto_state["paused_reason"] = reason

    async def _auto_entry_cycle(self) -> None:
        self._auto_state["last_scan_at"] = datetime.now(timezone.utc).isoformat()
        self._roll_daily()

        if not self.enabled:
            return self._pause("bot disabled")
        if not self.auto_entry:
            return self._pause("auto-entry OFF")
        if self._daily_pnl <= -abs(self.max_daily_loss):
            return self._pause(f"daily loss limit hit (${self._daily_pnl:.2f})")

        from app.services.live_alert_scanner import get_cache_snapshot
        setups = get_cache_snapshot()
        self._auto_state["setups_in_cache"] = len(setups)

        # 1. Quality filter
        quality = [
            s for s in setups
            if s.direction in ("BUY", "SELL")
            and (s.confluence_score or 0) >= self.min_score
            and (s.risk_reward or 0) >= self.min_rr
            and s.age_hours() <= self.max_setup_age_h
            and s.timeframe in self.timeframes
        ]

        # 2. Group per symbol — skip conflicting BUY & SELL signals
        by_symbol: dict[str, list] = {}
        for s in quality:
            by_symbol.setdefault(s.symbol, []).append(s)
        candidates = []
        for sym, group in by_symbol.items():
            if len({g.direction for g in group}) > 1:
                continue
            candidates.extend(sorted(group, key=lambda g: g.confluence_score, reverse=True))
        self._auto_state["candidates"] = len(candidates)

        if not candidates:
            self._auto_state["watchlist"] = []
            return self._pause("no qualified setups yet")

        # 3. Live Binance prices
        try:
            tickers = await self._client.futures_symbol_ticker()
            price_map = {t["symbol"]: float(t["price"]) for t in tickers}
        except Exception as e:
            return self._pause(f"price fetch failed: {e}")

        now = datetime.now(timezone.utc)
        watchlist = []
        for s in candidates:
            sym = s.symbol
            key = f"{sym}|{s.direction}|{s.timeframe}|{s.entry_low:.8g}|{s.entry_high:.8g}"
            price = price_map.get(sym)
            zone_low = min(s.entry_low, s.entry_high) * (1 - ENTRY_TOLERANCE)
            zone_high = max(s.entry_low, s.entry_high) * (1 + ENTRY_TOLERANCE)
            item = {
                "symbol": sym, "direction": s.direction, "timeframe": s.timeframe,
                "score": round(s.confluence_score, 1), "rr": round(s.risk_reward, 2),
                "entry_low": s.entry_low, "entry_high": s.entry_high,
                "stop_loss": s.stop_loss, "price": price, "status": "waiting",
            }

            if self._symbol_filters and sym not in self._symbol_filters:
                item["status"] = "not on Binance"
            elif price is None:
                item["status"] = "no price"
            elif key in self._traded_setups:
                item["status"] = "already traded"
            elif sym in self._positions:
                item["status"] = "in position"
            elif sym in self._external_positions:
                item["status"] = "manual position"
            elif sym in self._cooldowns and (now - self._cooldowns[sym]).total_seconds() < self.cooldown_min * 60:
                left = self.cooldown_min - (now - self._cooldowns[sym]).total_seconds() / 60
                item["status"] = f"cooldown {left:.0f}m"
            elif (s.direction == "BUY" and price <= s.stop_loss) or (s.direction == "SELL" and price >= s.stop_loss):
                item["status"] = "invalidated (SL broken)"
                self._traded_setups.add(key)
            elif not (zone_low <= price <= zone_high):
                dist = (price - zone_high) / price if price > zone_high else (zone_low - price) / price
                item["status"] = f"waiting ({dist * 100:.2f}% away)"
            elif len(self._positions) >= self.max_positions:
                item["status"] = "IN ZONE — max positions"
            else:
                # 🎯 IN ZONE → AUTO ENTRY
                res = await self.open_position(
                    sym, s.direction,
                    setup_sl=s.stop_loss,
                    source="auto",
                    setup_info={
                        "timeframe": s.timeframe,
                        "score": round(s.confluence_score, 1),
                        "rr": round(s.risk_reward, 2),
                        "entry_low": s.entry_low,
                        "entry_high": s.entry_high,
                    },
                )
                self._traded_setups.add(key)
                if "error" in res:
                    item["status"] = f"entry failed: {res['error'][:80]}"
                    self._cooldowns[sym] = now  # avoid hammering a failing symbol
                else:
                    item["status"] = "ENTERED"
                    self._auto_state["total_auto_entries"] += 1
                    self._auto_state["last_action"] = {
                        "time": now.isoformat(), "symbol": sym,
                        "direction": s.direction, "price": res.get("entry_price"),
                    }
            watchlist.append(item)

        # keep memory bounded
        if len(self._traded_setups) > 2000:
            self._traded_setups = set(list(self._traded_setups)[-1000:])

        watchlist.sort(key=lambda x: (x["status"] != "ENTERED", not str(x["status"]).startswith("IN ZONE"), -x["score"]))
        self._auto_state["watchlist"] = watchlist[:30]
        self._pause(None)

    # ── helpers ────────────────────────────────────────────────────────────────

    def _roll_daily(self) -> None:
        today = datetime.now(timezone.utc).date()
        if today != self._daily_date:
            self._daily_date = today
            self._daily_pnl = 0.0

    def _add_daily_pnl(self, pnl: float) -> None:
        self._roll_daily()
        self._daily_pnl += pnl

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
                "pnl":         round(s.last_pnl, 3),
                "mark":        s.last_mark,
                "setup_sl":    s.setup_sl,
                "source":      s.source,
                "setup":       s.setup_info,
                "opened_at":   s.opened_at.isoformat(),
            })
        self._roll_daily()
        return {
            "enabled":       self.enabled,
            "running":       self._running,
            "open_positions": positions,
            "tp_usd":        self.tp_usd,
            "sl_usd":        self.sl_usd,
            "leverage":      self.leverage,
            "margin_usd":    self.margin_usd,
            "auto_entry":    self.auto_entry,
            "min_score":     self.min_score,
            "min_rr":        self.min_rr,
            "max_positions": self.max_positions,
            "cooldown_min":  self.cooldown_min,
            "max_setup_age_h": self.max_setup_age_h,
            "max_daily_loss": self.max_daily_loss,
            "timeframes":    self.timeframes,
            "daily_pnl":     round(self._daily_pnl, 2),
            "hedge_mode":    self._hedge_mode,
            "external_positions": self._external_positions,
            "auto_state":    self._auto_state,
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
        auto_entry: Optional[bool] = None,
        min_score: Optional[float] = None,
        min_rr: Optional[float] = None,
        max_positions: Optional[int] = None,
        cooldown_min: Optional[int] = None,
        max_setup_age_h: Optional[float] = None,
        max_daily_loss: Optional[float] = None,
        timeframes: Optional[list] = None,
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
        if auto_entry is not None:
            self.auto_entry = auto_entry
        if min_score is not None:
            self.min_score = min_score
        if min_rr is not None:
            self.min_rr = min_rr
        if max_positions is not None:
            self.max_positions = max(1, max_positions)
        if cooldown_min is not None:
            self.cooldown_min = max(0, cooldown_min)
        if max_setup_age_h is not None:
            self.max_setup_age_h = max_setup_age_h
        if max_daily_loss is not None:
            self.max_daily_loss = max_daily_loss
        if timeframes:
            self.timeframes = timeframes
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
    auto_entry: bool = True,
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
        auto_entry=auto_entry,
    )
    return _bot_instance
