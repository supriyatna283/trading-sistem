"""Pydantic schemas for trade setups."""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class TradeSetupSchema(BaseModel):
    id: Optional[int] = None
    symbol: str
    direction: str  # BUY / SELL
    entry_low: float
    entry_high: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    risk_reward: float
    setup_type: str
    confluence_score: int = 0
    status: str = "ACTIVE"
    timeframe: str
    explanation: Optional[str] = None
    created_at: Optional[datetime] = None


class SetupStatusUpdate(BaseModel):
    status: str  # ACTIVE, TRIGGERED, INVALIDATED, CLOSED


class ConfluenceResult(BaseModel):
    symbol: str
    total_score: int
    max_score: int
    details: dict
    recommendation: str  # "STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"
    setups: List[TradeSetupSchema] = []
