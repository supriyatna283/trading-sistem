"""
Auto Signal Scheduler
======================
Background asyncio task that auto-generates trading setups on a schedule.
Runs immediately at startup, then repeats every INTERVAL_MINUTES.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
WATCHLIST: List[str] = [
    # ── Mega Caps ──────────────────────────────
    "BTCUSDT", "ETHUSDT",
    # ── Large Caps ─────────────────────────────
    "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
    "AVAXUSDT", "DOTUSDT", "LINKUSDT", "DOGEUSDT",
    # ── Mid Caps ───────────────────────────────
    "LTCUSDT", "UNIUSDT", "AAVEUSDT", "ATOMUSDT",
    "NEARUSDT", "FTMUSDT", "MATICUSDT", "OPUSDT",
    "ARBUSDT", "APTUSDT", "SUIUSDT", "SEIUSDT",
    # ── DeFi ───────────────────────────────────
    "MKRUSDT", "CRVUSDT", "LDOUSDT", "SNXUSDT",
    "COMPUSDT", "1INCHUSDT",
    # ── AI / Data ──────────────────────────────
    "FETUSDT", "RENDERUSDT", "WLDUSDT", "TAOUSDT",
    # ── Gaming / Metaverse ─────────────────────
    "SANDUSDT", "MANAUSDT", "AXSUSDT", "IMXUSDT",
    # ── Layer 1 Alts ───────────────────────────
    "KASUSDT", "INJUSDT", "TIAUSDT", "STXUSDT",
]

TIMEFRAMES = ["1h", "4h"]          # Generate for each TF
INTERVAL_MINUTES = 30              # Re-generate every 30 minutes
CONCURRENCY_LIMIT = 5              # Raised to 5 for 40-pair list

# Scheduler state (accessible from API)
scheduler_state = {
    "running": False,
    "last_run": None,
    "next_run": None,
    "last_generated": 0,
    "total_runs": 0,
    "errors": [],
}

_stop_event: asyncio.Event | None = None


async def _run_once(db_factory) -> int:
    """Run a full generation cycle. Returns number of setups generated."""
    from app.engines.market_data import MarketDataEngine
    from app.engines.market_structure import MarketStructureAnalyzer
    from app.engines.smart_money import SmartMoneyConceptsEngine
    from app.engines.confluence import ConfluenceEngine
    from app.engines.setup_generator import SetupGenerator
    from app.models.trade_setup import TradeSetup

    data_engine = MarketDataEngine()
    confluence_engine = ConfluenceEngine()
    smc_engine = SmartMoneyConceptsEngine()
    structure_analyzer = MarketStructureAnalyzer()
    setup_gen = SetupGenerator(min_confluence_score=12, min_rr=1.8)

    generated = 0
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async def process_symbol(symbol: str, timeframe: str):
        nonlocal generated
        async with semaphore:
            try:
                tfs = ["1d", "4h", "1h", "15m"]
                tasks = [data_engine.get_candles(symbol, tf, 200) for tf in tfs]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                candles_by_tf = {}
                for tf, df in zip(tfs, results):
                    if not isinstance(df, Exception) and df is not None and not df.empty:
                        candles_by_tf[tf] = df

                if not candles_by_tf:
                    return

                # Fix ambiguous DataFrame truth value error
                entry_df = candles_by_tf.get(timeframe)
                if entry_df is None or entry_df.empty:
                    if candles_by_tf:
                        entry_df = next(iter(candles_by_tf.values()))
                    else:
                        return
                
                if entry_df is None or entry_df.empty:
                    return

                confluence = confluence_engine.score(candles_by_tf, symbol, timeframe)
                smc = smc_engine.analyze(entry_df, symbol, timeframe)
                structure = structure_analyzer.analyze(entry_df, symbol, timeframe)

                setup_schema = setup_gen.generate(symbol, timeframe, confluence, smc, structure, entry_df)
                if setup_schema is None:
                    return

                # Save to DB
                db = next(db_factory())
                try:
                    # Expire previous ACTIVE setup for same symbol+tf
                    active_setups = db.query(TradeSetup).filter(
                        TradeSetup.symbol == symbol,
                        TradeSetup.timeframe == timeframe,
                        TradeSetup.status == "ACTIVE",
                    ).all()
                    for s in active_setups:
                        s.status = "INVALIDATED"

                    new_setup = TradeSetup(
                        symbol=symbol,
                        direction=setup_schema.direction,
                        entry_low=setup_schema.entry_low,
                        entry_high=setup_schema.entry_high,
                        stop_loss=setup_schema.stop_loss,
                        take_profit_1=setup_schema.take_profit_1,
                        take_profit_2=setup_schema.take_profit_2,
                        take_profit_3=setup_schema.take_profit_3,
                        risk_reward=setup_schema.risk_reward,
                        setup_type=setup_schema.setup_type,
                        confluence_score=setup_schema.confluence_score,
                        status="ACTIVE",
                        timeframe=timeframe,
                        explanation=setup_schema.explanation,
                    )
                    db.add(new_setup)
                    db.commit()
                    generated += 1
                    logger.info(f"✅ Auto-generated {setup_schema.direction} setup for {symbol} [{timeframe}] | Score: {setup_schema.confluence_score}/24")
                    
                    # 🔔 Send Telegram Alert for all valid setups (V5: already filtered by 12/24 min)
                    from app.services.telegram_bot import send_telegram_signal
                    asyncio.create_task(send_telegram_signal(setup_schema, timeframe))

                    # ⚡ Auto-Trade Execution (if enabled)
                    try:
                        from app.engines.trading_engine import trading_engine
                        if trading_engine.config.enabled:
                            from app.schemas.trading import OrderRequest
                            order_req = OrderRequest(
                                symbol=symbol,
                                side=setup_schema.direction,
                                price=setup_schema.entry_low,
                                stop_loss=setup_schema.stop_loss,
                                take_profit=setup_schema.take_profit_1,
                                setup_id=new_setup.id,
                            )
                            result = trading_engine.execute_order(order_req)
                            if result.success:
                                logger.info(f"⚡ Auto-executed {result.side} {result.quantity} {result.symbol} | {'DRY-RUN' if result.dry_run else 'LIVE'}")
                            else:
                                logger.warning(f"⚠️ Auto-execute skipped: {result.message}")
                    except Exception as e:
                        logger.warning(f"⚠️ Auto-trade error for {symbol}: {e}")
                        
                finally:
                    db.close()


            except Exception as e:
                logger.warning(f"⚠️ Scheduler skipped {symbol}/{timeframe}: {e}")

    # Run all symbols × timeframes
    tasks = [
        process_symbol(sym, tf)
        for sym in WATCHLIST
        for tf in TIMEFRAMES
    ]
    await asyncio.gather(*tasks)
    return generated


async def run_scheduler(db_factory):
    """
    Background loop: run once immediately at startup, then every INTERVAL_MINUTES.
    db_factory is a callable that yields a DB session (the FastAPI get_db generator).
    """
    global _stop_event
    _stop_event = asyncio.Event()
    scheduler_state["running"] = True

    logger.info(f"🤖 Auto Signal Scheduler started — watchlist: {len(WATCHLIST)} symbols, interval: {INTERVAL_MINUTES}m")

    while not _stop_event.is_set():
        run_start = datetime.now(timezone.utc)
        logger.info(f"🔄 Scheduler cycle starting at {run_start.strftime('%H:%M:%S UTC')}")

        try:
            count = await _run_once(db_factory)
            scheduler_state["last_generated"] = count
            scheduler_state["total_runs"] += 1
            scheduler_state["last_run"] = run_start.isoformat()
            next_run = run_start.timestamp() + INTERVAL_MINUTES * 60
            scheduler_state["next_run"] = datetime.fromtimestamp(next_run, tz=timezone.utc).isoformat()
            logger.info(f"✅ Cycle complete — {count} new setup(s) generated. Next run in {INTERVAL_MINUTES}m.")
        except Exception as e:
            logger.error(f"❌ Scheduler cycle error: {e}")
            scheduler_state["errors"].append(str(e))
            if len(scheduler_state["errors"]) > 10:
                scheduler_state["errors"] = scheduler_state["errors"][-10:]

        # Wait INTERVAL_MINUTES or until stop is requested
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=INTERVAL_MINUTES * 60)
        except asyncio.TimeoutError:
            pass  # Normal: time elapsed, run next cycle

    scheduler_state["running"] = False
    logger.info("🛑 Auto Signal Scheduler stopped.")


def stop_scheduler():
    """Signal the scheduler to stop gracefully."""
    if _stop_event:
        _stop_event.set()
