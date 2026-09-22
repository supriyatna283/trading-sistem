"""SymbolNote — per-symbol trader notes stored in the database."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from app.database import Base


class SymbolNote(Base):
    __tablename__ = "symbol_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, unique=True, index=True)
    # Free-form analysis text
    content = Column(Text, nullable=True, default="")
    # Bias tag: BULLISH | BEARISH | NEUTRAL | WATCH | AVOID
    bias = Column(String(20), nullable=True, default="NEUTRAL")
    # JSON list of key levels: [{"label": "R1", "price": 65000}, ...]
    key_levels = Column(JSON, nullable=True, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "content": self.content or "",
            "bias": self.bias or "NEUTRAL",
            "key_levels": self.key_levels or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
