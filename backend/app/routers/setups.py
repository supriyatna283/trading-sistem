"""Trading setups API endpoints — V4 uses REAL Binance data + full macro integration + Phase 3 Power Features."""

from fastapi import APIRouter, Depends, Query
from app.security import require_api_key
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
from app.database import get_db
from app.models.trade_setup import TradeSetup
from app.engines.market_data import MarketDataEngine
from app.engines.market_structure import MarketStructureAnalyzer
from app.engines.smart_money import SmartMoneyConceptsEngine
from app.engines.confluence import ConfluenceEngine, MAX_SCORE
from app.engines.setup_generator import SetupGenerator
from app.engines.mtf_confirmation import MTFConfirmationEngine
from app.engines.sentiment import SentimentEngine
from app.engines.news_calendar import NewsCalendarEngine
from app.engines.market_intel import MarketIntelEngine
from app.schemas.trade_setup import SetupStatusUpdate

router = APIRouter(prefix="/api/v1/setups", tags=["Trading Setups"])

# Phase 3: min score = 16 (threshold recalibrated for max_score=36)
MIN_SCORE = 16
setup_gen = SetupGenerator(min_confluence_score=MIN_SCORE, min_rr=1.8)
confluence_engine = ConfluenceEngine(min_confluence_score=MIN_SCORE)
smc_engine = SmartMoneyConceptsEngine()
structure_analyzer = MarketStructureAnalyzer()
data_engine = MarketDataEngine()
mtf_engine = MTFConfirmationEngine()
sentiment_engine = SentimentEngine()
news_engine = NewsCalendarEngine()
market_intel_engine = MarketIntelEngine()

# ── Trading Mode Configuration ─────────────────────────────────────────────────
# Defines which timeframes to fetch & min score per mode.
MODE_CONFIG = {
    "scalping": {
        "timeframes": ["1h", "15m", "5m", "1m"],  # primary context → detail
        "entry_tf": "5m",
        "min_score": 10,   # lower bar — fast signals
        "label": "Scalping",
    },
    "day_trading": {
        "timeframes": ["1d", "4h", "1h", "15m"],  # standard MTF
        "entry_tf": "1h",
        "min_score": 16,   # standard
        "label": "Day Trading",
    },
    "swing_trading": {
        "timeframes": ["1d", "4h", "1h", "15m"],  # same MTF, higher bar
        "entry_tf": "4h",
        "min_score": 20,   # higher quality required
        "label": "Swing Trading",
    },
}
DEFAULT_MODE = "day_trading"


def _sanitize_details(details: dict) -> dict:
    """Convert confluence details to a JSON-safe dict."""
    try:
        return json.loads(json.dumps(details, default=lambda o: str(o) if not isinstance(o, (int, float, bool, str, list, dict, type(None))) else o))
    except Exception:
        return {}


@router.get("")
async def list_setups(
    status: str = Query(None),
    symbol: str = Query(None),
    db: Session = Depends(get_db),
):
    """List trading setups, optionally filtered by status or symbol."""
    query = db.query(TradeSetup)
    if status:
        query = query.filter(TradeSetup.status == status)
    if symbol:
        query = query.filter(TradeSetup.symbol == symbol.upper())
    query = query.order_by(TradeSetup.created_at.desc())
    setups = query.all()
    return {"setups": [s.to_dict() for s in setups]}


