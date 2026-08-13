"""
Signal Watchdog Service
========================
Background async task running every 15 minutes.
Checks all ACTIVE trade setups and auto-invalidates stale/broken ones.

Invalidation Rules:
1. Price entered entry zone → TRIGGERED
2. Price closed beyond SL → INVALIDATED (structure broken)
3. 4H bias reversed against setup direction → INVALIDATED
4. Price moved >3% away from entry zone → INVALIDATED (opportunity passed)
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

WATCHDOG_INTERVAL_SECONDS = 900   # 15 minutes
ENTRY_DRIFT_MAX_PCT = 3.0         # Max % price can drift from entry zone before invalidation
BIAS_LOOKBACK_CANDLES = 100       # Candles for 4H bias re-check


async def _check_and_update_setups(db_factory) -> dict:
    """Main watchdog logic. Returns dict with counts of each action taken."""
    from app.models.trade_setup import TradeSetup
    from app.engines.market_data import MarketDataEngine
    from app.engines.market_structure import MarketStructureAnalyzer
    from app.utils.indicators import calculate_rsi

    data_engine = MarketDataEngine()
    structure_analyzer = MarketStructureAnalyzer()

    db = next(db_factory())
    results = {"triggered": 0, "invalidated": 0, "checked": 0, "errors": 0}

    try:
        active_setups = db.query(TradeSetup).filter(
            TradeSetup.status == "ACTIVE"
        ).all()

        if not active_setups:
            logger.debug("Watchdog: No ACTIVE setups to check.")
            return results

        # Group by symbol to avoid redundant API calls
        symbols = list(set(s.symbol for s in active_setups))
        price_cache: dict = {}
        bias_cache: dict = {}

        # Fetch current prices + 4H candles for all unique symbols
        async def fetch_symbol_data(symbol: str):
            try:
                df_4h = await data_engine.get_candles(symbol, "4h", BIAS_LOOKBACK_CANDLES)
                if df_4h is not None and not df_4h.empty:
                    current_price = float(df_4h.iloc[-1]["close"])
                    price_cache[symbol] = current_price
                    # Compute 4H bias
                    bias = structure_analyzer.analyze(df_4h, symbol, "4h")
                    rsi_4h = float(calculate_rsi(df_4h) or 50)
                    bias_cache[symbol] = {
                        "bias": bias.bias,
                        "rsi": rsi_4h,
                    }
            except Exception as e:
                logger.debug(f"Watchdog: Failed to fetch data for {symbol}: {e}")

        await asyncio.gather(*[fetch_symbol_data(sym) for sym in symbols])

        # Evaluate each setup
        for setup in active_setups:
            results["checked"] += 1
            sym = setup.symbol
            current_price = price_cache.get(sym)
            if current_price is None:
                continue

            entry_low = float(setup.entry_low)
            entry_high = float(setup.entry_high)
            stop_loss = float(setup.stop_loss)
            direction = setup.direction
            new_status: Optional[str] = None
            reason = ""

            # Rule 1: Price entered entry zone → TRIGGERED
            if entry_low <= current_price <= entry_high:
                new_status = "TRIGGERED"
                reason = f"Price {current_price:.4f} entered entry zone [{entry_low:.4f}-{entry_high:.4f}]"

            # Rule 2: Price closed beyond SL → INVALIDATED
            elif direction == "BUY" and current_price < stop_loss:
                new_status = "INVALIDATED"
                reason = f"Price {current_price:.4f} breached BUY SL {stop_loss:.4f}"
            elif direction == "SELL" and current_price > stop_loss:
                new_status = "INVALIDATED"
                reason = f"Price {current_price:.4f} breached SELL SL {stop_loss:.4f}"

            # Rule 3: 4H bias reversed → INVALIDATED (check if NOT in extreme RSI exception territory)
            elif sym in bias_cache:
                bias_data = bias_cache[sym]
                current_4h_bias = bias_data["bias"]
                rsi_4h = bias_data["rsi"]
                opposite_bias = "BEARISH" if direction == "BUY" else "BULLISH"
                if current_4h_bias == opposite_bias:
                    # Only invalidate if NOT in extreme RSI territory (which allows counter-trend)
                    if direction == "BUY" and rsi_4h >= 20:
                        new_status = "INVALIDATED"
                        reason = f"4H bias reversed to BEARISH, RSI4H={rsi_4h:.1f} (no oversold exception)"
                    elif direction == "SELL" and rsi_4h <= 80:
                        new_status = "INVALIDATED"
                        reason = f"4H bias reversed to BULLISH, RSI4H={rsi_4h:.1f} (no overbought exception)"

            # Rule 4: Price drifted too far from entry zone → INVALIDATED (opportunity passed)
            if new_status is None:
                if direction == "BUY":
                    # For BUY: price running up >3% above entry_high means opportunity passed
                    drift_pct = (current_price - entry_high) / entry_high * 100
                    if drift_pct > ENTRY_DRIFT_MAX_PCT:
                        new_status = "INVALIDATED"
                        reason = f"BUY price {current_price:.4f} drifted {drift_pct:.1f}% above entry zone (opportunity passed)"
                else:
                    # For SELL: price falling >3% below entry_low means opportunity passed
                    drift_pct = (entry_low - current_price) / entry_low * 100
                    if drift_pct > ENTRY_DRIFT_MAX_PCT:
                        new_status = "INVALIDATED"
                        reason = f"SELL price {current_price:.4f} drifted {drift_pct:.1f}% below entry zone (opportunity passed)"

            if new_status:
                try:
                    setup.status = new_status
                    db.commit()
                    if new_status == "TRIGGERED":
                        results["triggered"] += 1
                        logger.info(f"🎯 Watchdog TRIGGERED: {setup.symbol} {direction} | {reason}")
                    else:
                        results["invalidated"] += 1
                        logger.info(f"⚠️  Watchdog INVALIDATED: {setup.symbol} {direction} | {reason}")
                except Exception as e:
                    results["errors"] += 1
                    logger.error(f"Watchdog DB update error for {setup.symbol}: {e}")
                    db.rollback()

    except Exception as e:
        logger.error(f"Watchdog fatal error: {e}")
        results["errors"] += 1
    finally:
        db.close()

    return results


async def run_signal_watchdog(db_factory):
    """
    Background loop: runs every WATCHDOG_INTERVAL_SECONDS (15 min).
    Checks all ACTIVE setups for invalidation or trigger conditions.
    """
    logger.info(f"🐕 Signal Watchdog started — interval: {WATCHDOG_INTERVAL_SECONDS}s ({WATCHDOG_INTERVAL_SECONDS//60}m)")

    # Wait 2 minutes on startup to let auto_scheduler generate initial setups
    await asyncio.sleep(120)

    while True:
        try:
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
            logger.info(f"🔍 Watchdog checking ACTIVE setups at {ts}...")
            results = await _check_and_update_setups(db_factory)
            logger.info(
                f"🐕 Watchdog done: checked={results['checked']}, "
                f"triggered={results['triggered']}, "
                f"invalidated={results['invalidated']}, "
                f"errors={results['errors']}"
            )
        except Exception as e:
            logger.error(f"Watchdog loop error: {e}")

        await asyncio.sleep(WATCHDOG_INTERVAL_SECONDS)
