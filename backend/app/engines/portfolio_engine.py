"""
Portfolio Engine — Position Tracking & PnL
=============================================
Syncs with Binance Futures to provide real-time portfolio data,
trade history, and performance statistics.
"""

import logging
from typing import List, Dict
from datetime import datetime, timedelta
from binance.client import Client
from binance.exceptions import BinanceAPIException
from app.config import get_settings
from app.schemas.trading import PositionInfo, TradeHistoryItem, PortfolioStats

logger = logging.getLogger(__name__)


class PortfolioEngine:
    """Portfolio tracking via Binance Futures API."""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.BINANCE_API_KEY
        self.api_secret = settings.BINANCE_API_SECRET
        self._client = None

    @property
    def client(self):
        if self._client is None and self.api_key and self.api_secret:
            try:
                self._client = Client(self.api_key, self.api_secret)
            except Exception as e:
                logger.error(f"Binance client init failed: {e}")
        return self._client

    # ─── Account Balance ───
    def get_balance(self) -> Dict:
        """Get futures wallet balance."""
        if not self.client:
            return {
                "total_balance": 0, "available_balance": 0,
                "total_unrealized_pnl": 0, "total_margin_used": 0,
                "connected": False,
            }
        try:
            account = self.client.futures_account()
            return {
                "total_balance": round(float(account.get("totalWalletBalance", 0)), 2),
                "available_balance": round(float(account.get("availableBalance", 0)), 2),
                "total_unrealized_pnl": round(float(account.get("totalUnrealizedProfit", 0)), 2),
                "total_margin_used": round(float(account.get("totalInitialMargin", 0)), 2),
                "total_cross_wallet": round(float(account.get("totalCrossWalletBalance", 0)), 2),
                "connected": True,
            }
        except BinanceAPIException as e:
            logger.error(f"Balance fetch failed: {e}")
            return {
                "total_balance": 0, "available_balance": 0,
                "total_unrealized_pnl": 0, "total_margin_used": 0,
                "connected": False, "error": str(e),
            }

    # ─── Open Positions ───
    def get_positions(self) -> List[PositionInfo]:
        """Get all open futures positions with real-time PnL."""
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
                pnl = float(p.get("unRealizedProfit", 0))
                notional = abs(size) * mark
                pnl_pct = (pnl / (abs(size) * entry) * 100) if entry > 0 else 0

                result.append(PositionInfo(
                    symbol=p["symbol"],
                    side="LONG" if size > 0 else "SHORT",
                    size=abs(size),
                    entry_price=round(entry, 8),
                    mark_price=round(mark, 8),
                    liquidation_price=round(float(p.get("liquidationPrice", 0)), 8),
                    unrealized_pnl=round(pnl, 4),
                    unrealized_pnl_pct=round(pnl_pct, 2),
                    leverage=int(p.get("leverage", 1)),
                    margin=round(float(p.get("initialMargin", 0)), 4),
                    notional=round(notional, 2),
                ))
            return result
        except BinanceAPIException as e:
            logger.error(f"Position fetch failed: {e}")
            return []

    # ─── Real-time PnL ───
    def get_pnl(self) -> Dict:
        """Get aggregated PnL across all positions."""
        positions = self.get_positions()
        balance = self.get_balance()

        total_unrealized = sum(p.unrealized_pnl for p in positions)
        total_margin = sum(p.margin for p in positions)
        total_notional = sum(p.notional for p in positions)

        return {
            "positions": [p.dict() for p in positions],
            "total_unrealized_pnl": round(total_unrealized, 4),
            "total_margin_used": round(total_margin, 4),
            "total_notional": round(total_notional, 2),
            "wallet_balance": balance.get("total_balance", 0),
            "available_balance": balance.get("available_balance", 0),
            "equity": round(balance.get("total_balance", 0) + total_unrealized, 2),
            "positions_count": len(positions),
        }

    # ─── Trade History ───
    def get_trade_history(self, days: int = 30, limit: int = 50) -> List[TradeHistoryItem]:
        """Get closed trade history from Binance."""
        if not self.client:
            return []
        try:
            # Get all symbols with recent trades
            account = self.client.futures_account()
            positions = account.get("positions", [])

            # Collect trades from all traded symbols
            start_time = int((datetime.utcnow() - timedelta(days=days)).timestamp() * 1000)
            all_trades: List[TradeHistoryItem] = []

            traded_symbols = set()
            for p in positions:
                if float(p.get("initialMargin", 0)) > 0 or float(p.get("unrealizedProfit", 0)) != 0:
                    traded_symbols.add(p["symbol"])

            # Also check income history for realized PnL
            try:
                income = self.client.futures_income_history(
                    incomeType="REALIZED_PNL",
                    startTime=start_time,
                    limit=limit,
                )
                for item in income:
                    pnl = float(item.get("income", 0))
                    ts = int(item.get("time", 0))
                    all_trades.append(TradeHistoryItem(
                        symbol=item.get("symbol", ""),
                        side="LONG" if pnl > 0 else "SHORT",
                        entry_price=0,
                        exit_price=0,
                        quantity=0,
                        realized_pnl=round(pnl, 4),
                        realized_pnl_pct=0,
                        commission=0,
                        closed_at=datetime.utcfromtimestamp(ts / 1000) if ts > 0 else None,
                    ))
            except Exception as e:
                logger.warning(f"Income history fetch failed: {e}")

            # Sort by date descending
            all_trades.sort(key=lambda t: t.closed_at or datetime.min, reverse=True)
            return all_trades[:limit]

        except BinanceAPIException as e:
            logger.error(f"Trade history fetch failed: {e}")
            return []

    # ─── Portfolio Statistics ───
    def get_stats(self, days: int = 30) -> PortfolioStats:
        """Calculate portfolio performance statistics."""
        balance = self.get_balance()
        positions = self.get_positions()
        history = self.get_trade_history(days=days, limit=200)

        total_pnl = sum(t.realized_pnl for t in history)
        wins = [t for t in history if t.realized_pnl > 0]
        losses = [t for t in history if t.realized_pnl < 0]
        total_trades = len(history)

        win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0

        # Today's PnL
        today = datetime.utcnow().date()
        today_trades = [t for t in history if t.closed_at and t.closed_at.date() == today]
        today_pnl = sum(t.realized_pnl for t in today_trades)

        # Max drawdown (simplified — peak-to-trough from cumulative PnL)
        max_dd = 0
        cumulative = 0
        peak = 0
        for t in sorted(history, key=lambda x: x.closed_at or datetime.min):
            cumulative += t.realized_pnl
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd

        total_bal = balance.get("total_balance", 0)
        max_dd_pct = (max_dd / total_bal * 100) if total_bal > 0 else 0

        return PortfolioStats(
            total_balance=total_bal,
            available_balance=balance.get("available_balance", 0),
            total_unrealized_pnl=sum(p.unrealized_pnl for p in positions),
            total_realized_pnl=round(total_pnl, 4),
            total_margin_used=sum(p.margin for p in positions),
            open_positions_count=len(positions),
            win_count=len(wins),
            loss_count=len(losses),
            win_rate=round(win_rate, 1),
            total_trades=total_trades,
            max_drawdown_pct=round(max_dd_pct, 2),
            today_pnl=round(today_pnl, 4),
        )


# Singleton
portfolio_engine = PortfolioEngine()