@router.get("/generate/{symbol}")
async def generate_setup(
    symbol: str,
    timeframe: str = Query("1h"),
    trading_mode: str = Query(DEFAULT_MODE, description="Trading mode: scalping | day_trading | swing_trading"),
    db: Session = Depends(get_db),
):
    """
    Generate a trade setup using REAL market data from Binance.
    Supports trading_mode param to auto-select optimal entry timeframe and quality gate.
    """
    import asyncio
    candles_by_tf = {}

    # Resolve mode config
    cfg = MODE_CONFIG.get(trading_mode, MODE_CONFIG[DEFAULT_MODE])
    tfs = cfg["timeframes"]
    # Use provided timeframe if explicitly given, else use mode default entry TF
    entry_tf = timeframe if timeframe != "1h" or trading_mode == "day_trading" else cfg["entry_tf"]
    # Ensure entry_tf is included in fetch list
    if entry_tf not in tfs:
        tfs = [entry_tf] + tfs

    mode_min_score = cfg["min_score"]

    # Fetch candles + macro context in parallel
    candle_tasks = [data_engine.get_candles(symbol.upper(), tf, 200) for tf in tfs]
    sentiment_task = sentiment_engine.get_full_sentiment()
    news_task = news_engine.get_events()

    all_results = await asyncio.gather(
        *candle_tasks, sentiment_task, news_task,
        return_exceptions=True,
    )

    # Unpack candle results
    for i, df in enumerate(all_results[:len(tfs)]):
        if not isinstance(df, Exception) and not df.empty:
            candles_by_tf[tfs[i]] = df

    # Unpack macro context
    sentiment_data = all_results[len(tfs)] if not isinstance(all_results[len(tfs)], Exception) else None
    news_events = all_results[len(tfs) + 1] if not isinstance(all_results[len(tfs) + 1], Exception) else None

    if not candles_by_tf:
        return {
            "setup": None,
            "confluence": None,
            "message": f"Could not fetch market data for {symbol}",
        }

    # Run confluence analysis — use resolved entry TF
    entry_df = candles_by_tf.get(entry_tf) or candles_by_tf.get("1h") or next(iter(candles_by_tf.values()), None)
    if entry_df is None or entry_df.empty:
        return {
            "setup": None,
            "confluence": None,
            "message": f"No candle data available for {symbol} on {entry_tf}",
        }

    # MTF Confirmation
    mtf_result = mtf_engine.analyze(candles_by_tf, symbol.upper())
    structure = structure_analyzer.analyze(entry_df, symbol.upper(), entry_tf)
    smc = smc_engine.analyze(entry_df, symbol.upper(), entry_tf)

    # Phase 3: Fetch Market Intel (OI, order book, S&R) + Volume Delta
    latest_price = float(entry_df.iloc[-1]["close"]) if not entry_df.empty else 0
    market_intel_data = None
    volume_delta = None
    try:
        market_intel_data = await market_intel_engine.get_overview(
            symbol.upper(), df=entry_df, current_price=latest_price
        )
    except Exception:
        pass

    confluence = confluence_engine.score(
        candles_by_tf, symbol.upper(), entry_tf,
        sentiment_data=sentiment_data,
        news_events=news_events,
        mtf_result=mtf_result,
        market_intel_data=market_intel_data,
    )

    # Phase 3: Volume Delta (only if score is promising, to save API calls)
    if confluence.total_score >= 12:
        try:
            from app.engines.order_flow_engine import order_flow_engine
            footprint = await order_flow_engine.get_footprint(symbol.upper(), timeframe, limit=1)
            if footprint and len(footprint) > 0:
                volume_delta = footprint[-1].get("delta", 0)
        except Exception:
            pass

    # Mode-aware quality gate: only generate if score meets mode minimum
    if confluence.total_score < mode_min_score:
        return {
            "setup": None,
            "confluence": confluence.model_dump(),
            "message": f"Score {confluence.total_score}/{confluence.max_score} below {cfg['label']} threshold ({mode_min_score}).",
        }

    # Generate setup (V4 — full Phase 3 power features)
    setup = setup_gen.generate(
        symbol.upper(), entry_tf, confluence, smc, structure, entry_df,
        mtf_result=mtf_result,
        news_events=news_events,
        sentiment_data=sentiment_data,
        market_intel_data=market_intel_data,
        volume_delta=volume_delta,
    )

    if setup:
        # Expire older ACTIVE setups for the same symbol & timeframe
        active_setups = db.query(TradeSetup).filter(
            TradeSetup.symbol == setup.symbol,
            TradeSetup.timeframe == setup.timeframe,
            TradeSetup.status == "ACTIVE"
        ).all()
        for s in active_setups:
            s.status = "INVALIDATED"

        # Persist to DB — record the trading_mode so frontend can filter by it
        db_setup = TradeSetup(
            symbol=setup.symbol,
            direction=setup.direction,
            entry_low=setup.entry_low,
            entry_high=setup.entry_high,
            stop_loss=setup.stop_loss,
            take_profit_1=setup.take_profit_1,
            take_profit_2=setup.take_profit_2,
            take_profit_3=setup.take_profit_3,
            risk_reward=setup.risk_reward,
            setup_type=setup.setup_type,
            confluence_score=setup.confluence_score,
            confluence_details=_sanitize_details(confluence.details),
            status=setup.status,
            timeframe=setup.timeframe,
            explanation=setup.explanation,
        )
        db.add(db_setup)
        db.commit()
        db.refresh(db_setup)

        # 🔔 Send Telegram notification for generated setup
        try:
            from app.services.telegram_bot import send_telegram_signal
            import asyncio
            asyncio.create_task(send_telegram_signal(setup, timeframe))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"⚠️ Telegram send failed: {e}")

        return {
            "setup": db_setup.to_dict(),
            "confluence": confluence.model_dump(),
            "message": f"[{cfg['label']}] {setup.direction} setup for {symbol} on {entry_tf} (Score: {confluence.total_score}/{confluence.max_score}, R:R 1:{setup.risk_reward})",
        }

    return {
        "setup": None,
        "confluence": confluence.model_dump(),
        "message": f"[{cfg['label']}] No setup for {symbol} — Score: {confluence.total_score}/{confluence.max_score} (min: {mode_min_score}/{MAX_SCORE}). Timeframe: {entry_tf}.",
    }


