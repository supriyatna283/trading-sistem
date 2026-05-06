"""Scanner result model."""

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.database import Base


class ScannerResult(Base):
    __tablename__ = "scanner_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    trend = Column(String(20), nullable=False)
    liquidity_status = Column(String(100), nullable=True)
    setup_status = Column(String(100), nullable=True)
    confluence_score = Column(Integer, default=0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "trend": self.trend,
            "liquidity_status": self.liquidity_status,
            "setup_status": self.setup_status,
            "confluence_score": self.confluence_score,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
