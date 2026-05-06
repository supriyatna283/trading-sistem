"""Risk management API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user_settings import UserSettings
from app.engines.risk_management import RiskManagementEngine
from app.schemas.risk import RiskSettingsSchema, PositionSizeRequest

router = APIRouter(prefix="/api/v1/risk", tags=["Risk Management"])
risk_engine = RiskManagementEngine()


@router.get("/settings")
async def get_risk_settings(db: Session = Depends(get_db)):
    """Get current risk management settings."""
    settings = db.query(UserSettings).first()
    if not settings:
        settings = UserSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return {"settings": settings.to_dict()}


@router.put("/settings")
async def update_risk_settings(
    data: RiskSettingsSchema,
    db: Session = Depends(get_db),
):
    """Update risk management settings."""
    settings = db.query(UserSettings).first()
    if not settings:
        settings = UserSettings()
        db.add(settings)

    settings.account_balance = data.account_balance
    settings.risk_per_trade = data.risk_per_trade
    settings.max_daily_risk = data.max_daily_risk
    settings.max_concurrent_trades = data.max_concurrent_trades
    db.commit()
    db.refresh(settings)
    return {"settings": settings.to_dict()}


@router.post("/calculate")
async def calculate_position_size(req: PositionSizeRequest):
    """Calculate position size based on risk parameters."""
    result = risk_engine.calculate_position_size(req)
    return {"result": result.model_dump()}
