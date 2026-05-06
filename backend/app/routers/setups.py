"""Trading setups API endpoints — V3 uses REAL Binance data + full macro integration."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.database import get_db
from app.models.trade_setup import TradeSetup
from app.engines.market_data import MarketDataEngine
from app.engines.market_structure import MarketStructureAnalyzer
from app.engines.smart_money import SmartMoneyConceptsEngine
from app.engines.confluence import ConfluenceEngine
from app.engines.setup_generator import SetupGenerator
from app.engines.mtf_confirmation import MTFConfirmationEngine
from app.engines.sentiment import SentimentEngine
from app.engines.news_calendar import NewsCalendarEngine
from app.schemas.trade_setup import SetupStatusUpdate

router = APIRouter(prefix="/api/v1/setups", tags=["Trading Setups"])

setup_gen = SetupGenerator(min_confluence_score=5, min_rr=1.5)
confluence_engine = ConfluenceEngine()
smc_engine = SmartMoneyConceptsEngine()
structure_analyzer = MarketStructureAnalyzer()
data_engine = MarketDataEngine()
mtf_engine = MTFConfirmationEngine()
sentiment_engine = SentimentEngine()
news_engine = NewsCalendarEngine()


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
    db: Session = Depends(get_db),
):
    """
    Generate a trade setup using REAL market data from Binance.
    V3 Pipeline:
    1. Fetch real OHLCV candles across multiple timeframes (parallel)
    2. Fetch macro context: sentiment (F&G, funding, OI) + news calendar
    3. Run MTF Confirmation analysis
    4. Analyze Market Structure (HH/HL/LH/LL, BOS, CHOCH)
    5. Detect Smart Money Concepts (unmitigated OB, unfilled FVG, Liquidity)
    6. Score Multi-TF Confluence (18-point system with macro filters)
    7. Generate setup ONLY if score >= 5/18 and R:R >= 1.5
    """
    import asyncio
    candles_by_tf = {}

    # Fetch candles + macro context in parallel
    tfs = ["1d", "4h", "1h", "15m"]
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

    # Run confluence analysis
    entry_df = candles_by_tf.get(timeframe, candles_by_tf.get("1h"))
    if entry_df is None or entry_df.empty:
        return {
            "setup": None,
            "confluence": None,
            "message": f"No candle data available for {symbol} on {timeframe}",
        }

    # MTF Confirmation
    mtf_result = mtf_engine.analyze(candles_by_tf, symbol.upper())

    structure = structure_analyzer.analyze(entry_df, symbol.upper(), timeframe)
    smc = smc_engine.analyze(entry_df, symbol.upper(), timeframe)
    confluence = confluence_engine.score(
        candles_by_tf, symbol.upper(), timeframe,
        sentiment_data=sentiment_data,
        news_events=news_events,
        mtf_result=mtf_result,
    )

    # Generate setup (V3 — 8 quality gates)
    setup = setup_gen.generate(
        symbol.upper(), timeframe, confluence, smc, structure, entry_df,
        mtf_result=mtf_result,
        news_events=news_events,
        sentiment_data=sentiment_data,
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

        # Persist to DB
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
            status=setup.status,
            timeframe=setup.timeframe,
            explanation=setup.explanation,
        )
        db.add(db_setup)
        db.commit()
        db.refresh(db_setup)
        return {
            "setup": db_setup.to_dict(),
            "confluence": confluence.model_dump(),
            "message": f"✅ High-quality {setup.direction} setup generated for {symbol} (Score: {confluence.total_score}/{confluence.max_score}, R:R 1:{setup.risk_reward})",
        }

    return {
        "setup": None,
        "confluence": confluence.model_dump(),
        "message": f"No setup generated for {symbol} — Score: {confluence.total_score}/{confluence.max_score} (min required: 5/18).",
    }


@router.post("/generate/all")
async def generate_all_setups(
    timeframe: str = Query("1h"),
    db: Session = Depends(get_db),
):
    """
    Trigger signal generation for ALL dynamic symbols from Binance.
    Uses concurrency limit to avoid overwhelming system resources.
    """
    import asyncio
    
    # 1. Fetch dynamic symbols
    all_syms = await data_engine.fetch_symbols()
    symbols = [s["symbol"] for s in all_syms]
    
    if not symbols:
        return {"message": "No symbols found to generate setups for."}

    # 2. Process in batches to limit concurrency
    semaphore = asyncio.Semaphore(10) # 10 parallel scans at a time
    
    async def process_symbol(symbol):
        async with semaphore:
            try:
                # We reuse the logic but without the full HTTP overhead of calling ourselves
                # For simplicity in this endpoint, we just call the generate_setup function logic
                # or better, just leave it as is and let the frontend call it if we want progress.
                # But a POST /generate/all is what the user probably wants for "one click".
                return await generate_setup(symbol, timeframe, db)
            except Exception as e:
                return {"symbol": symbol, "error": str(e)}

    tasks = [process_symbol(s) for s in symbols]
    results = await asyncio.gather(*tasks)
    
    generated_count = sum(1 for r in results if r.get("setup") is not None)
    
    return {
        "total_symbols": len(symbols),
        "generated_count": generated_count,
        "message": f"Processed {len(symbols)} symbols. Generated {generated_count} new setups.",
    }


@router.get("/{setup_id}")
async def get_setup(setup_id: int, db: Session = Depends(get_db)):
    """Get a specific setup by ID."""
    setup = db.query(TradeSetup).filter(TradeSetup.id == setup_id).first()
    if not setup:
        return {"error": "Setup not found"}
    return {"setup": setup.to_dict()}


@router.put("/{setup_id}/status")
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


@router.post("/expire-stale")
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
        setup.status = "INVALIDATED"
        expired_count += 1
    db.commit()
    return {
        "expired_count": expired_count,
        "message": f"Expired {expired_count} stale setups older than {max_age_hours}h.",
    }
