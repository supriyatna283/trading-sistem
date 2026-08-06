"""Shadow trade setup model (False Negatives Tracker)."""

from sqlalchemy import Column, Integer, String, DateTime, Numeric, Text, Enum, JSON
from sqlalchemy.sql import func
from app.database import Base


class ShadowSetup(Base):
    __tablename__ = "shadow_setups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    direction = Column(String(10), nullable=False)
    entry_low = Column(Numeric(20, 8), nullable=False)
    entry_high = Column(Numeric(20, 8), nullable=False)
    stop_loss = Column(Numeric(20, 8), nullable=False)
    take_profit_1 = Column(Numeric(20, 8), nullable=False)
    risk_reward = Column(Numeric(5, 2), nullable=False)
    confluence_score = Column(Integer, default=0)
    timeframe = Column(String(5), nullable=False)
    reason = Column(Text, nullable=True) # Alasan kenapa jadi WAIT (misal: Whale Dump)
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_low": float(self.entry_low),
            "entry_high": float(self.entry_high),
            "stop_loss": float(self.stop_loss),
            "take_profit_1": float(self.take_profit_1),
            "risk_reward": float(self.risk_reward),
            "confluence_score": self.confluence_score,
            "timeframe": self.timeframe,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
