from sqlalchemy import Column, Integer, String, DateTime, Numeric
from sqlalchemy.sql import func
from app.database import Base

class AISignalResult(Base):
    __tablename__ = "ai_signal_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), index=True, nullable=False)
    timeframe = Column(String(5), nullable=False)
    direction = Column(String(10), nullable=False)  # BUY / SELL
    grade = Column(String(5), nullable=False)       # A+ / A / B / C
    confluence_pct = Column(Integer, nullable=False)

    entry_low = Column(Numeric(20, 8), nullable=False)
    entry_high = Column(Numeric(20, 8), nullable=False)
    stop_loss = Column(Numeric(20, 8), nullable=False)
    tp1 = Column(Numeric(20, 8), nullable=False)
    tp2 = Column(Numeric(20, 8), nullable=True)
    tp3 = Column(Numeric(20, 8), nullable=True)

    # Tracking outcome
    status = Column(String(20), default="ACTIVE")
    # ACTIVE / WIN_TP1 / WIN_TP2 / WIN_TP3 / LOSS / EXPIRED
    hit_price = Column(Numeric(20, 8), nullable=True)
    hit_at = Column(DateTime, nullable=True)
    pnl_pct = Column(Numeric(8, 4), nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "grade": self.grade,
            "confluence_pct": self.confluence_pct,
            "entry_low": float(self.entry_low) if self.entry_low else None,
            "entry_high": float(self.entry_high) if self.entry_high else None,
            "stop_loss": float(self.stop_loss) if self.stop_loss else None,
            "tp1": float(self.tp1) if self.tp1 else None,
            "tp2": float(self.tp2) if self.tp2 else None,
            "tp3": float(self.tp3) if self.tp3 else None,
            "status": self.status,
            "hit_price": float(self.hit_price) if self.hit_price else None,
            "hit_at": self.hit_at.isoformat() if self.hit_at else None,
            "pnl_pct": float(self.pnl_pct) if self.pnl_pct else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
