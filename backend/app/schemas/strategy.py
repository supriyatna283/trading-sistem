"""Strategy Builder Pydantic Schemas"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class BlockParam(BaseModel):
    """A single configurable parameter for a strategy block."""
    key: str
    value: Any


class StrategyBlock(BaseModel):
    """One building block within a strategy."""
    id: str
    enabled: bool = True
    weight: int = Field(default=1, ge=1, le=5)
    params: Dict[str, Any] = {}


class StrategyCreate(BaseModel):
    """Payload for creating/saving a strategy."""
    name: str
    description: str = ""
    min_score: int = Field(default=5, ge=1, le=20)
    blocks: List[StrategyBlock] = []


class StrategyEvaluateRequest(BaseModel):
    """Request to evaluate a strategy against live data."""
    strategy: StrategyCreate
    symbol: str = "BTCUSDT"
    entry_tf: str = "1h"


class BlockResult(BaseModel):
    id: str
    name: str
    passed: bool
    reason: str
    weight: int
    score: int


class StrategyEvaluateResponse(BaseModel):
    symbol: str
    strategy_name: str
    total_score: int
    max_score: int
    min_score: int
    passed: bool
    recommendation: str
    bias: str
    block_results: List[BlockResult]
