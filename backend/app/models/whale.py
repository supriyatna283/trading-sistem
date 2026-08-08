from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey, Index, BigInteger
from sqlalchemy.orm import relationship
import enum
from datetime import datetime, timezone
from app.database import Base

class WhaleDirection(str, enum.Enum):
    INFLOW = "inflow"
    OUTFLOW = "outflow"
    TRANSFER = "transfer"

class Chain(Base):
    __tablename__ = "chains"

    id = Column(String(50), primary_key=True, index=True) # e.g., 'ethereum', 'bsc', 'solana'
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
    entity_type = Column(String(100), nullable=False, default="unlabeled") # exchange, fund, whale, unlabeled
    entity_source = Column(String(100), nullable=True) # e.g., 'arkham'
    confidence = Column(Float, nullable=True)
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
    raw_source = Column(String(50), nullable=False) # 'moralis', 'helius'

    from_wallet = relationship("Wallet", foreign_keys=[from_wallet_id])
    to_wallet = relationship("Wallet", foreign_keys=[to_wallet_id])

    __table_args__ = (
        Index('ix_whale_tx_chain_hash', 'chain_id', 'tx_hash', unique=True),
        Index('ix_whale_tx_usd_value', 'usd_value'),
    )
