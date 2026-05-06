"""Strategy Router — CRUD + evaluation endpoints (V2)"""

import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.engines.strategy_builder import StrategyBuilderEngine, AVAILABLE_BLOCKS, DEFAULT_STRATEGY
from app.engines.market_data import MarketDataEngine
from app.engines.sentiment import SentimentEngine
from app.engines.news_calendar import NewsCalendarEngine
from app.schemas.strategy import StrategyCreate, StrategyEvaluateRequest

router = APIRouter(prefix="/api/v1/strategies", tags=["Strategy Builder"])

builder_engine = StrategyBuilderEngine()
data_engine = MarketDataEngine()
sentiment_engine = SentimentEngine()
news_engine = NewsCalendarEngine()

TIMEFRAMES = ["1d", "4h", "1h", "15m", "5m"]

# In-memory strategy store (replace with DB when strategy model is migrated)
_strategies: dict = {
    0: {
        "id": 0,
        "name": DEFAULT_STRATEGY["name"],
        "description": DEFAULT_STRATEGY["description"],
        "min_score": DEFAULT_STRATEGY["min_score"],
        "blocks": DEFAULT_STRATEGY["blocks"],
        "is_default": True,
    }
}
_next_id = 1


@router.get("/blocks")
async def get_available_blocks():
    """List all available strategy building blocks."""
    return {"blocks": builder_engine.get_available_blocks()}


@router.get("")
async def list_strategies():
    """List all saved strategies."""
    return {"strategies": list(_strategies.values())}


@router.post("")
async def create_strategy(data: StrategyCreate):
    """Save a new strategy."""
    global _next_id
    strategy_id = _next_id
    _next_id += 1

    strategy = {
        "id": strategy_id,
        "name": data.name,
        "description": data.description,
        "min_score": data.min_score,
        "blocks": [b.model_dump() for b in data.blocks],
        "is_default": False,
    }
    _strategies[strategy_id] = strategy
    return {"strategy": strategy}


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: int):
    """Get a specific strategy by ID."""
    strategy = _strategies.get(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"strategy": strategy}


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: int):
    """Delete a strategy (cannot delete default)."""
    strategy = _strategies.get(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if strategy.get("is_default"):
        raise HTTPException(status_code=400, detail="Cannot delete the default strategy")
    del _strategies[strategy_id]
    return {"message": f"Strategy {strategy_id} deleted"}


@router.post("/evaluate")
async def evaluate_strategy(req: StrategyEvaluateRequest):
    """Evaluate a strategy against live market data with macro context."""
    symbol = req.symbol.upper()
    entry_tf = req.entry_tf
    strategy = req.strategy.model_dump()

    # Fetch all timeframes + macro context in parallel
    candle_tasks = [data_engine.get_candles(symbol, tf, 200) for tf in TIMEFRAMES]
    sentiment_task = sentiment_engine.get_full_sentiment()
    news_task = news_engine.get_events()

    all_results = await asyncio.gather(
        *candle_tasks, sentiment_task, news_task,
        return_exceptions=True,
    )

    candles_by_tf = {}
    for i, (tf, result) in enumerate(zip(TIMEFRAMES, all_results[:len(TIMEFRAMES)])):
        if isinstance(result, Exception) or result is None:
            import pandas as pd
            candles_by_tf[tf] = pd.DataFrame()
        else:
            candles_by_tf[tf] = result

    sentiment_data = all_results[len(TIMEFRAMES)] if not isinstance(all_results[len(TIMEFRAMES)], Exception) else None
    news_events = all_results[len(TIMEFRAMES) + 1] if not isinstance(all_results[len(TIMEFRAMES) + 1], Exception) else None

    result = builder_engine.evaluate(
        strategy, candles_by_tf, symbol, entry_tf,
        news_events=news_events,
        sentiment_data=sentiment_data,
    )
    return {"evaluation": result}
