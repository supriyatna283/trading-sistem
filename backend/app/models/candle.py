"""OHLCV candle data model."""

from sqlalchemy import Column, BigInteger, String, DateTime, Numeric, Index
from app.database import Base


class Candle(Base):
    __tablename__ = "candles"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(5), nullable=False)
    open_time = Column(DateTime, nullable=False)
    open = Column(Numeric(20, 8), nullable=False)
    high = Column(Numeric(20, 8), nullable=False)
    low = Column(Numeric(20, 8), nullable=False)
    close = Column(Numeric(20, 8), nullable=False)
    volume = Column(Numeric(30, 8), nullable=False)

    __table_args__ = (
        Index("idx_candle_lookup", "symbol", "timeframe", "open_time", unique=True),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "open_time": self.open_time.isoformat() if self.open_time else None,
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": float(self.volume),
        }
