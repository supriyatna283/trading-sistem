"""
Auto Signal Scheduler
======================
Background asyncio task that auto-generates trading setups on a schedule.
Runs immediately at startup, then repeats every INTERVAL_MINUTES.
"""

import asyncio
import logging
import json
from datetime import datetime, timezone
from typing import List

logger = logging.getLogger(__name__)


def _sanitize_details(details: dict) -> dict:
    """Convert confluence details to a JSON-safe dict (removes non-serializable objects)."""
    try:
        return json.loads(json.dumps(details, default=lambda o: str(o) if not isinstance(o, (int, float, bool, str, list, dict, type(None))) else o))
    except Exception:
        return {}

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
TIMEFRAMES = ["1h", "4h"]          # Generate for each TF
INTERVAL_MINUTES = 30              # Re-generate every 30 minutes
CONCURRENCY_LIMIT = 5              # Max concurrent symbol scans
MAX_SYMBOLS = 100                  # Max pairs to scan per cycle (top by OKX listing order)

# Scheduler state (accessible from API)
scheduler_state = {
    "running": False,
    "last_run": None,
    "next_run": None,
    "last_generated": 0,
    "total_runs": 0,
    "symbols_scanned": 0,
    "errors": [],
}

_stop_event: asyncio.Event | None = None


async def _fetch_okx_symbols() -> List[str]:
    """Fetch all live USDT-SWAP symbols from OKX dynamically."""
    import httpx
    symbols = []
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(
                "https://www.okx.com/api/v5/public/instruments",
                params={"instType": "SWAP"}
            )
            data = resp.json()
            if data.get("code") == "0" and data.get("data"):
                for inst in data["data"]:
                    inst_id = inst.get("instId", "")
                    if inst_id.endswith("-USDT-SWAP") and inst.get("state") == "live":
                        base = inst_id.split("-")[0]
                        symbols.append(f"{base}USDT")
        logger.info(f"📡 OKX: Fetched {len(symbols)} live USDT-SWAP pairs")
    except Exception as e:
        logger.warning(f"⚠️ Failed to fetch OKX symbols: {e}. Using fallback list.")
        # Fallback to essential pairs
        symbols = [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
            "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT", "DOGEUSDT",
            "LTCUSDT", "UNIUSDT", "AAVEUSDT", "ATOMUSDT", "NEARUSDT",
            "MATICUSDT", "OPUSDT", "ARBUSDT", "APTUSDT", "SUIUSDT",
            "MKRUSDT", "CRVUSDT", "LDOUSDT", "FETUSDT", "RENDERUSDT",
            "KASUSDT", "INJUSDT", "TIAUSDT", "SEIUSDT", "TAOUSDT",
        ]
    # Limit to MAX_SYMBOLS to avoid excessive load
    return symbols[:MAX_SYMBOLS]


async def _run_once(db_factory) -> int:
    """Run a full generation cycle. Returns number of setups generated."""
    from app.engines.market_data import MarketDataEngine
    from app.engines.market_structure import MarketStructureAnalyzer
    from app.engines.smart_money import SmartMoneyConceptsEngine
    from app.engines.confluence import ConfluenceEngine
    from app.engines.setup_generator import SetupGenerator
    from app.models.trade_setup import TradeSetup

    # Dynamically fetch all OKX pairs for this cycle
    watchlist = await _fetch_okx_symbols()
    scheduler_state["symbols_scanned"] = len(watchlist)
    logger.info(f"🔍 Scanning {len(watchlist)} OKX pairs × {len(TIMEFRAMES)} timeframes...")

    data_engine = MarketDataEngine()
    confluence_engine = ConfluenceEngine()
    smc_engine = SmartMoneyConceptsEngine()
    structure_analyzer = MarketStructureAnalyzer()
    setup_gen = SetupGenerator(min_confluence_score=14, min_rr=1.8)

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
                        confluence_details=_sanitize_details(confluence.details),
                        status="ACTIVE",
                        timeframe=timeframe,
                        explanation=setup_schema.explanation,
                    )
                    db.add(new_setup)
                    db.commit()
                    generated += 1
                    logger.info(f"✅ Setup: {setup_schema.direction} {symbol} [{timeframe}] | Score: {setup_schema.confluence_score}/30")

                    # 🔔 Send Telegram Alert
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
                                logger.info(f"⚡ Auto-executed {result.side} {result.quantity} {result.symbol}")
                    except Exception as e:
                        logger.warning(f"⚠️ Auto-trade error for {symbol}: {e}")

                finally:
                    db.close()

            except Exception as e:
                logger.warning(f"⚠️ Scheduler skipped {symbol}/{timeframe}: {e}")

    # Run all symbols × timeframes
    tasks = [
        process_symbol(sym, tf)
        for sym in watchlist
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
