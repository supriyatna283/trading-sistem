"""Pydantic schemas for trading journal."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class JournalEntryCreate(BaseModel):
    setup_id: Optional[int] = None
    symbol: str
    direction: str
    entry_price: float
    exit_price: Optional[float] = None
    stop_loss: float
    take_profit: float
    position_size: float
    pnl: Optional[float] = None
    r_multiple: Optional[float] = None
    result: Optional[str] = None
    notes: Optional[str] = None
    screenshot_url: Optional[str] = None
    entered_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None


class JournalAnalytics(BaseModel):
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_r_multiple: float = 0.0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    expectancy: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
