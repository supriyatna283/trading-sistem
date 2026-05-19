"""Alert API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.alert import Alert
from app.models.user_settings import UserSettings
from app.services.alert_service import alert_service
from app.security import require_api_key

router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts"])


@router.get("")
async def list_alerts(db: Session = Depends(get_db)):
    """List alert history."""
    alerts = db.query(Alert).order_by(Alert.sent_at.desc()).limit(50).all()
    return {"alerts": [a.to_dict() for a in alerts]}


@router.put("/settings", dependencies=[Depends(require_api_key)])
async def update_alert_settings(
    telegram_chat_id: str = None,
    email: str = None,
    alert_enabled: bool = True,
    db: Session = Depends(get_db),
):
    """Update alert channel settings."""
    settings = db.query(UserSettings).first()
    if not settings:
        settings = UserSettings()
        db.add(settings)

    if telegram_chat_id is not None:
        settings.telegram_chat_id = telegram_chat_id
    if email is not None:
        settings.email = email
    settings.alert_enabled = alert_enabled
    db.commit()
    return {"settings": settings.to_dict()}


@router.post("/test", dependencies=[Depends(require_api_key)])
async def test_alert():
    """Send a test alert to verify configuration."""
    test_setup = {
        "symbol": "BTCUSDT",
        "direction": "BUY",
        "entry_low": 67050,
        "entry_high": 67200,
        "stop_loss": 66680,
        "take_profit_1": 68400,
        "risk_reward": 3.0,
        "setup_type": "Test Alert",
        "confluence_score": 6,
    }
    results = await alert_service.send_setup_alert(test_setup)
    return {"results": results}