@router.post("/generate/all", dependencies=[Depends(require_api_key)])
async def generate_all_setups(
    timeframe: str = Query("1h"),
    trading_mode: str = Query(DEFAULT_MODE, description="Trading mode: scalping | day_trading | swing_trading"),
):
    """
    Trigger signal generation for ALL dynamic symbols using the selected trading mode.
    - scalping     → entry TF: 5m,  min score: 10
    - day_trading  → entry TF: 1h,  min score: 16
    - swing_trading→ entry TF: 4h,  min score: 20
    Each symbol gets its own DB session to avoid SQLAlchemy concurrent-write conflicts.
    """
    import asyncio
    from app.database import SessionLocal

    cfg = MODE_CONFIG.get(trading_mode, MODE_CONFIG[DEFAULT_MODE])
    # Use provided timeframe, else fall back to mode entry TF
    resolved_tf = timeframe if timeframe != "1h" or trading_mode == "day_trading" else cfg["entry_tf"]

    # 1. Fetch dynamic symbols
    all_syms = await data_engine.fetch_symbols()
    symbols = [s["symbol"] for s in all_syms]

    if not symbols:
        return {"message": "No symbols found to generate setups for."}

    # 2. Process in batches — each symbol gets its own fresh DB session
    semaphore = asyncio.Semaphore(10)  # max 10 parallel scans at a time

    async def process_symbol(symbol):
        async with semaphore:
            local_db = SessionLocal()
            try:
                result = await generate_setup(symbol, resolved_tf, trading_mode, local_db)
                local_db.commit()
                return result
            except Exception as e:
                local_db.rollback()
                return {"symbol": symbol, "error": str(e)}
            finally:
                local_db.close()

    tasks = [process_symbol(s) for s in symbols]
    results = await asyncio.gather(*tasks)

    generated_count = sum(1 for r in results if isinstance(r, dict) and r.get("setup") is not None)

    return {
        "total_symbols": len(symbols),
        "generated_count": generated_count,
        "trading_mode": trading_mode,
        "entry_timeframe": resolved_tf,
        "mode_min_score": cfg["min_score"],
        "message": f"[{cfg['label']}] Processed {len(symbols)} symbols on {resolved_tf}. Generated {generated_count} setups (min score ≥ {cfg['min_score']}).",
    }


@router.get("/{setup_id}")
async def get_setup(setup_id: int, db: Session = Depends(get_db)):
    """Get a specific setup by ID."""
    setup = db.query(TradeSetup).filter(TradeSetup.id == setup_id).first()
    if not setup:
        return {"error": "Setup not found"}
    return {"setup": setup.to_dict()}


@router.put("/{setup_id}/status", dependencies=[Depends(require_api_key)])
async def update_setup_status(
    setup_id: int,
    update: SetupStatusUpdate,
    db: Session = Depends(get_db),
):
    """Update the status of a setup."""
    setup = db.query(TradeSetup).filter(TradeSetup.id == setup_id).first()
    if not setup:
        return {"error": "Setup not found"}
    setup.status = update.status
    db.commit()
    return {"setup": setup.to_dict()}


