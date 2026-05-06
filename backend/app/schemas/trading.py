"""Pydantic schemas for auto-trading and portfolio tracking."""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ─── Auto-Trade Configuration ───
class AutoTradeConfig(BaseModel):
    enabled: bool = False
    risk_per_trade: float = 1.0       # % of account balance
    max_positions: int = 3
    max_daily_loss: float = 3.0       # % of account balance
    default_leverage: int = 5
    use_market_order: bool = False     # False = limit order
    dry_run: bool = True              # True = log only, no real orders


# ─── Order Request / Result ───
class OrderRequest(BaseModel):
    symbol: str
    side: str                          # BUY / SELL
    order_type: str = "LIMIT"          # LIMIT / MARKET
    quantity: Optional[float] = None   # If None, auto-calculated from risk
    price: Optional[float] = None      # Required for LIMIT
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    leverage: int = 5
    setup_id: Optional[int] = None     # Link to trade setup


class OrderResult(BaseModel):
    success: bool
    order_id: Optional[str] = None
    symbol: str
    side: str
    quantity: float = 0
    price: float = 0
    status: str = ""
    message: str = ""
    dry_run: bool = False
    sl_order_id: Optional[str] = None
    tp_order_id: Optional[str] = None


# ─── Position Info ───
class PositionInfo(BaseModel):
    symbol: str
    side: str                          # LONG / SHORT
    size: float                        # quantity
    entry_price: float
    mark_price: float = 0
    liquidation_price: float = 0
    unrealized_pnl: float = 0
    unrealized_pnl_pct: float = 0
    leverage: int = 1
    margin: float = 0
    notional: float = 0


# ─── Trade History ───
class TradeHistoryItem(BaseModel):
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    realized_pnl: float
    realized_pnl_pct: float = 0
    commission: float = 0
    duration_minutes: int = 0
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None


# ─── Portfolio Stats ───
class PortfolioStats(BaseModel):
    total_balance: float = 0
    available_balance: float = 0
    total_unrealized_pnl: float = 0
    total_realized_pnl: float = 0
    total_margin_used: float = 0
    open_positions_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0
    total_trades: int = 0
    max_drawdown_pct: float = 0
    today_pnl: float = 0
