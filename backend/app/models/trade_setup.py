"""Trade setup model."""

from sqlalchemy import Column, Integer, String, DateTime, Numeric, Text, Enum, JSON, Float
from sqlalchemy.sql import func
from datetime import datetime, timezone
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
    confluence_details = Column(JSON, nullable=True)
    status = Column(
        Enum("ACTIVE", "TRIGGERED", "INVALIDATED", "CLOSED", name="setup_status_enum"),
        default="ACTIVE",
    )
    timeframe = Column(String(5), nullable=False)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # ── Signal DB Logging (V6) ──────────────────────────────────────────────
    # Snapshot of conditions at the moment the signal was generated.
    # Critical for backtesting accuracy and post-mortem analysis.
    entry_price_at_signal = Column(Float, nullable=True)   # Last close when signal was created
    market_regime = Column(String(20), nullable=True)       # TRENDING | RANGING | TRANSITION
    htf_bias_4h = Column(String(20), nullable=True)         # 4H bias at signal time
    htf_bias_1d = Column(String(20), nullable=True)         # 1D bias at signal time
    atr_at_signal = Column(Float, nullable=True)            # ATR value at signal time
    # ────────────────────────────────────────────────────────────────────────

    def _get_adjusted_score(self) -> float:
        """
        Confidence Decay System (V6 — item #7):
        Each hour after 2 hours without trigger, score decays by 0.5 pts.

        This does NOT modify the DB value — it's used only in API responses
        and filtering so fresh signals are ranked higher than stale ones.
        """
        if self.created_at is None:
            return float(self.confluence_score or 0)

        try:
            now = datetime.now(timezone.utc)
            created = self.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            hours_old = (now - created).total_seconds() / 3600
            decay = max(0.0, hours_old - 2.0) * 0.5
            return max(0.0, float(self.confluence_score or 0) - decay)
        except Exception:
            return float(self.confluence_score or 0)

    def to_dict(self):
        raw_score = self.confluence_score or 0
        adjusted_score = self._get_adjusted_score()
        max_score = 35  # V6: updated from 33 (session_quality now max 3)

        # Scale adjusted score to 100-point signal score for frontend
        signal_score = round((adjusted_score / max_score) * 100) if max_score > 0 else 0

        # Determine grade based on scaled score
        if signal_score >= 75:
            signal_grade = "A+"
        elif signal_score >= 50:
            signal_grade = "VALID"
        elif signal_score >= 35:
            signal_grade = "WEAK"
        else:
            signal_grade = "NO_TRADE"

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
            "confluence_score": raw_score,
            "adjusted_score": round(adjusted_score, 1),
            "confluence_details": self.confluence_details or {},
            "signal_score": signal_score,
            "signal_grade": signal_grade,
            "max_score": max_score,
            "status": self.status,
            "timeframe": self.timeframe,
            "explanation": self.explanation,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            # Signal DB Logging fields
            "entry_price_at_signal": self.entry_price_at_signal,
            "market_regime": self.market_regime,
            "htf_bias_4h": self.htf_bias_4h,
            "htf_bias_1d": self.htf_bias_1d,
            "atr_at_signal": self.atr_at_signal,
        }