@router.post("/expire-stale", dependencies=[Depends(require_api_key)])
async def expire_stale_setups(
    max_age_hours: int = Query(24, description="Max age in hours before expiry"),
    db: Session = Depends(get_db),
):
    """Auto-expire ACTIVE setups older than max_age_hours (default 24h)."""
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    stale = (
        db.query(TradeSetup)
        .filter(TradeSetup.status == "ACTIVE", TradeSetup.created_at < cutoff)
        .all()
    )
    expired_count = 0
    for setup in stale:
        setup.status = "EXPIRED"  # Use EXPIRED (not INVALIDATED) for age-based expiry
        expired_count += 1
    db.commit()
    return {
        "expired_count": expired_count,
        "message": f"Expired {expired_count} stale setups older than {max_age_hours}h.",
    }


@router.delete("/clear/all", dependencies=[Depends(require_api_key)])
async def clear_all_setups(db: Session = Depends(get_db)):
    """Delete ALL setups from the database, disconnecting journals first."""
    try:
        from app.models.journal_entry import JournalEntry
        # 1. Disconnect journals first to avoid FK constraint errors
        db.query(JournalEntry).filter(JournalEntry.setup_id != None).update({"setup_id": None}, synchronize_session=False)
        # 2. Now safe to delete all setups
        count = db.query(TradeSetup).delete(synchronize_session=False)
        db.commit()
        return {"message": f"Successfully deleted all {count} setups.", "count": count}
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/clear/by-status", dependencies=[Depends(require_api_key)])
async def clear_setups_by_status(
    status: str = Query(...),
    db: Session = Depends(get_db),
):
    """Delete setups with a specific status."""
    try:
        count = db.query(TradeSetup).filter(TradeSetup.status == status).delete(synchronize_session=False)
        db.commit()
        return {"message": f"Successfully deleted {count} setups with status {status}.", "count": count}
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/clear/old", dependencies=[Depends(require_api_key)])
async def clear_old_setups_hard(
    older_than_hours: int = Query(48),
    db: Session = Depends(get_db),
):
    """Hard delete setups older than X hours."""
    try:
        cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
        count = db.query(TradeSetup).filter(TradeSetup.created_at < cutoff).delete(synchronize_session=False)
        db.commit()
        return {"message": f"Successfully deleted {count} setups older than {older_than_hours}h.", "count": count}
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/{setup_id}", dependencies=[Depends(require_api_key)])
async def delete_setup(setup_id: int, db: Session = Depends(get_db)):
    """Delete a specific setup by ID, disconnecting journal if exists."""
    try:
        from app.models.journal_entry import JournalEntry
        # 1. Disconnect journal first
        db.query(JournalEntry).filter(JournalEntry.setup_id == setup_id).update({"setup_id": None}, synchronize_session=False)
        # 2. Delete setup
        setup = db.query(TradeSetup).filter(TradeSetup.id == setup_id).first()
        if not setup:
            return {"error": "Setup not found"}
        db.delete(setup)
        db.commit()
        return {"message": f"Successfully deleted setup {setup_id}"}
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/test-telegram", dependencies=[Depends(require_api_key)])
async def test_telegram_signal(db: Session = Depends(get_db)):
    """Send a test signal to Telegram using the latest ACTIVE setup or a dummy one."""
    from app.services.telegram_bot import send_telegram_signal
    
    setup = db.query(TradeSetup).filter(TradeSetup.status == "ACTIVE").first()
    if not setup:
        # Create a dummy setup for testing
        from app.schemas.trade_setup import TradeSetupSchema
        dummy = TradeSetupSchema(
            symbol="BTCUSDT",
            direction="BUY",
            entry_low=40000,
            entry_high=40500,
            stop_loss=39000,
            take_profit_1=42000,
            take_profit_2=43000,
            take_profit_3=44000,
            risk_reward=2.5,
            setup_type="TEST_SIGNAL",
            confluence_score=8,
            timeframe="1h",
            explanation="This is a test signal to verify Telegram integration."
        )
        success = await send_telegram_signal(dummy, "1h")
    else:
        success = await send_telegram_signal(setup, setup.timeframe)
    
    return {"success": success, "message": "Test signal sent" if success else "Failed to send test signal"}
