"""
AI Signal Tracker
=================
Background task to track active AI signals and update their status (Win/Loss).
Runs every 5 minutes.
"""

import asyncio
import logging
from datetime import datetime, timezone
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import SessionLocal
from app.models.ai_signal_result import AISignalResult
from app.engines.market_data import MarketDataEngine

logger = logging.getLogger(__name__)

TRACKER_INTERVAL_MIN = 5
MAX_HOURS_ACTIVE = 24

async def _get_current_prices(symbols: set) -> dict:
    """Fetch current prices for given symbols. 
    Uses Binance miniTicker as a quick fallback if MarketDataEngine takes too long for multiple symbols.
    """
    if not symbols:
        return {}
        
    prices = {}
    try:
        sym_list = list(symbols)
        # Try Binance first for bulk prices
        sym_param = '["' + '","'.join(sym_list) + '"]'
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"https://api.binance.com/api/v3/ticker/price?symbols={sym_param}")
            if resp.status_code == 200:
                data = resp.json()
                for item in data:
                    prices[item["symbol"]] = float(item["price"])
                return prices
    except Exception as e:
        logger.warning(f"Failed to fetch bulk prices from Binance: {e}")

    # Fallback to MarketDataEngine (OKX)
    try:
        engine = MarketDataEngine()
        for sym in symbols:
            candles = await engine.get_candles(sym, "1m", 1)
            if candles and len(candles) > 0:
                prices[sym] = candles[0].close
    except Exception as e:
        logger.error(f"Failed to fetch prices from MarketDataEngine: {e}")
        
    return prices

async def _check_signals():
    """Check all ACTIVE AI signals against current prices."""
    db: Session = SessionLocal()
    try:
        # Fetch all ACTIVE signals
        active_signals = db.query(AISignalResult).filter(AISignalResult.status == "ACTIVE").all()
        if not active_signals:
            return

        symbols = {s.symbol for s in active_signals}
        prices = await _get_current_prices(symbols)

        now_utc = datetime.now(timezone.utc)
        updated_count = 0

        for sig in active_signals:
            current_price = prices.get(sig.symbol)
            if not current_price:
                continue

            # Check expiration
            created_utc = sig.created_at.replace(tzinfo=timezone.utc) if sig.created_at.tzinfo is None else sig.created_at
            hours_active = (now_utc - created_utc).total_seconds() / 3600
            
            if hours_active > MAX_HOURS_ACTIVE:
                sig.status = "EXPIRED"
                updated_count += 1
                continue

            # Evaluate Hit
            status_changed = False
            hit_price = None

            if sig.direction == "BUY":
                if current_price <= float(sig.stop_loss):
                    sig.status = "LOSS"
                    hit_price = current_price
                    status_changed = True
                elif sig.tp3 and current_price >= float(sig.tp3):
                    sig.status = "WIN_TP3"
                    hit_price = current_price
                    status_changed = True
                elif sig.tp2 and current_price >= float(sig.tp2):
                    sig.status = "WIN_TP2"
                    hit_price = current_price
                    status_changed = True
                elif current_price >= float(sig.tp1):
                    sig.status = "WIN_TP1"
                    hit_price = current_price
                    status_changed = True
                    
            elif sig.direction == "SELL":
                if current_price >= float(sig.stop_loss):
                    sig.status = "LOSS"
                    hit_price = current_price
                    status_changed = True
                elif sig.tp3 and current_price <= float(sig.tp3):
                    sig.status = "WIN_TP3"
                    hit_price = current_price
                    status_changed = True
                elif sig.tp2 and current_price <= float(sig.tp2):
                    sig.status = "WIN_TP2"
                    hit_price = current_price
                    status_changed = True
                elif current_price <= float(sig.tp1):
                    sig.status = "WIN_TP1"
                    hit_price = current_price
                    status_changed = True

            if status_changed:
                sig.hit_price = hit_price
                sig.hit_at = datetime.utcnow()
                
                # Calculate simple PnL% based on entry (using average of entry zone)
                entry_avg = (float(sig.entry_low) + float(sig.entry_high)) / 2
                if sig.direction == "BUY":
                    sig.pnl_pct = ((hit_price - entry_avg) / entry_avg) * 100
                else:
                    sig.pnl_pct = ((entry_avg - hit_price) / entry_avg) * 100
                    
                updated_count += 1

        if updated_count > 0:
            db.commit()
            logger.info(f"📊 Signal Tracker: Updated {updated_count} signals")

    except Exception as e:
        logger.error(f"Error in signal tracker: {e}")
        db.rollback()
    finally:
        db.close()

async def signal_tracker_loop():
    """Continuous loop to track signals."""
    logger.info(f"🚀 AI Signal Tracker started. Interval: {TRACKER_INTERVAL_MIN} mins")
    
    # Wait a bit before starting first cycle
    await asyncio.sleep(30)
    
    while True:
        try:
            await _check_signals()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Signal Tracker loop error: {e}")
            
        await asyncio.sleep(TRACKER_INTERVAL_MIN * 60)
