from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func
from typing import List, Optional
from datetime import datetime, timedelta
from app.database import get_db
from app.models.whale import WhaleTransaction, Wallet
from app.schemas.whale import WhaleTransactionResponse, WalletResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/whale", tags=["Whale Tracker"])

@router.get("/live", response_model=List[WhaleTransactionResponse])
def get_live_whales(
    chain: Optional[str] = None,
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db)
):
    """Get the latest whale transactions for the live feed."""
    query = db.query(WhaleTransaction).options(
        joinedload(WhaleTransaction.from_wallet),
        joinedload(WhaleTransaction.to_wallet)
    )
    if chain and chain.lower() != "all":
        query = query.filter(WhaleTransaction.chain_id == chain.lower())
        
    transactions = query.order_by(desc(WhaleTransaction.block_time)).limit(limit).all()
    return transactions

@router.get("/history")
def get_whale_history(
    chain: Optional[str] = None,
    days: int = Query(7, le=30),
    min_usd: Optional[float] = None,
    entity_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get historical aggregated volume for charts."""
    since = datetime.utcnow() - timedelta(days=days)
    
    query = db.query(
        func.date(WhaleTransaction.block_time).label('date'),
        func.sum(WhaleTransaction.usd_value).label('volume'),
        func.count(WhaleTransaction.id).label('tx_count')
    ).filter(WhaleTransaction.block_time >= since)

    if chain and chain.lower() != "all":
        query = query.filter(WhaleTransaction.chain_id == chain.lower())
    if min_usd:
        query = query.filter(WhaleTransaction.usd_value >= min_usd)
        
    if entity_type and entity_type.lower() != "all":
        # Simplified: we filter if either from or to is the entity type
        query = query.join(Wallet, WhaleTransaction.from_wallet_id == Wallet.id).filter(
            Wallet.entity_type == entity_type
        ) # Note: this is a simplification for the chart

    results = query.group_by(func.date(WhaleTransaction.block_time)).order_by(func.date(WhaleTransaction.block_time)).all()
    
    return [
        {
            "date": str(r.date),
            "volume": r.volume or 0,
            "tx_count": r.tx_count or 0
        } for r in results
    ]

@router.get("/top-wallets")
def get_top_wallets(
    chain: Optional[str] = None,
    period: str = Query("24h"),
    db: Session = Depends(get_db)
):
    """Get top wallets by volume."""
    hours = 24 if period == "24h" else (24*7 if period == "7d" else 24*30)
    since = datetime.utcnow() - timedelta(hours=hours)

    # Simplified approach: Sum volume where wallet is either sender or receiver
    # In a real heavy-load scenario, a materialized view is better.
    query = db.query(
        Wallet,
        func.sum(WhaleTransaction.usd_value).label('total_volume')
    ).join(
        WhaleTransaction,
        (Wallet.id == WhaleTransaction.from_wallet_id) | (Wallet.id == WhaleTransaction.to_wallet_id)
    ).filter(
        WhaleTransaction.block_time >= since
    )

    if chain and chain.lower() != "all":
        query = query.filter(WhaleTransaction.chain_id == chain.lower())

    results = query.group_by(Wallet.id).order_by(desc('total_volume')).limit(10).all()

    return [
        {
            "wallet": WalletResponse.from_orm(r.Wallet),
            "total_volume": r.total_volume or 0
        } for r in results
    ]
