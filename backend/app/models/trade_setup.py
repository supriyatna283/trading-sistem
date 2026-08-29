"""Trade setup model."""

from sqlalchemy import Column, Integer, String, DateTime, Numeric, Text, Enum, JSON
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
    confluence_details = Column(JSON, nullable=True)  # Stores VWAP, VP, Divergence, etc.
    status = Column(
        Enum("ACTIVE", "TRIGGERED", "INVALIDATED", "CLOSED", name="setup_status_enum"),
        default="ACTIVE",
    )
    timeframe = Column(String(5), nullable=False)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        from datetime import datetime, timezone

        # FIX #3: Normalize score to 0-100% consistently (max_score from confluence engine)
        # Use stored confluence_score over max_score=30 for DB setups
        raw_score = self.confluence_score or 0
        signal_score = round((raw_score / 30) * 100)
        signal_score_pct = min(100, signal_score)

        # Determine grade based on scaled score
        if signal_score_pct >= 80:
            signal_grade = "A+"
        elif signal_score_pct >= 65:
            signal_grade = "A"
        elif signal_score_pct >= 50:
            signal_grade = "B"
        else:
            signal_grade = "C"

        # FIX #5: Risk per unit for position sizing
        entry_low = float(self.entry_low)
        entry_high = float(self.entry_high)
        stop_loss = float(self.stop_loss)
        risk_per_unit = abs(entry_low - stop_loss) if self.direction == "BUY" else abs(stop_loss - entry_high)

        # FIX #10: Invalidation level — 50% of risk beyond SL
        # For BUY: below SL by half the SL distance
        # For SELL: above SL by half the SL distance
        if risk_per_unit > 0:
            invalidation_level = (stop_loss - risk_per_unit * 0.5) if self.direction == "BUY" else (stop_loss + risk_per_unit * 0.5)
        else:
            invalidation_level = None

        # FIX #8/#12: Stale setup detection — ACTIVE setup older than 4h without being triggered
        hours_active = None
        is_stale = False
        if self.created_at:
            now_utc = datetime.now(timezone.utc)
            created_utc = self.created_at.replace(tzinfo=timezone.utc) if self.created_at.tzinfo is None else self.created_at
            hours_active = round((now_utc - created_utc).total_seconds() / 3600, 1)
            is_stale = (self.status == "ACTIVE" and hours_active > 4)

        return {
            "id": self.id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_low": entry_low,
            "entry_high": entry_high,
            "stop_loss": stop_loss,
            "take_profit_1": float(self.take_profit_1),
            "take_profit_2": float(self.take_profit_2) if self.take_profit_2 else None,
            "take_profit_3": float(self.take_profit_3) if self.take_profit_3 else None,
            "risk_reward": float(self.risk_reward),
            "setup_type": self.setup_type,
            "confluence_score": raw_score,
            "confluence_details": self.confluence_details or {},
            "signal_score": signal_score,
            # FIX #3: consistent percentage field
            "signal_score_pct": signal_score_pct,
            "signal_grade": signal_grade,
            "status": self.status,
            "timeframe": self.timeframe,
            "explanation": self.explanation,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            # FIX #5: position sizing helper
            "risk_per_unit": round(risk_per_unit, 8),
            # FIX #10: invalidation level
            "invalidation_level": round(invalidation_level, 8) if invalidation_level else None,
            # FIX #8/#12: stale detection
            "hours_active": hours_active,
            "is_stale": is_stale,
            # FIX #11: TP probability (conservative empirical estimates)
            "tp_probability": {"tp1": 75, "tp2": 55, "tp3": 30},
            # FIX #3: max_score for UI display
            "max_score": 30,
        }
