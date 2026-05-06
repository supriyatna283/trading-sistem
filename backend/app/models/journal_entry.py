"""Journal entry model for trade recording."""

from sqlalchemy import Column, Integer, String, DateTime, Numeric, Text, Enum, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    setup_id = Column(Integer, ForeignKey("trade_setups.id"), nullable=True)
    symbol = Column(String(20), nullable=False, index=True)
    direction = Column(Enum("BUY", "SELL", name="journal_direction_enum"), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    exit_price = Column(Numeric(20, 8), nullable=True)
    stop_loss = Column(Numeric(20, 8), nullable=False)
    take_profit = Column(Numeric(20, 8), nullable=False)
    position_size = Column(Numeric(20, 8), nullable=False)
    pnl = Column(Numeric(20, 8), nullable=True)
    r_multiple = Column(Numeric(5, 2), nullable=True)
    result = Column(
        Enum("WIN", "LOSS", "BREAKEVEN", name="result_enum"), nullable=True
    )
    notes = Column(Text, nullable=True)
    screenshot_url = Column(String(500), nullable=True)
    entered_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "setup_id": self.setup_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": float(self.entry_price),
            "exit_price": float(self.exit_price) if self.exit_price else None,
            "stop_loss": float(self.stop_loss),
            "take_profit": float(self.take_profit),
            "position_size": float(self.position_size),
            "pnl": float(self.pnl) if self.pnl else None,
            "r_multiple": float(self.r_multiple) if self.r_multiple else None,
            "result": self.result,
            "notes": self.notes,
            "screenshot_url": self.screenshot_url,
            "entered_at": self.entered_at.isoformat() if self.entered_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
