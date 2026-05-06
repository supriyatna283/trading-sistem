"""Journal API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.journal_entry import JournalEntry
from app.engines.journal import JournalAnalyticsEngine
from pydantic import BaseModel
from app.schemas.journal import JournalEntryCreate
from app.models.trade_setup import TradeSetup

class SetupResult(BaseModel):
    result: str  # WIN, LOSS, BREAKEVEN
    notes: str = ""


router = APIRouter(prefix="/api/v1/journal", tags=["Trading Journal"])

analytics_engine = JournalAnalyticsEngine()


@router.get("")
async def list_entries(db: Session = Depends(get_db)):
    """List all journal entries."""
    entries = db.query(JournalEntry).order_by(JournalEntry.created_at.desc()).limit(100).all()
    return {"entries": [e.to_dict() for e in entries]}


@router.post("")
async def create_entry(data: JournalEntryCreate, db: Session = Depends(get_db)):
    """Create a new journal entry."""
    entry = JournalEntry(
        setup_id=data.setup_id,
        symbol=data.symbol,
        direction=data.direction,
        entry_price=data.entry_price,
        exit_price=data.exit_price,
        stop_loss=data.stop_loss,
        take_profit=data.take_profit,
        position_size=data.position_size,
        pnl=data.pnl,
        r_multiple=data.r_multiple,
        result=data.result,
        notes=data.notes,
        screenshot_url=data.screenshot_url,
        entered_at=data.entered_at,
        closed_at=data.closed_at,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"entry": entry.to_dict()}


@router.post("/from-setup/{setup_id}")
async def log_setup(setup_id: int, data: SetupResult, db: Session = Depends(get_db)):
    """Automatically log a journal entry from a TradeSetup."""
    setup = db.query(TradeSetup).filter(TradeSetup.id == setup_id).first()
    if not setup:
        return {"error": "Setup not found"}
        
    # Calculate automated metrics
    exit_price = None
    pnl = 0.0
    
    # Calculate position size risk based on 1% risk per trade logic (or dummy)
    risk_amt = abs(float(setup.entry_low) - float(setup.stop_loss)) or 1.0
    
    if data.result == "WIN":
        exit_price = float(setup.take_profit_1)
        r_mult = float(setup.risk_reward)
        pnl = float(setup.take_profit_1) - float(setup.entry_low)
        if setup.direction == "SELL": pnl = -pnl
    elif data.result == "LOSS":
        exit_price = float(setup.stop_loss)
        r_mult = -1.0
        pnl = float(setup.stop_loss) - float(setup.entry_low)
        if setup.direction == "SELL": pnl = -pnl
    else: # BREAKEVEN
        exit_price = float(setup.entry_low)
        r_mult = 0.0
        pnl = 0.0
        
    # Assume 1 standard size for PNL absolute value calculation
    position_size = 1.0
    
    entry = JournalEntry(
        setup_id=setup.id,
        symbol=setup.symbol,
        direction=setup.direction,
        entry_price=setup.entry_low,
        exit_price=exit_price,
        stop_loss=setup.stop_loss,
        take_profit=setup.take_profit_1,
        position_size=position_size,
        pnl=pnl,
        r_multiple=r_mult,
        result=data.result,
        notes=f"Auto-logged from setup. {data.notes}",
    )
    
    setup.status = "CLOSED"
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"message": "Setup logged to journal successfully", "entry": entry.to_dict()}



@router.get("/analytics")
async def get_analytics(db: Session = Depends(get_db)):
    """Get performance analytics from journal entries."""
    entries = db.query(JournalEntry).all()
    if not entries:
        return {
            "analytics": {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "avg_r_multiple": 0.0,
                "total_pnl": 0.0,
                "wins": 0,
                "losses": 0,
            }
        }
    entry_dicts = [e.to_dict() for e in entries]
    analytics = analytics_engine.calculate(entry_dicts)
    return {"analytics": analytics.model_dump()}
