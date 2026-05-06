"""Trade setup model."""

from sqlalchemy import Column, Integer, String, DateTime, Numeric, Text, Enum
from sqlalchemy.sql import func
from app.database import Base


class TradeSetup(Base):
    __tablename__ = "trade_setups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    direction = Column(Enum("BUY", "SELL", name="direction_enum"), nullable=False)
    entry_low = Column(Numeric(20, 8), nullable=False)
    entry_high = Column(Numeric(20, 8), nullable=False)
    stop_loss = Column(Numeric(20, 8), nullable=False)
    take_profit_1 = Column(Numeric(20, 8), nullable=False)
    take_profit_2 = Column(Numeric(20, 8), nullable=True)
    take_profit_3 = Column(Numeric(20, 8), nullable=True)
    risk_reward = Column(Numeric(5, 2), nullable=False)
    setup_type = Column(String(100), nullable=False)
    confluence_score = Column(Integer, default=0)
    status = Column(
        Enum("ACTIVE", "TRIGGERED", "INVALIDATED", "CLOSED", name="setup_status_enum"),
        default="ACTIVE",
    )
    timeframe = Column(String(5), nullable=False)
    explanation = Column(Text, nullable=True)
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
            "take_profit_2": float(self.take_profit_2) if self.take_profit_2 else None,
            "take_profit_3": float(self.take_profit_3) if self.take_profit_3 else None,
            "risk_reward": float(self.risk_reward),
            "setup_type": self.setup_type,
            "confluence_score": self.confluence_score,
            "status": self.status,
            "timeframe": self.timeframe,
            "explanation": self.explanation,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
