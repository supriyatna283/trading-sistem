"""Backtest API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.database import get_db
from app.engines.backtester import BacktestEngine
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/backtest", tags=["Backtesting"])
engine = BacktestEngine()


class BacktestParams(BaseModel):
    symbol: str
    timeframe: str
    days: int
    initial_capital: float = 10000.0
    risk_per_trade_pct: float = 1.0


@router.post("/run")
async def run_backtest(params: BacktestParams):
    """
    Run a simulation over the specified number of days in the past.
    """
    if params.days > 90:
        raise HTTPException(
            status_code=400, detail="Max backtest period is 90 days for now."
        )

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=params.days)
    
    start_ts = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)

    try:
        results = await engine.run_backtest(
            symbol=params.symbol,
            timeframe=params.timeframe,
            start_ts=start_ts,
            end_ts=end_ts,
            initial_capital=params.initial_capital,
            risk_per_trade_pct=params.risk_per_trade_pct
        )
        return results
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
