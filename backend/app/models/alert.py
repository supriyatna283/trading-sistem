"""Alert model."""

from sqlalchemy import Column, Integer, String, DateTime, Text, Enum, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    setup_id = Column(Integer, ForeignKey("trade_setups.id"), nullable=True)
    channel = Column(
        Enum("TELEGRAM", "EMAIL", "WEB", name="alert_channel_enum"), nullable=False
    )
    message = Column(Text, nullable=False)
    sent_at = Column(DateTime, server_default=func.now())
    status = Column(
        Enum("SENT", "FAILED", "PENDING", name="alert_status_enum"),
        default="PENDING",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "setup_id": self.setup_id,
            "channel": self.channel,
            "message": self.message,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "status": self.status,
        }
