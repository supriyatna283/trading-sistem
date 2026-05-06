"""
Portfolio Router — Portfolio Tracking Endpoints
=================================================
Open positions, balance, PnL, trade history, performance stats.
"""

from fastapi import APIRouter
import logging
from app.engines.portfolio_engine import portfolio_engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/portfolio", tags=["Portfolio"])


@router.get("/balance")
async def get_balance():
    """Get futures wallet balance."""
    return portfolio_engine.get_balance()


@router.get("/positions")
async def get_positions():
    """Get all open futures positions with live PnL."""
    positions = portfolio_engine.get_positions()
    return {"positions": [p.dict() for p in positions], "count": len(positions)}


@router.get("/pnl")
async def get_pnl():
    """Get aggregated real-time PnL across all positions."""
    return portfolio_engine.get_pnl()


@router.get("/history")
async def get_trade_history(days: int = 30, limit: int = 50):
    """Get closed trade history."""
    history = portfolio_engine.get_trade_history(days=days, limit=limit)
    return {"trades": [t.dict() for t in history], "count": len(history)}


@router.get("/stats")
async def get_stats(days: int = 30):
    """Get portfolio performance statistics."""
    stats = portfolio_engine.get_stats(days=days)
    return {"stats": stats.dict()}
