"""Pydantic schemas for market data."""

from pydantic import BaseModel, PlainSerializer
from typing import Optional, List, Annotated
from datetime import datetime, timezone


def _serialize_utc(value: Optional[datetime]) -> Optional[str]:
    """
    Serialize a datetime as an explicit UTC ISO-8601 string ending in 'Z'.

    Engine timestamps are naive UTC (from exchange epoch-ms). Without a zone marker
    browsers parse "2025-01-01T10:00:00" as *local* time, shifting every marker by the
    user's UTC offset (e.g. -7h in WIB). Only applied in JSON mode, so python-mode
    model_dump() consumers still receive real datetime objects.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


UTCDatetime = Annotated[
    datetime, PlainSerializer(_serialize_utc, return_type=str, when_used="json")
]


class CandleSchema(BaseModel):
    symbol: str
    timeframe: str
    open_time: UTCDatetime
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
    time: Optional[UTCDatetime] = None


class StructureLabel(BaseModel):
    index: int
    label: str  # HH, HL, LH, LL, BOS, CHOCH, MSS
    price: float
    time: Optional[UTCDatetime] = None


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
    time: Optional[UTCDatetime] = None
    tested: bool = False
    mitigated: bool = False
    status: str = "FRESH"          # "FRESH" | "TESTED" | "MITIGATED" | "INVALIDATED"
    bos_confirmed: bool = False    # True when displacement broke a recent swing


class FairValueGap(BaseModel):
    type: str  # "BULLISH" or "BEARISH"
    high: float
    low: float
    index: int
    time: Optional[UTCDatetime] = None
    filled: bool = False
    midpoint: Optional[float] = None   # 50% Consequent Encroachment (CE)
    fill_pct: float = 0.0              # 0..100 percentage of gap penetrated
    ce_touched: bool = False           # True once price reaches the 50% CE line
    status: str = "FRESH"              # "FRESH" | "PARTIAL" | "CE_TOUCHED" | "FILLED"


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
