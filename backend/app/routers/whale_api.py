from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func
from typing import List, Optional
from datetime import datetime, timedelta
from app.database import get_db
from app.models.whale import WhaleTransaction, Wallet
from app.schemas.whale import WhaleTransactionResponse, WalletResponse
import logging
import httpx
import os
import asyncio
from app.config import get_settings

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

@router.get("/dashboard")
def get_whale_dashboard(db: Session = Depends(get_db)):
    from sqlalchemy import case, String, Float
    from sqlalchemy.sql import cast
    now = datetime.utcnow()
    since = now - timedelta(hours=24)

    # 1. Total Volume & Mega Moves
    summary = db.query(
        func.sum(WhaleTransaction.usd_value).label('total_volume'),
        func.sum(case((WhaleTransaction.usd_value >= 5000000, 1), else_=0)).label('mega_moves_count')
    ).filter(WhaleTransaction.block_time >= since).first()

    total_volume = float(summary.total_volume or 0)
    mega_moves = int(summary.mega_moves_count or 0)

    # 2. Top Asset
    top_asset_row = db.query(
        WhaleTransaction.token_symbol,
        func.sum(WhaleTransaction.usd_value).label('vol')
    ).filter(WhaleTransaction.block_time >= since).group_by(WhaleTransaction.token_symbol).order_by(desc('vol')).first()
    
    top_asset = top_asset_row.token_symbol if top_asset_row else "ETH"

    # 3. Chain Breakdown
    chain_rows = db.query(
        WhaleTransaction.chain_id,
        func.sum(WhaleTransaction.usd_value).label('vol')
    ).filter(WhaleTransaction.block_time >= since).group_by(WhaleTransaction.chain_id).all()
    
    chain_breakdown = {}
    for r in chain_rows:
        pct = (float(r.vol) / total_volume * 100) if total_volume > 0 else 0
        chain_breakdown[r.chain_id] = {
            "volume": float(r.vol),
            "percentage": round(pct, 1)
        }

    # 4. Net Flow Bias (Outflow - Inflow)
    flow_row = db.query(
        func.sum(case((WhaleTransaction.direction == 'outflow', WhaleTransaction.usd_value), else_=0)).label('outflow'),
        func.sum(case((WhaleTransaction.direction == 'inflow', WhaleTransaction.usd_value), else_=0)).label('inflow')
    ).filter(WhaleTransaction.block_time >= since).first()
    
    outflow = float(flow_row.outflow or 0)
    inflow = float(flow_row.inflow or 0)
    net_flow = outflow - inflow
    
    if net_flow > 0:
        bias_label = "BULLISH FLOW"
        bias_desc = f"+${net_flow/1000000:.1f}M Net Accumulation (Outflow from CEX)"
    else:
        bias_label = "BEARISH FLOW"
        bias_desc = f"-${abs(net_flow)/1000000:.1f}M Net Dump (Inflow to CEX)"

    # 5. Top Entities (Wallets)
    entity_rows = db.query(
        Wallet.label,
        Wallet.entity_type,
        Wallet.address,
        Wallet.win_rate,
        Wallet.pnl_usd,
        func.sum(WhaleTransaction.usd_value).label('vol')
    ).join(
        WhaleTransaction,
        (Wallet.id == WhaleTransaction.from_wallet_id) | (Wallet.id == WhaleTransaction.to_wallet_id)
    ).filter(
        WhaleTransaction.block_time >= since,
        Wallet.label.isnot(None)
    ).group_by(Wallet.id).order_by(desc('vol')).limit(6).all()
    
    top_entities = []
    for r in entity_rows:
        top_entities.append({
            "name": r.label,
            "type": r.entity_type,
            "address": r.address,
            "win_rate": r.win_rate or 0,
            "pnl_usd": r.pnl_usd or 0,
            "volume": float(r.vol)
        })
        
    # Generate AI Narrative asynchronously if key is present
    ai_narrative = f"Heuristic detected: {bias_label}. {bias_desc}."
    settings = get_settings()
    nvidia_key = settings.NVIDIA_API_KEY
    if nvidia_key:
        prompt = f"Write a 1-sentence punchy narrative for a crypto whale dashboard. Context: Top asset traded is {top_asset}, Net flow bias is {bias_label} ({bias_desc}), Mega moves count: {mega_moves}. Make it sound like an expert on-chain analyst."
        try:
            with httpx.Client() as client:
                resp = client.post(
                    "https://integrate.api.nvidia.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {nvidia_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "nvidia/nemotron-3-ultra-550b-a55b",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 50
                    },
                    timeout=5.0
                )
                if resp.status_code == 200:
                    ai_narrative = resp.json()["choices"][0]["message"]["content"]
                else:
                    logger.error(f"NVIDIA API error: {resp.text}")
        except Exception as e:
            logger.error(f"Failed to generate AI narrative: {e}")

    return {
        "total_volume_24h": total_volume,
        "mega_moves_count": mega_moves,
        "top_asset": top_asset,
        "chain_breakdown": chain_breakdown,
        "net_flow_bias": {
            "label": bias_label,
            "description": bias_desc,
            "net_flow_usd": net_flow
        },
        "top_entities": top_entities,
        "ai_narrative": ai_narrative
    }

@router.get("/graph")
def get_money_flow_graph(
    chain: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db)
):
    """Generate Node/Edge graph for Money Flow Visualizer."""
    query = db.query(WhaleTransaction).options(
        joinedload(WhaleTransaction.from_wallet),
        joinedload(WhaleTransaction.to_wallet)
    ).order_by(desc(WhaleTransaction.block_time))
    
    if chain and chain.lower() != "all":
        query = query.filter(WhaleTransaction.chain_id == chain.lower())
        
    transactions = query.limit(limit).all()
    
    nodes_dict = {}
    edges = []
    
    for idx, tx in enumerate(transactions):
        # Add from node
        from_id = f"wallet_{tx.from_wallet_id}" if tx.from_wallet_id else f"unknown_{idx}_from"
        if from_id not in nodes_dict:
            nodes_dict[from_id] = {
                "id": from_id,
                "data": {
                    "label": tx.from_wallet.label or (tx.from_wallet.address[:6] + "..." + tx.from_wallet.address[-4:]) if tx.from_wallet else "Unknown",
                    "type": tx.from_wallet.entity_type if tx.from_wallet else "unknown",
                    "win_rate": tx.from_wallet.win_rate if tx.from_wallet else 0,
                    "pnl": tx.from_wallet.pnl_usd if tx.from_wallet else 0
                }
            }
            
        # Add to node
        to_id = f"wallet_{tx.to_wallet_id}" if tx.to_wallet_id else f"unknown_{idx}_to"
        if to_id not in nodes_dict:
            nodes_dict[to_id] = {
                "id": to_id,
                "data": {
                    "label": tx.to_wallet.label or (tx.to_wallet.address[:6] + "..." + tx.to_wallet.address[-4:]) if tx.to_wallet else "Unknown",
                    "type": tx.to_wallet.entity_type if tx.to_wallet else "unknown",
                    "win_rate": tx.to_wallet.win_rate if tx.to_wallet else 0,
                    "pnl": tx.to_wallet.pnl_usd if tx.to_wallet else 0
                }
            }
            
        # Add edge
        edges.append({
            "id": f"edge_{tx.id}",
            "source": from_id,
            "target": to_id,
            "data": {
                "amount": tx.amount,
                "usd_value": tx.usd_value,
                "token": tx.token_symbol
            },
            "animated": True
        })
        
    return {
        "nodes": list(nodes_dict.values()),
        "edges": edges
    }
