"""
Whale Tracker Pro — Scoring API Router
=========================================
New endpoints for the scoring module.

Endpoints:
  GET  /api/whale/watchlist          — list all watchlist coins with latest scores
  POST /api/whale/watchlist          — add coin to watchlist
  PUT  /api/whale/watchlist/{id}     — update watchlist entry
  DELETE /api/whale/watchlist/{id}   — remove from watchlist

  GET  /api/whale/scores/{symbol}    — latest score + full breakdown for a coin
  POST /api/whale/scores/refresh     — trigger immediate re-score for all coins
  GET  /api/whale/scores/{symbol}/history — historical score trend

  GET  /api/whale/smart-wallets      — list smart wallets
  POST /api/whale/smart-wallets      — add smart wallet manually
  DELETE /api/whale/smart-wallets/{id} — remove smart wallet

  GET  /api/whale/alerts/history     — recent alert events
  GET  /api/whale/alerts/config      — current alert config (threshold, channels)
  PUT  /api/whale/alerts/config      — update alert config

  GET  /api/whale/backtest/{symbol}  — run backtest for symbol

  GET  /api/whale/config             — current scoring weights
  PUT  /api/whale/config             — update scoring weights (hot-reload)

  POST /api/whale/labels/import      — bulk import address labels
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.whale import (
    WatchlistCoin, WhaleScore, Wallet, SmartWallet, AlertEvent
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/whale/pro", tags=["Whale Tracker Pro"])


# ---------------------------------------------------------------------------
# Helpers: build scoring engine with configured provider
# ---------------------------------------------------------------------------

def _get_engine(provider_name: str | None = None):
    """Instantiate ScoringEngine with the configured provider."""
    from app.whale.scoring.engine import ScoringEngine
    from app.whale.scoring.config import load_scoring_config
    from app.whale.providers.mock_provider import MockWhaleProvider
    from app.whale.providers.hyperliquid_provider import HyperliquidProvider
    from app.whale.providers.auto_provider import AutoWhaleProvider

    cfg = load_scoring_config()
    pname = (provider_name or cfg.default_provider or "auto").lower()

    if pname == "hyperliquid":
        provider = HyperliquidProvider()
    elif pname == "auto":
        provider = AutoWhaleProvider()
    else:
        provider = MockWhaleProvider()

    return ScoringEngine(provider=provider, config=cfg)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class WatchlistAddRequest(BaseModel):
    symbol: str
    chain_id: str
    token_address: Optional[str] = None
    coingecko_id: Optional[str] = None
    notes: Optional[str] = None


class WatchlistUpdateRequest(BaseModel):
    is_active: Optional[bool] = None
    notes: Optional[str] = None
    coingecko_id: Optional[str] = None


class SmartWalletAddRequest(BaseModel):
    address: str
    chain_id: str
    alias: Optional[str] = None
    win_rate: Optional[float] = None
    pnl_usd: Optional[float] = None
    notes: Optional[str] = None


class ScoringConfigUpdateRequest(BaseModel):
    weight_accumulation: Optional[float] = None
    weight_netflow: Optional[float] = None
    weight_smart_wallet: Optional[float] = None
    weight_concentration: Optional[float] = None
    weight_new_project: Optional[float] = None
    alert_threshold: Optional[float] = None
    alert_critical_threshold: Optional[float] = None
    default_provider: Optional[str] = None


class LabelImportRequest(BaseModel):
    chain_id: str
    labels: dict   # { "0xAddress": {"label": "Binance Hot", "entity_type": "exchange"} }


# ---------------------------------------------------------------------------
# Watchlist endpoints
# ---------------------------------------------------------------------------

@router.get("/watchlist")
def get_watchlist(
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
):
    """Return all watchlist coins with their latest score."""
    query = db.query(WatchlistCoin)
    if active_only:
        query = query.filter(WatchlistCoin.is_active == True)
    coins = query.order_by(WatchlistCoin.added_at.desc()).all()

    result = []
    for coin in coins:
        # Get latest score
        latest_score = (
            db.query(WhaleScore)
            .filter(WhaleScore.coin_id == coin.id)
            .order_by(desc(WhaleScore.scored_at))
            .first()
        )
        result.append({
            "id": coin.id,
            "symbol": coin.symbol,
            "chain_id": coin.chain_id,
            "token_address": coin.token_address,
            "coingecko_id": coin.coingecko_id,
            "is_active": coin.is_active,
            "added_at": coin.added_at.isoformat() if coin.added_at else None,
            "notes": coin.notes,
            "latest_score": {
                "score": latest_score.score,
                "grade": latest_score.grade,
                "scored_at": latest_score.scored_at.isoformat(),
                "is_stale": latest_score.is_stale,
                "flags": latest_score.flags or [],
            } if latest_score else None,
        })

    return result


@router.post("/watchlist", status_code=201)
def add_to_watchlist(
    req: WatchlistAddRequest,
    db: Session = Depends(get_db),
):
    """Add a coin to the watchlist."""
    existing = db.query(WatchlistCoin).filter_by(
        symbol=req.symbol.upper(), chain_id=req.chain_id.lower()
    ).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            db.commit()
            return {"message": "Coin re-activated", "id": existing.id}
        raise HTTPException(status_code=409, detail="Coin already in watchlist")

    coin = WatchlistCoin(
        symbol=req.symbol.upper(),
        chain_id=req.chain_id.lower(),
        token_address=req.token_address,
        coingecko_id=req.coingecko_id,
        notes=req.notes,
    )
    db.add(coin)
    db.commit()
    db.refresh(coin)
    return {"message": "Added to watchlist", "id": coin.id, "symbol": coin.symbol}


@router.put("/watchlist/{coin_id}")
def update_watchlist(
    coin_id: int,
    req: WatchlistUpdateRequest,
    db: Session = Depends(get_db),
):
    coin = db.query(WatchlistCoin).filter_by(id=coin_id).first()
    if not coin:
        raise HTTPException(status_code=404, detail="Coin not found")
    if req.is_active is not None:
        coin.is_active = req.is_active
    if req.notes is not None:
        coin.notes = req.notes
    if req.coingecko_id is not None:
        coin.coingecko_id = req.coingecko_id
    db.commit()
    return {"message": "Updated", "id": coin_id}


@router.delete("/watchlist/{coin_id}")
def remove_from_watchlist(coin_id: int, db: Session = Depends(get_db)):
    coin = db.query(WatchlistCoin).filter_by(id=coin_id).first()
    if not coin:
        raise HTTPException(status_code=404, detail="Coin not found")
    coin.is_active = False
    db.commit()
    return {"message": "Removed from watchlist", "id": coin_id}


# ---------------------------------------------------------------------------
# Score endpoints
# ---------------------------------------------------------------------------

@router.get("/scores/{symbol}")
async def get_score(
    symbol: str,
    chain_id: str = Query("auto"),
    provider: str = Query("auto"),
    db: Session = Depends(get_db),
):
    """Compute (or retrieve cached) whale score for a symbol."""
    symbol = symbol.upper()

    # Try to find from watchlist
    coin = db.query(WatchlistCoin).filter_by(symbol=symbol).first()
    effective_chain = chain_id if chain_id != "auto" else (coin.chain_id if coin else "ethereum")

    # Check if we have a recent score (< 15 minutes old)
    if coin:
        recent = (
            db.query(WhaleScore)
            .filter(
                WhaleScore.coin_id == coin.id,
                WhaleScore.scored_at >= datetime.utcnow() - timedelta(minutes=15),
            )
            .order_by(desc(WhaleScore.scored_at))
            .first()
        )
        if recent and recent.signal_details:
            return {
                **recent.signal_details,
                "cached": True,
                "scored_at": recent.scored_at.isoformat(),
            }

    # Compute fresh score
    engine = _get_engine(provider)
    result = await engine.score(
        symbol=symbol,
        chain_id=effective_chain,
        token_address=coin.token_address if coin else "",
        db=db,
    )

    # Persist to DB
    if coin:
        _persist_score(db, coin.id, result)

    return {**result.to_dict(), "cached": False}


@router.post("/scores/refresh")
async def refresh_all_scores(
    provider: str = Query("auto"),
    db: Session = Depends(get_db),
):
    """Trigger immediate re-score for all active watchlist coins."""
    coins = db.query(WatchlistCoin).filter_by(is_active=True).all()
    engine = _get_engine(provider)
    results = []

    for coin in coins:
        try:
            result = await engine.score(
                symbol=coin.symbol,
                chain_id=coin.chain_id,
                token_address=coin.token_address or "",
                db=db,
            )
            _persist_score(db, coin.id, result)
            results.append({
                "symbol": coin.symbol,
                "score": result.score,
                "grade": result.grade,
                "status": "ok",
            })
        except Exception as e:
            logger.error(f"Score refresh failed for {coin.symbol}: {e}")
            results.append({"symbol": coin.symbol, "status": "error", "error": str(e)})

    return {"refreshed": len(results), "results": results}


@router.get("/scores/{symbol}/history")
def get_score_history(
    symbol: str,
    chain_id: str = Query("auto"),
    days: int = Query(30, le=90),
    db: Session = Depends(get_db),
):
    """Return historical score trend for charting."""
    coin = db.query(WatchlistCoin).filter_by(symbol=symbol.upper()).first()
    if not coin:
        return []

    since = datetime.utcnow() - timedelta(days=days)
    scores = (
        db.query(WhaleScore)
        .filter(WhaleScore.coin_id == coin.id, WhaleScore.scored_at >= since)
        .order_by(WhaleScore.scored_at)
        .all()
    )

    return [
        {
            "date": s.scored_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "score": s.score,
            "grade": s.grade,
            "is_stale": s.is_stale,
            "accumulation_contribution": s.accumulation_contribution,
            "netflow_contribution": s.netflow_contribution,
            "smart_wallet_contribution": s.smart_wallet_contribution,
            "concentration_contribution": s.concentration_contribution,
        }
        for s in scores
    ]


# ---------------------------------------------------------------------------
# Smart Wallet endpoints
# ---------------------------------------------------------------------------

@router.get("/smart-wallets")
def get_smart_wallets(
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
):
    rows = db.query(SmartWallet).filter(
        SmartWallet.is_active == True if active_only else True
    ).all()

    return [
        {
            "id": sw.id,
            "address": sw.wallet.address if sw.wallet else None,
            "chain_id": sw.wallet.chain_id if sw.wallet else None,
            "alias": sw.alias or sw.wallet.label if sw.wallet else None,
            "win_rate": sw.win_rate or (sw.wallet.win_rate if sw.wallet else None),
            "pnl_usd": sw.pnl_usd or (sw.wallet.pnl_usd if sw.wallet else None),
            "added_by": sw.added_by,
            "is_active": sw.is_active,
            "added_at": sw.added_at.isoformat() if sw.added_at else None,
            "notes": sw.notes,
        }
        for sw in rows
    ]


@router.post("/smart-wallets", status_code=201)
def add_smart_wallet(req: SmartWalletAddRequest, db: Session = Depends(get_db)):
    # Get or create wallet
    from app.services.wallet_labeler import enrich_wallet
    import asyncio

    async def _add():
        wallet = await enrich_wallet(db, req.chain_id.lower(), req.address)
        # Upgrade to smart_money
        wallet.entity_type = "smart_money"
        if req.alias:
            wallet.label = req.alias
        if req.win_rate is not None:
            wallet.win_rate = req.win_rate
        if req.pnl_usd is not None:
            wallet.pnl_usd = req.pnl_usd
        db.commit()
        db.refresh(wallet)

        existing = db.query(SmartWallet).filter_by(wallet_id=wallet.id).first()
        if existing:
            existing.is_active = True
            existing.alias = req.alias or existing.alias
            db.commit()
            return {"message": "Smart wallet re-activated", "id": existing.id}

        sw = SmartWallet(
            wallet_id=wallet.id,
            alias=req.alias,
            win_rate=req.win_rate,
            pnl_usd=req.pnl_usd,
            added_by="manual",
            notes=req.notes,
        )
        db.add(sw)
        db.commit()
        db.refresh(sw)
        return {"message": "Smart wallet added", "id": sw.id}

    return asyncio.run(_add())


@router.delete("/smart-wallets/{sw_id}")
def remove_smart_wallet(sw_id: int, db: Session = Depends(get_db)):
    sw = db.query(SmartWallet).filter_by(id=sw_id).first()
    if not sw:
        raise HTTPException(status_code=404, detail="Smart wallet not found")
    sw.is_active = False
    db.commit()
    return {"message": "Removed", "id": sw_id}


# ---------------------------------------------------------------------------
# Alert History endpoint
# ---------------------------------------------------------------------------

@router.get("/alerts/history")
def get_alert_history(
    limit: int = Query(50, le=200),
    symbol: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(AlertEvent).order_by(desc(AlertEvent.sent_at))
    if symbol:
        coin = db.query(WatchlistCoin).filter_by(symbol=symbol.upper()).first()
        if coin:
            query = query.filter(AlertEvent.coin_id == coin.id)
    events = query.limit(limit).all()

    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "severity": e.severity,
            "title": e.title,
            "message": e.message,
            "channel": e.channel,
            "is_sent": e.is_sent,
            "sent_at": e.sent_at.isoformat() if e.sent_at else None,
            "coin_id": e.coin_id,
        }
        for e in events
    ]


# ---------------------------------------------------------------------------
# Scoring Config endpoints
# ---------------------------------------------------------------------------

@router.get("/config")
def get_scoring_config():
    """Return current scoring weights and thresholds."""
    from app.whale.scoring.config import load_scoring_config
    cfg = load_scoring_config()
    return {
        "weight_accumulation": cfg.weight_accumulation,
        "weight_netflow": cfg.weight_netflow,
        "weight_smart_wallet": cfg.weight_smart_wallet,
        "weight_concentration": cfg.weight_concentration,
        "weight_new_project": cfg.weight_new_project,
        "alert_threshold": cfg.alert_threshold,
        "alert_critical_threshold": cfg.alert_critical_threshold,
        "default_provider": cfg.default_provider,
        "grade_labels": cfg.grade_labels,
        "stale_price_move_pct": cfg.stale_price_move_pct,
    }


@router.put("/config")
def update_scoring_config(req: ScoringConfigUpdateRequest):
    """Hot-reload scoring weights. No restart required."""
    from app.whale.scoring.config import load_scoring_config, save_scoring_config
    cfg = load_scoring_config()

    if req.weight_accumulation is not None:
        cfg.weight_accumulation = req.weight_accumulation
    if req.weight_netflow is not None:
        cfg.weight_netflow = req.weight_netflow
    if req.weight_smart_wallet is not None:
        cfg.weight_smart_wallet = req.weight_smart_wallet
    if req.weight_concentration is not None:
        cfg.weight_concentration = req.weight_concentration
    if req.weight_new_project is not None:
        cfg.weight_new_project = req.weight_new_project
    if req.alert_threshold is not None:
        cfg.alert_threshold = req.alert_threshold
    if req.alert_critical_threshold is not None:
        cfg.alert_critical_threshold = req.alert_critical_threshold
    if req.default_provider is not None:
        cfg.default_provider = req.default_provider

    save_scoring_config(cfg)
    return {"message": "Config updated and saved", "config": get_scoring_config()}


# ---------------------------------------------------------------------------
# Backtest endpoint
# ---------------------------------------------------------------------------

@router.get("/backtest/{symbol}")
async def run_backtest(
    symbol: str,
    chain_id: str = Query("auto"),
    forward_days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """Run historical backtest for a symbol."""
    from app.whale.backtest.engine import BacktestEngine
    coin = db.query(WatchlistCoin).filter_by(symbol=symbol.upper()).first()
    effective_chain = chain_id if chain_id != "auto" else (coin.chain_id if coin else "ethereum")
    engine = BacktestEngine()
    result = await engine.run(db, symbol=symbol.upper(), chain_id=effective_chain, forward_days=forward_days)
    return result.to_dict()


# ---------------------------------------------------------------------------
# Label import endpoint
# ---------------------------------------------------------------------------

@router.post("/labels/import")
def import_labels(req: LabelImportRequest, db: Session = Depends(get_db)):
    """Bulk import address labels (exchange, whale, smart_money, etc.)."""
    from app.whale.filters.address_classifier import AddressClassifier
    classifier = AddressClassifier()
    count = classifier.import_labels_from_dict(
        label_dict=req.labels,
        db=db,
        chain_id=req.chain_id.lower(),
        source="manual_import",
    )
    return {"message": f"Imported {count} labels", "chain_id": req.chain_id}


# ---------------------------------------------------------------------------
# Internal helper: persist score to DB
# ---------------------------------------------------------------------------

def _persist_score(db: Session, coin_id: int, result) -> None:
    """Save a ScoreResult to the whale_scores table."""
    from app.whale.scoring.engine import ScoreResult
    try:
        score_row = WhaleScore(
            coin_id=coin_id,
            scored_at=result.scored_at,
            score=result.score,
            grade=result.grade,
            accumulation_score=result.accumulation.raw_score if result.accumulation else 0.0,
            netflow_score=result.netflow.raw_score if result.netflow else 0.0,
            smart_wallet_score=result.smart_wallet.raw_score if result.smart_wallet else 0.0,
            concentration_score=result.concentration.raw_score if result.concentration else 0.0,
            new_project_score=result.new_project.raw_score if result.new_project else 0.0,
            accumulation_contribution=next(
                (b.contribution for b in result.breakdown if b.signal_name == "accumulation"), 0.0
            ),
            netflow_contribution=next(
                (b.contribution for b in result.breakdown if b.signal_name == "exchange_netflow"), 0.0
            ),
            smart_wallet_contribution=next(
                (b.contribution for b in result.breakdown if b.signal_name == "smart_wallet"), 0.0
            ),
            concentration_contribution=next(
                (b.contribution for b in result.breakdown if b.signal_name == "holder_concentration"), 0.0
            ),
            new_project_contribution=next(
                (b.contribution for b in result.breakdown if b.signal_name == "new_project"), 0.0
            ),
            signal_details=result.to_dict(),
            flags=result.flags,
            is_stale=result.is_stale,
            data_source=result.provider,
        )
        db.add(score_row)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[persist_score] Failed for coin {coin_id}: {e}")
