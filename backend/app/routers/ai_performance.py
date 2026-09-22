"""
AI Performance Router
=====================
Endpoints for tracking and displaying AI Analyst historical performance.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import math

from app.database import get_db
from app.models.ai_signal_result import AISignalResult

router = APIRouter(prefix="/api/v1/ai/performance", tags=["AI Performance"])

@router.get("/")
def get_performance_stats(
    db: Session = Depends(get_db),
    time_window: str = Query("30d", description="Time window (e.g. 7d, 30d, 90d, all)")
):
    """Get high-level AI signal performance statistics."""
    query = db.query(AISignalResult)
    
    if time_window != "all":
        days = int(time_window.replace("d", ""))
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(AISignalResult.created_at >= cutoff)
        
    signals = query.all()
    
    total = len(signals)
    active = sum(1 for s in signals if s.status == "ACTIVE")
    completed = total - active
    
    wins = sum(1 for s in signals if s.status.startswith("WIN"))
    losses = sum(1 for s in signals if s.status == "LOSS")
    
    win_rate = (wins / completed * 100) if completed > 0 else 0
    total_pnl = sum(float(s.pnl_pct) for s in signals if s.pnl_pct is not None)
    
    return {
        "total_signals": total,
        "active_signals": active,
        "completed_signals": completed,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 2),
        "total_pnl_pct": round(total_pnl, 2),
        "avg_pnl_per_trade": round(total_pnl / completed, 2) if completed > 0 else 0
    }

@router.get("/history")
def get_performance_history(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None
):
    """Get paginated history of AI signals."""
    query = db.query(AISignalResult)
    
    if status:
        if status == "WIN":
            query = query.filter(AISignalResult.status.like("WIN%"))
        else:
            query = query.filter(AISignalResult.status == status)
            
    total = query.count()
    signals = query.order_by(AISignalResult.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    
    return {
        "items": [s.to_dict() for s in signals],
        "total": total,
        "page": page,
        "pages": math.ceil(total / limit)
    }

@router.get("/equity")
def get_performance_equity(
    db: Session = Depends(get_db),
    time_window: str = Query("30d")
):
    """Get equity curve data points."""
    query = db.query(AISignalResult).filter(AISignalResult.pnl_pct.isnot(None))
    
    if time_window != "all":
        days = int(time_window.replace("d", ""))
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(AISignalResult.hit_at >= cutoff)
        
    signals = query.order_by(AISignalResult.hit_at.asc()).all()
    
    equity = 0
    curve = []
    
    for s in signals:
        equity += float(s.pnl_pct)
        curve.append({
            "time": s.hit_at.isoformat() if s.hit_at else None,
            "equity": round(equity, 2),
            "pnl": round(float(s.pnl_pct), 2),
            "symbol": s.symbol
        })
        
    return curve
