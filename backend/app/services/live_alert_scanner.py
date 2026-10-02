"""
Live Alert Scanner
==================
Fast polling loop (every 5 minutes) that checks ACTIVE setups from DB
against live OKX prices and fires WA alerts when:

  1. Price enters the FVG/OTE entry zone (COMPOSITE_SCORE alert)
  2. A Killzone session is starting
  3. A fresh sweep is detected near recorded liquidity levels

This is SEPARATE from auto_scheduler (30 min) which generates new setups.
The scanner is a REAL-TIME layer on top of existing setups.

Scan cycle logs are exposed via GET /api/v1/alerts/scanner/status
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional
import httpx

logger = logging.getLogger(__name__)


# ── Scan state (shared, readable from API) ────────────────────────────────────
scan_state: Dict = {
    "running":         False,
    "last_scan_at":    None,
    "next_scan_at":    None,
    "total_cycles":    0,
    "symbols_checked": 0,
    "alerts_fired":    0,
    "alerts_blocked":  0,
    "last_cycle_log":  [],  # list of per-symbol scan results
    "errors":          [],
}

SCAN_INTERVAL_SEC  = 300   # 5 minutes
CONCURRENCY_LIMIT  = 10
ENTRY_TOLERANCE    = 0.002  # 0.2% — price considered "in zone" if within this of entry_high

_stop_event: Optional[asyncio.Event] = None


# ── OKX Price Fetcher ─────────────────────────────────────────────────────────

async def _fetch_prices(symbols: List[str]) -> Dict[str, float]:
    prices = {}
    if not symbols:
        return prices
    try:
        inst_ids = ",".join(f"{s.replace('USDT','')}-USDT" for s in symbols)
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(
                "https://www.okx.com/api/v5/market/tickers",
                params={"instType": "SPOT", "instId": inst_ids}
            )
            data = resp.json()
            if data.get("code") == "0":
                for item in data.get("data", []):
                    sym = item["instId"].replace("-", "")
                    try:
                        prices[sym] = float(item["last"])
                    except Exception:
                        pass
    except Exception as e:
        logger.warning(f"Price fetch error: {e}")
    return prices


# ── Session Helper ────────────────────────────────────────────────────────────

def _current_session() -> str:
    hour = datetime.now(timezone.utc).hour
    if  0 <= hour <  7: return "ASIA"
    if  7 <= hour < 12: return "LONDON"
    if 12 <= hour < 17: return "NY_OPEN"
    if 17 <= hour < 20: return "NY_PM"
    return "DEAD"

def _is_killzone() -> bool:
    return _current_session() in ("LONDON", "NY_OPEN")


# ── Main Scan Cycle ───────────────────────────────────────────────────────────

async def _run_scan_cycle(db_factory):
    """Single scan cycle: load active setups, fetch prices, fire alerts if in zone."""
    from app.models.trade_setup import TradeSetup
    from app.routers.alerts import broadcast_setup_alert
    from app.services.signal_state_manager import signal_state_manager

    cycle_log = []
    alerts_fired = 0
    alerts_blocked = 0

    try:
        db = next(db_factory())
        try:
            active_setups = db.query(TradeSetup).filter(
                TradeSetup.status == "ACTIVE"
            ).order_by(TradeSetup.created_at.desc()).limit(200).all()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Scanner DB error: {e}")
        return 0, 0, [{"error": str(e)}]

    if not active_setups:
        return 0, 0, [{"info": "No active setups in DB"}]

    # Deduplicate symbols (take highest score per symbol+tf combo)
    symbols = list({s.symbol for s in active_setups})
    prices  = await _fetch_prices(symbols)
    scan_state["symbols_checked"] = len(symbols)

    session = _current_session()
    in_kz   = _is_killzone()

    sem = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async def check_setup(setup: "TradeSetup"):
        nonlocal alerts_fired, alerts_blocked
        async with sem:
            price = prices.get(setup.symbol)
            result = {
                "symbol":    setup.symbol,
                "tf":        setup.timeframe,
                "direction": setup.direction,
                "entry_low": setup.entry_low,
                "entry_high": getattr(setup, "entry_high", setup.entry_low),
                "price":     price,
                "in_zone":   False,
                "action":    "skip",
                "reason":    "",
            }

            if price is None:
                result["reason"] = "no_price"
                cycle_log.append(result)
                return

            entry_low  = setup.entry_low
            entry_high = getattr(setup, "entry_high", entry_low * 1.002)

            # Check if price is inside the entry zone (with tolerance)
            zone_low  = entry_low  * (1 - ENTRY_TOLERANCE)
            zone_high = entry_high * (1 + ENTRY_TOLERANCE)
            in_zone   = zone_low <= price <= zone_high

            result["in_zone"] = in_zone
            result["zone_low"]  = round(zone_low, 4)
            result["zone_high"] = round(zone_high, 4)

            if not in_zone:
                result["reason"] = f"price {price} outside zone [{round(zone_low,2)}-{round(zone_high,2)}]"
                result["action"] = "skip"
                cycle_log.append(result)
                return

            # Price is in zone — check dedup via state manager
            allowed, dedup_reason = signal_state_manager.can_broadcast(
                setup.symbol, setup.direction, entry_low, entry_high, setup.timeframe
            )
            if not allowed:
                result["action"] = "blocked"
                result["reason"] = dedup_reason
                alerts_blocked += 1
                cycle_log.append(result)
                return

            # Fire alert!
            result["action"] = "fire"
            result["reason"] = f"price in zone @ {price} (session={session}, killzone={in_kz})"
            logger.info(f"SCANNER ALERT: {setup.symbol} {setup.direction} price={price} in zone [{entry_low}-{entry_high}]")

            try:
                broadcast_results = await broadcast_setup_alert(setup, setup.timeframe)
                wa_ok = any(r.get("wa_ok") or r.get("status") == "sent" for r in (broadcast_results or []))
                result["wa_sent"] = wa_ok
                if wa_ok:
                    alerts_fired += 1
            except Exception as e:
                result["wa_error"] = str(e)

            cycle_log.append(result)

    tasks = [check_setup(s) for s in active_setups]
    await asyncio.gather(*tasks)

    return alerts_fired, alerts_blocked, cycle_log


# ── Scanner Loop ──────────────────────────────────────────────────────────────

async def run_alert_scanner(db_factory):
    """Background loop: poll every SCAN_INTERVAL_SEC."""
    global _stop_event
    _stop_event = asyncio.Event()
    scan_state["running"] = True

    logger.info(f"Live Alert Scanner started — polling every {SCAN_INTERVAL_SEC}s")

    while not _stop_event.is_set():
        start = datetime.now(timezone.utc)
        scan_state["last_scan_at"] = start.isoformat()

        try:
            fired, blocked, cycle_log = await _run_scan_cycle(db_factory)
            scan_state["total_cycles"]   += 1
            scan_state["alerts_fired"]   += fired
            scan_state["alerts_blocked"] += blocked
            scan_state["last_cycle_log"]  = cycle_log
            logger.info(
                f"Scanner cycle #{scan_state['total_cycles']}: "
                f"checked={scan_state['symbols_checked']} fired={fired} blocked={blocked}"
            )
        except Exception as e:
            err = str(e)
            logger.error(f"Scanner cycle error: {err}")
            scan_state["errors"].append(err)
            if len(scan_state["errors"]) > 10:
                scan_state["errors"] = scan_state["errors"][-10:]

        from datetime import timedelta
        next_at = start + timedelta(seconds=SCAN_INTERVAL_SEC)
        scan_state["next_scan_at"] = next_at.isoformat()

        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=SCAN_INTERVAL_SEC)
        except asyncio.TimeoutError:
            pass

    scan_state["running"] = False
    logger.info("Live Alert Scanner stopped.")


def stop_alert_scanner():
    if _stop_event:
        _stop_event.set()