"""User settings model for risk and preferences."""

from sqlalchemy import Column, Integer, String, Numeric, Boolean, JSON
from app.database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_balance = Column(Numeric(20, 2), default=10000.00)
    risk_per_trade = Column(Numeric(5, 2), default=1.00)
    max_daily_risk = Column(Numeric(5, 2), default=3.00)
    max_concurrent_trades = Column(Integer, default=3)
    telegram_chat_id = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    alert_enabled = Column(Boolean, default=True)
    watchlist = Column(JSON, default=list)

    def to_dict(self):
        return {
            "id": self.id,
            "account_balance": float(self.account_balance),
            "risk_per_trade": float(self.risk_per_trade),
            "max_daily_risk": float(self.max_daily_risk),
            "max_concurrent_trades": self.max_concurrent_trades,
            "telegram_chat_id": self.telegram_chat_id,
            "email": self.email,
            "alert_enabled": self.alert_enabled,
            "watchlist": self.watchlist or [],
        }
