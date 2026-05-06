"""Pydantic schemas for risk management."""

from pydantic import BaseModel
from typing import Optional


class RiskSettingsSchema(BaseModel):
    account_balance: float = 10000.0
    risk_per_trade: float = 1.0
    max_daily_risk: float = 3.0
    max_concurrent_trades: int = 3


class PositionSizeRequest(BaseModel):
    account_balance: float
    risk_per_trade: float  # percentage
    entry_price: float
    stop_loss: float
    direction: str  # BUY or SELL


class PositionSizeResult(BaseModel):
    position_size: float
    risk_amount: float
    stop_distance: float
    stop_distance_pct: float
    risk_reward: Optional[float] = None
    take_profit: Optional[float] = None
