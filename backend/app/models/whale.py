from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey, Index, BigInteger, Boolean, Text, JSON
from sqlalchemy.orm import relationship
import enum
from datetime import datetime, timezone
from app.database import Base


# ---------------------------------------------------------------------------
# Existing models (unchanged)
# ---------------------------------------------------------------------------

class WhaleDirection(str, enum.Enum):
    INFLOW = "inflow"
    OUTFLOW = "outflow"
    TRANSFER = "transfer"


class Chain(Base):
    __tablename__ = "chains"

    id = Column(String(50), primary_key=True, index=True)  # e.g., 'ethereum', 'bsc', 'solana'
    name = Column(String(100), nullable=False)


class WhaleThreshold(Base):
    __tablename__ = "whale_thresholds"

    chain_id = Column(String(50), ForeignKey("chains.id"), primary_key=True)
    usd_threshold = Column(Float, nullable=False, default=500000.0)


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    chain_id = Column(String(50), ForeignKey("chains.id"), nullable=False)
    address = Column(String(255), nullable=False)
    label = Column(String(255), nullable=True)
    entity_type = Column(String(100), nullable=False, default="unlabeled")
    entity_source = Column(String(100), nullable=True)
    confidence = Column(Float, nullable=True)
    win_rate = Column(Float, nullable=True, default=0.0)
    pnl_usd = Column(Float, nullable=True, default=0.0)
    last_enriched_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('ix_wallet_chain_address', 'chain_id', 'address', unique=True),
    )


class WhaleTransaction(Base):
    __tablename__ = "whale_transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    chain_id = Column(String(50), ForeignKey("chains.id"), nullable=False)
    tx_hash = Column(String(255), nullable=False)

    from_wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=True)
    to_wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=True)

    token_symbol = Column(String(50), nullable=False)
    token_address = Column(String(255), nullable=True)
    amount = Column(Float, nullable=False)
    usd_value = Column(Float, nullable=False)
    direction = Column(Enum(WhaleDirection), nullable=False)

    block_time = Column(DateTime, nullable=False, index=True)
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    raw_source = Column(String(50), nullable=False)

    from_wallet = relationship("Wallet", foreign_keys=[from_wallet_id])
    to_wallet = relationship("Wallet", foreign_keys=[to_wallet_id])

    __table_args__ = (
        Index('ix_whale_tx_chain_hash', 'chain_id', 'tx_hash', unique=True),
        Index('ix_whale_tx_usd_value', 'usd_value'),
    )


# ---------------------------------------------------------------------------
# NEW: Whale Tracker Pro — Scoring Module Tables
# ---------------------------------------------------------------------------

class WatchlistCoin(Base):
    """Coins actively tracked for whale scoring."""
    __tablename__ = "watchlist_coins"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)                 # 'BTC', 'HYPE', 'WIF'
    chain_id = Column(String(50), nullable=False)               # 'bitcoin', 'hyperliquid', 'solana'
    token_address = Column(String(255), nullable=True)          # contract address (null for native)
    coingecko_id = Column(String(100), nullable=True)           # CoinGecko ID for price lookups
    is_active = Column(Boolean, nullable=False, default=True)
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes = Column(Text, nullable=True)

    scores = relationship("WhaleScore", back_populates="coin", cascade="all, delete-orphan")
    balances = relationship("WalletBalance", back_populates="coin", cascade="all, delete-orphan")

    __table_args__ = (
        Index('uq_watchlist_symbol_chain', 'symbol', 'chain_id', unique=True),
    )


class WhaleScore(Base):
    """Historical whale scores per coin — time-series for backtest and trend display."""
    __tablename__ = "whale_scores"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    coin_id = Column(Integer, ForeignKey("watchlist_coins.id"), nullable=False)
    scored_at = Column(DateTime, nullable=False, index=True)

    # Final score
    score = Column(Float, nullable=False)                       # 0-100
    grade = Column(String(2), nullable=True)                    # A/B/C/D/F

    # Per-signal breakdown (raw scores, 0-100 each)
    accumulation_score = Column(Float, default=0.0)
    netflow_score = Column(Float, default=0.0)
    smart_wallet_score = Column(Float, default=0.0)
    concentration_score = Column(Float, default=0.0)            # typically negative (risk deduction)
    new_project_score = Column(Float, default=0.0)

    # Contributions (weighted)
    accumulation_contribution = Column(Float, default=0.0)
    netflow_contribution = Column(Float, default=0.0)
    smart_wallet_contribution = Column(Float, default=0.0)
    concentration_contribution = Column(Float, default=0.0)
    new_project_contribution = Column(Float, default=0.0)

    # Full JSON breakdown for UI display (contains detail text, flags, extra data)
    signal_details = Column(JSON, nullable=True)

    # Metadata
    flags = Column(JSON, nullable=True)                         # list of flag strings
    is_stale = Column(Boolean, default=False)                   # price already moved
    data_source = Column(String(50), default="mixed")
    price_at_score = Column(Float, nullable=True)               # USD price when scored
    price_change_7d_pct = Column(Float, nullable=True)          # price change context

    coin = relationship("WatchlistCoin", back_populates="scores")

    __table_args__ = (
        Index('ix_whale_score_coin_time', 'coin_id', 'scored_at'),
    )


class WalletBalance(Base):
    """Time-series snapshots of large wallet balances for a tracked coin."""
    __tablename__ = "wallet_balances"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    coin_id = Column(Integer, ForeignKey("watchlist_coins.id"), nullable=True)
    balance = Column(Float, nullable=False)
    balance_usd = Column(Float, nullable=False)
    snapshot_at = Column(DateTime, nullable=False)

    wallet = relationship("Wallet")
    coin = relationship("WatchlistCoin", back_populates="balances")

    __table_args__ = (
        Index('ix_wallet_balance_snapshot', 'wallet_id', 'snapshot_at'),
        Index('ix_wallet_balance_coin', 'coin_id', 'snapshot_at'),
    )


class SmartWallet(Base):
    """
    Manually curated list of smart money wallets.
    Tracked for position/activity signals in the scoring engine.
    """
    __tablename__ = "smart_wallets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    alias = Column(String(100), nullable=True)                  # human-readable name
    win_rate = Column(Float, nullable=True)
    pnl_usd = Column(Float, nullable=True)
    added_by = Column(String(50), default="manual")             # 'manual' or 'auto'
    is_active = Column(Boolean, default=True)
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes = Column(Text, nullable=True)

    wallet = relationship("Wallet")

    __table_args__ = (
        Index('uq_smart_wallet', 'wallet_id', unique=True),
    )


class AlertEvent(Base):
    """Audit log of all alerts fired by the scoring engine."""
    __tablename__ = "alert_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    coin_id = Column(Integer, ForeignKey("watchlist_coins.id"), nullable=True)
    event_type = Column(String(50), nullable=False)             # 'score_threshold', 'big_accumulation', etc.
    severity = Column(Enum("info", "warning", "critical", name="alert_severity_enum"), default="info")
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    payload = Column(JSON, nullable=True)
    sent_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    channel = Column(String(50), nullable=False)                # 'webhook', 'email', 'dashboard'
    is_sent = Column(Boolean, default=False)

    coin = relationship("WatchlistCoin")

    __table_args__ = (
        Index('ix_alert_event_coin_time', 'coin_id', 'sent_at'),
        Index('ix_alert_event_type', 'event_type'),
    )
