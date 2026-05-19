"""
Trading Intelligence Platform — FastAPI Application
=====================================================
Main entry point. Mounts all routers, configures CORS, and initializes DB.
Auto Signal Scheduler starts on startup and generates signals every 30 minutes.
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import get_settings
from app.database import init_db, get_db
from app.migrate_db import migrate
from app.routers import (
    market_data,
    analysis,
    setups,
    risk,
    scanner,
    journal,
    alerts,
    ws,
    mtf,
    calendar,
    strategy,
    sentiment,
    backtest,
    market_intel,
    trading,
    portfolio,
    order_flow,
)
from app.services.auto_scheduler import run_scheduler, stop_scheduler, scheduler_state
from app.security import require_api_key
from fastapi import Depends

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

_scheduler_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown logic."""
    global _scheduler_task
    logger.info("🚀 Trading Intelligence Platform starting up...")

    # 1. Initialize Database
    try:
        from sqlalchemy import text
        from app.database import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        init_db()
        migrate()
        logger.info("✅ Database tables created/verified")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        logger.info("⚠️ Continuing without database connectivity...")

    cfg = get_settings()
    if cfg.APP_ENV == "production" and not cfg.API_KEY:
        logger.warning("⚠️ API_KEY is not set — mutating endpoints return 503 in production")
    elif not cfg.API_KEY:
        logger.warning("⚠️ API_KEY not set — write endpoints are open (development only)")

    # 2. Start Auto Signal Scheduler as background asyncio task
    try:
        _scheduler_task = asyncio.create_task(run_scheduler(get_db))
        logger.info("🤖 Auto Signal Scheduler launched (every 30 minutes)")
    except Exception as e:
        logger.error(f"❌ Scheduler failed to start: {e}")

    # 3. Start WebSocket Proxy — Skip Binance (blocked 451 on HuggingFace), use OKX
    logger.info("⏭️ Binance WebSocket skipped (blocked on cloud). Using OKX data source.")

    # 4. Start Smart Tape WebSocket Manager (OKX trades stream)
    try:
        from app.services.tape_ws_manager import smart_tape_manager
        await smart_tape_manager.start()
        logger.info("✅ Smart Tape WebSocket Manager started (OKX)")
    except Exception as e:
        logger.error(f"❌ Smart Tape failed to start: {e}")

    yield

    # Shutdown
    logger.info("👋 Shutting down...")
    stop_scheduler()
    if _scheduler_task:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
            
    try:
        from app.services.binance_ws_client import binance_proxy
        await binance_proxy.stop()
    except Exception:
        pass

    try:
        from app.services.tape_ws_manager import smart_tape_manager
        await smart_tape_manager.stop()
    except Exception:
        pass


settings = get_settings()

app = FastAPI(
    title="Trading Intelligence Platform",
    description=(
        "Professional trading decision support system. "
        "Provides market analysis, Smart Money Concepts detection, "
        "multi-timeframe confluence scoring, and risk management."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — explicit origins only (no wildcard with credentials)
_cors_origins = list({
    settings.FRONTEND_URL.rstrip("/"),
    "http://localhost:3000",
    "http://127.0.0.1:3000",
})
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(market_data.router)
app.include_router(analysis.router)
app.include_router(setups.router)
app.include_router(risk.router)
app.include_router(scanner.router)
app.include_router(journal.router)
app.include_router(alerts.router)
app.include_router(ws.router)
app.include_router(mtf.router)
app.include_router(calendar.router)
app.include_router(strategy.router)
app.include_router(sentiment.router)
app.include_router(backtest.router)
app.include_router(market_intel.router)
app.include_router(trading.router)
app.include_router(portfolio.router)
app.include_router(order_flow.router)


@app.get("/")
async def root():
    return {
        "name": "Trading Intelligence Platform",
        "version": "2.0.0",
        "status": "operational",
        "docs": "/docs",
        "auto_scheduler": scheduler_state,
        "endpoints": {
            "market_data": "/api/v1/market",
            "analysis": "/api/v1/analysis",
            "setups": "/api/v1/setups",
            "risk": "/api/v1/risk",
            "scanner": "/api/v1/scanner",
            "journal": "/api/v1/journal",
            "alerts": "/api/v1/alerts",
            "websocket": "/ws/market/{symbol}",
            "scheduler": "/scheduler/status",
            "sentiment": "/api/v1/sentiment",
            "market_intel": "/api/v1/market-intel",
        },
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "scheduler": scheduler_state}


@app.get("/scheduler/status")
async def scheduler_status():
    """Current state of the auto signal scheduler."""
    return {"scheduler": scheduler_state}


@app.post("/scheduler/trigger", dependencies=[Depends(require_api_key)])
async def trigger_scheduler():
    """Manually trigger an immediate scheduler run (for testing)."""
    from app.services.auto_scheduler import _run_once
    try:
        count = await _run_once(get_db)
        return {"message": f"Manual run complete: {count} setup(s) generated", "generated": count}
    except Exception as e:
        return {"error": str(e)}
