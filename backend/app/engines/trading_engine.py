"""
Trading Engine — Binance Futures Order Execution
===================================================
Handles order placement, SL/TP, position sizing, and safety checks.
Supports dry-run mode for testing without real orders.
"""

import logging
from typing import Optional, Dict
from binance.client import Client
from binance.exceptions import BinanceAPIException
from app.config import get_settings
from app.schemas.trading import (
    AutoTradeConfig, OrderRequest, OrderResult, PositionInfo,
)
from app.engines.risk_management import RiskManagementEngine
from app.schemas.risk import PositionSizeRequest

logger = logging.getLogger(__name__)

# In-memory config (could be persisted to DB later)
_auto_trade_config = AutoTradeConfig()
_daily_loss_tracker: Dict[str, float] = {}  # date -> loss amount


class TradingEngine:
    """Binance Futures trading engine with safety guards."""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.BINANCE_API_KEY
        self.api_secret = settings.BINANCE_API_SECRET
        self.risk_engine = RiskManagementEngine()
        self._client: Optional[Client] = None
        self._exchange_info: Optional[Dict] = None

    @property
    def client(self) -> Optional[Client]:
        """Lazy-init Binance client."""
        if self._client is None and self.api_key and self.api_secret:
            try:
                self._client = Client(self.api_key, self.api_secret)
                logger.info("✅ Binance client initialized")
            except Exception as e:
                logger.error(f"❌ Binance client init failed: {e}")
        return self._client

    @property
    def config(self) -> AutoTradeConfig:
        return _auto_trade_config

    def update_config(self, cfg: AutoTradeConfig):
        global _auto_trade_config
        _auto_trade_config = cfg
        logger.info(f"⚙️ Auto-trade config updated: {cfg.dict()}")

    def is_connected(self) -> bool:
        """Check if Binance API is reachable."""
        try:
            if not self.client:
                return False
            self.client.futures_ping()
            return True
        except Exception:
            return False

    # ─── Account Info ───
    def get_account_balance(self) -> Dict:
        """Get futures account balance."""
        if not self.client:
            return {"total_balance": 0, "available_balance": 0, "error": "No API keys"}
        try:
            account = self.client.futures_account()
            return {
                "total_balance": float(account.get("totalWalletBalance", 0)),
                "available_balance": float(account.get("availableBalance", 0)),
                "total_unrealized_pnl": float(account.get("totalUnrealizedProfit", 0)),
                "total_margin_used": float(account.get("totalInitialMargin", 0)),
            }
        except BinanceAPIException as e:
            logger.error(f"Balance fetch failed: {e}")
            return {"total_balance": 0, "available_balance": 0, "error": str(e)}

    def get_open_positions(self) -> list[PositionInfo]:
        """Get all open futures positions."""
        if not self.client:
            return []
        try:
            positions = self.client.futures_position_information()
            result = []
            for p in positions:
                size = float(p.get("positionAmt", 0))
                if size == 0:
                    continue
                entry = float(p.get("entryPrice", 0))
                mark = float(p.get("markPrice", 0))
                notional = abs(size) * mark
                pnl = float(p.get("unRealizedProfit", 0))
                pnl_pct = (pnl / (abs(size) * entry) * 100) if entry > 0 and size != 0 else 0

                result.append(PositionInfo(
                    symbol=p["symbol"],
                    side="LONG" if size > 0 else "SHORT",
                    size=abs(size),
                    entry_price=entry,
                    mark_price=mark,
                    liquidation_price=float(p.get("liquidationPrice", 0)),
                    unrealized_pnl=round(pnl, 4),
                    unrealized_pnl_pct=round(pnl_pct, 2),
                    leverage=int(p.get("leverage", 1)),
                    margin=float(p.get("initialMargin", 0)),
                    notional=round(notional, 2),
                ))
            return result
        except BinanceAPIException as e:
            logger.error(f"Position fetch failed: {e}")
            return []

    # ─── Order Execution ───
    def execute_order(self, req: OrderRequest) -> OrderResult:
        """Execute a futures order with SL/TP."""
        cfg = self.config

        # Safety: check if auto-trading is enabled
        if not cfg.enabled:
            return OrderResult(
                success=False, symbol=req.symbol, side=req.side,
                message="Auto-trading is disabled. Enable it in settings.",
            )

        # Safety: check max positions
        open_positions = self.get_open_positions()
        if len(open_positions) >= cfg.max_positions:
            return OrderResult(
                success=False, symbol=req.symbol, side=req.side,
                message=f"Max positions ({cfg.max_positions}) reached.",
            )

        # Safety: check daily loss
        from datetime import date
        today = str(date.today())
        daily_loss = _daily_loss_tracker.get(today, 0)
        balance = self.get_account_balance()
        max_daily_loss_amount = balance.get("total_balance", 0) * (cfg.max_daily_loss / 100)
        if daily_loss >= max_daily_loss_amount:
            return OrderResult(
                success=False, symbol=req.symbol, side=req.side,
                message=f"Daily loss limit reached ({cfg.max_daily_loss}%).",
            )

        # Safety: duplicate check
        for pos in open_positions:
            if pos.symbol == req.symbol:
                return OrderResult(
                    success=False, symbol=req.symbol, side=req.side,
                    message=f"Already have an open position on {req.symbol}.",
                )

        # Calculate position size if not provided
        quantity = req.quantity
        if quantity is None or quantity <= 0:
            if req.stop_loss and req.price:
                pos_size = self.risk_engine.calculate_position_size(
                    PositionSizeRequest(
                        account_balance=balance.get("total_balance", 0),
                        risk_per_trade=cfg.risk_per_trade,
                        entry_price=req.price,
                        stop_loss=req.stop_loss,
                        direction=req.side,
                    )
                )
                quantity = pos_size.position_size
            else:
                return OrderResult(
                    success=False, symbol=req.symbol, side=req.side,
                    message="Cannot calculate position size without price and stop_loss.",
                )

        # Round quantity to appropriate precision
        quantity = self._round_quantity(req.symbol, quantity)

        if quantity <= 0:
            return OrderResult(
                success=False, symbol=req.symbol, side=req.side,
                message="Calculated position size is zero (check USDT balance or Risk %).",
            )

        # ── Dry-run mode ──
        if cfg.dry_run or not self.client:
            logger.info(
                f"🧪 DRY-RUN: {req.side} {quantity} {req.symbol} @ {req.price} "
                f"| SL={req.stop_loss} TP={req.take_profit}"
            )
            return OrderResult(
                success=True, order_id="DRY_RUN",
                symbol=req.symbol, side=req.side,
                quantity=quantity, price=req.price or 0,
                status="DRY_RUN", dry_run=True,
                message=f"Dry-run: {req.side} {quantity} {req.symbol} @ {req.price}",
            )

        # ── Real execution ──
        try:
            # Set leverage
            try:
                self.client.futures_change_leverage(
                    symbol=req.symbol, leverage=req.leverage or cfg.default_leverage
                )
            except Exception:
                pass  # Leverage might already be set

            # Place main order
            order_params = {
                "symbol": req.symbol,
                "side": req.side,
                "quantity": quantity,
            }

            if req.order_type == "MARKET" or cfg.use_market_order:
                order_params["type"] = "MARKET"
            else:
                order_params["type"] = "LIMIT"
                order_params["price"] = str(req.price)
                order_params["timeInForce"] = "GTC"

            order = self.client.futures_create_order(**order_params)
            order_id = str(order.get("orderId", ""))
            fill_price = float(order.get("avgPrice", 0)) or (req.price or 0)

            logger.info(f"✅ Order placed: {req.side} {quantity} {req.symbol} | ID={order_id}")

            # Place SL order
            sl_order_id = None
            if req.stop_loss:
                try:
                    sl_side = "SELL" if req.side == "BUY" else "BUY"
                    sl_order = self.client.futures_create_order(
                        symbol=req.symbol,
                        side=sl_side,
                        type="STOP_MARKET",
                        stopPrice=str(req.stop_loss),
                        closePosition=True,
                    )
                    sl_order_id = str(sl_order.get("orderId", ""))
                    logger.info(f"   🛡️ SL placed @ {req.stop_loss} | ID={sl_order_id}")
                except Exception as e:
                    logger.warning(f"   ⚠️ SL placement failed: {e}")

            # Place TP order
            tp_order_id = None
            if req.take_profit:
                try:
                    tp_side = "SELL" if req.side == "BUY" else "BUY"
                    tp_order = self.client.futures_create_order(
                        symbol=req.symbol,
                        side=tp_side,
                        type="TAKE_PROFIT_MARKET",
                        stopPrice=str(req.take_profit),
                        closePosition=True,
                    )
                    tp_order_id = str(tp_order.get("orderId", ""))
                    logger.info(f"   🎯 TP placed @ {req.take_profit} | ID={tp_order_id}")
                except Exception as e:
                    logger.warning(f"   ⚠️ TP placement failed: {e}")

            return OrderResult(
                success=True, order_id=order_id,
                symbol=req.symbol, side=req.side,
                quantity=quantity, price=fill_price,
                status=order.get("status", "NEW"),
                message=f"Order executed: {req.side} {quantity} {req.symbol}",
                sl_order_id=sl_order_id,
                tp_order_id=tp_order_id,
            )

        except BinanceAPIException as e:
            logger.error(f"❌ Order failed: {e}")
            return OrderResult(
                success=False, symbol=req.symbol, side=req.side,
                message=f"Binance API error: {e.message}",
            )
        except Exception as e:
            logger.error(f"❌ Order failed: {e}")
            return OrderResult(
                success=False, symbol=req.symbol, side=req.side,
                message=f"Error: {str(e)}",
            )

    def close_position(self, symbol: str) -> OrderResult:
        """Close an open position with a market order."""
        positions = self.get_open_positions()
        target = next((p for p in positions if p.symbol == symbol), None)

        if not target:
            return OrderResult(
                success=False, symbol=symbol, side="",
                message=f"No open position found for {symbol}.",
            )

        close_side = "SELL" if target.side == "LONG" else "BUY"

        if self.config.dry_run or not self.client:
            logger.info(f"🧪 DRY-RUN: Close {target.side} {target.size} {symbol}")
            return OrderResult(
                success=True, order_id="DRY_RUN_CLOSE",
                symbol=symbol, side=close_side,
                quantity=target.size, status="DRY_RUN",
                dry_run=True,
                message=f"Dry-run: Closed {symbol}",
            )

        try:
            # Cancel all open orders for this symbol first
            try:
                self.client.futures_cancel_all_open_orders(symbol=symbol)
            except Exception:
                pass

            order = self.client.futures_create_order(
                symbol=symbol,
                side=close_side,
                type="MARKET",
                quantity=target.size,
            )
            logger.info(f"✅ Position closed: {symbol}")
            return OrderResult(
                success=True, order_id=str(order.get("orderId", "")),
                symbol=symbol, side=close_side,
                quantity=target.size,
                price=float(order.get("avgPrice", 0)),
                status="CLOSED",
                message=f"Closed {target.side} {target.size} {symbol}",
            )
        except BinanceAPIException as e:
            return OrderResult(
                success=False, symbol=symbol, side=close_side,
                message=f"Close failed: {e.message}",
            )

    def _get_exchange_info(self) -> Optional[Dict]:
        """Cache exchange info to avoid slow repeating API calls."""
        if not self.client:
            return None
        if not self._exchange_info:
            try:
                self._exchange_info = self.client.futures_exchange_info()
            except Exception as e:
                logger.error(f"Failed to fetch exchange info: {e}")
        return self._exchange_info

    def _round_quantity(self, symbol: str, quantity: float) -> float:
        """Round quantity to valid step size for the symbol."""
        try:
            info = self._get_exchange_info()
            if info:
                for s in info.get("symbols", []):
                    if s["symbol"] == symbol:
                        for f in s.get("filters", []):
                            if f["filterType"] == "LOT_SIZE":
                                step = float(f["stepSize"])
                                precision = len(f["stepSize"].rstrip("0").split(".")[-1]) if "." in f["stepSize"] else 0
                                return round(quantity - (quantity % step), precision)
        except Exception:
            pass
        # Fallback: round to 3 decimals
        return round(quantity, 3)


# Singleton
trading_engine = TradingEngine()
