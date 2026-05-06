"""Pydantic schemas for market data."""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CandleSchema(BaseModel):
    symbol: str
    timeframe: str
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketDataRequest(BaseModel):
    symbol: str
    timeframe: str = "1h"
    limit: int = 200


class SwingPoint(BaseModel):
    index: int
    price: float
    type: str  # "HIGH" or "LOW"
    time: Optional[datetime] = None


class StructureLabel(BaseModel):
    index: int
    label: str  # HH, HL, LH, LL, BOS, CHOCH, MSS
    price: float
    time: Optional[datetime] = None


class MarketBias(BaseModel):
    symbol: str
    timeframe: str
    bias: str  # "BULLISH", "BEARISH", "SIDEWAYS"
    structure_labels: List[StructureLabel] = []
    swing_points: List[SwingPoint] = []


class OrderBlock(BaseModel):
    type: str  # "BULLISH" or "BEARISH"
    high: float
    low: float
    index: int
    time: Optional[datetime] = None
    tested: bool = False
    mitigated: bool = False


class FairValueGap(BaseModel):
    type: str  # "BULLISH" or "BEARISH"
    high: float
    low: float
    index: int
    time: Optional[datetime] = None
    filled: bool = False


class LiquidityLevel(BaseModel):
    price: float
    type: str  # "EQUAL_HIGH", "EQUAL_LOW", "STOP_CLUSTER"
    strength: int = 1
    swept: bool = False


class SmartMoneyAnalysis(BaseModel):
    symbol: str
    timeframe: str
    order_blocks: List[OrderBlock] = []
    fvgs: List[FairValueGap] = []
    liquidity_levels: List[LiquidityLevel] = []
    premium_discount_mid: Optional[float] = None
