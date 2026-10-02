"""
Live Alert Scanner (DB-Free Edition)
=====================================
Fast polling loop (every 5 minutes) that checks setups from an
IN-MEMORY CACHE (fed by auto_scheduler) against live OKX prices.

NO DATABASE DEPENDENCY — works even when DB is unreachable.

Flow:
  auto_scheduler generates setup → push to _setup_cache
  live_alert_scanner reads _setup_cache → fetch OKX price
  if price in entry zone → broadcast WA via Vercel proxy
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
import httpx

logger = logging.getLogger(__name__)

# ── Scan state ────────────────────────────────────────────────────────────────
scan_state: Dict = {
    "running":         False,
    "last_scan_at":    None,
    "next_scan_at":    None,
    "total_cycles":    0,
    "symbols_checked": 0,
    "alerts_fired":    0,
    "alerts_blocked":  0,
    "cache_size":      0,
    "last_cycle_log":  [],
    "errors":          [],
}

SCAN_INTERVAL_SEC = 300   # 5 minutes
CONCURRENCY_LIMIT = 10
ENTRY_TOLERANCE   = 0.002  # 0.2%
CACHE_TTL_HOURS   = 48     # Remove setups older than this

_stop_event: Optional[asyncio.Event] = None


# ── In-Memory Setup Cache ─────────────────────────────────────────────────────

@dataclass
class CachedSetup:
    symbol:        str
    direction:     str
    entry_low:     float
    entry_high:    float
    stop_loss:     float
    take_profit_1: float
    take_profit_2: Optional[float]
    risk_reward:   float
    timeframe:     str
    confluence_score: float
    confluence_details: dict = field(default_factory=dict)
    created_at:    datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def age_hours(self) -> float:
        return (datetime.now(timezone.utc) - self.created_at).total_seconds() / 3600

    def is_expired(self) -> bool:
        return self.age_hours() > CACHE_TTL_HOURS


# Global setup cache — written by auto_scheduler, read by scanner
_setup_cache: List[CachedSetup] = []
_cache_lock = asyncio.Lock()


def push_setup_to_cache(setup_schema, timeframe: str):
    """Called by auto_scheduler after a setup is generated. Thread-safe-ish."""
    try:
        entry_high = getattr(setup_schema, "entry_high", setup_schema.entry_low * 1.002)
        cached = CachedSetup(
            symbol=setup_schema.symbol,
            direction=setup_schema.direction,
            entry_low=setup_schema.entry_low,
            entry_high=entry_high,
            stop_loss=setup_schema.stop_loss,
            take_profit_1=setup_schema.take_profit_1,
            take_profit_2=setup_schema.take_profit_2,
            risk_reward=setup_schema.risk_reward,
            timeframe=timeframe,
            confluence_score=setup_schema.confluence_score,
            confluence_details=getattr(setup_schema, "confluence_details", {}),
        )
        # Remove old entry for same symbol+tf+direction (replace with newer)
        global _setup_cache
        _setup_cache = [
            s for s in _setup_cache
            if not (s.symbol == cached.symbol and s.timeframe == timeframe and s.direction == cached.direction)
        ]
        _setup_cache.append(cached)
        scan_state["cache_size"] = len(_setup_cache)
        logger.debug(f"Cache push: {cached.symbol} {cached.direction} [{timeframe}] — cache size={len(_setup_cache)}")
    except Exception as e:
        logger.warning(f"Failed to push setup to cache: {e}")


def get_cache_snapshot() -> List[CachedSetup]:
    """Return non-expired setups."""
    global _setup_cache
    _setup_cache = [s for s in _setup_cache if not s.is_expired()]
    return list(_setup_cache)


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


# ── Main Scan Cycle (No DB) ───────────────────────────────────────────────────

async def _run_scan_cycle(db_factory=None):
    """
    Scan all cached setups against live OKX prices.
    db_factory is accepted for API compatibility but NOT USED.
    """
    from app.routers.alerts import broadcast_setup_alert
    from app.services.signal_state_manager import signal_state_manager

    cycle_log = []
    alerts_fired   = 0
    alerts_blocked = 0

    setups = get_cache_snapshot()
    scan_state["cache_size"] = len(setups)

    if not setups:
        return 0, 0, [{"info": f"Cache empty — waiting for auto_scheduler to generate setups (runs every 5 min)"}]

    symbols = list({s.symbol for s in setups})
    prices  = await _fetch_prices(symbols)
    scan_state["symbols_checked"] = len(symbols)

    session = _current_session()
    sem = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async def check_setup(setup: CachedSetup):
        nonlocal alerts_fired, alerts_blocked
        async with sem:
            price = prices.get(setup.symbol)
            result = {
                "symbol":    setup.symbol,
                "tf":        setup.timeframe,
                "direction": setup.direction,
                "entry_low": setup.entry_low,
                "entry_high": setup.entry_high,
                "price":     price,
                "in_zone":   False,
                "action":    "skip",
                "reason":    "",
                "age_h":     round(setup.age_hours(), 1),
                "session":   session,
            }

            if price is None:
                result["reason"] = "no_okx_price"
                cycle_log.append(result)
                return

            zone_low  = setup.entry_low  * (1 - ENTRY_TOLERANCE)
            zone_high = setup.entry_high * (1 + ENTRY_TOLERANCE)
            in_zone   = zone_low <= price <= zone_high

            result["in_zone"]   = in_zone
            result["zone_low"]  = round(zone_low,  4)
            result["zone_high"] = round(zone_high, 4)

            if not in_zone:
                result["reason"] = f"price {price} outside [{round(zone_low,2)}-{round(zone_high,2)}]"
                cycle_log.append(result)
                return

            # Price is IN entry zone — check dedup
            allowed, dedup_reason = signal_state_manager.can_broadcast(
                setup.symbol, setup.direction,
                setup.entry_low, setup.entry_high, setup.timeframe
            )
            if not allowed:
                result["action"] = "blocked"
                result["reason"] = dedup_reason
                alerts_blocked += 1
                cycle_log.append(result)
                return

            # Fire!
            result["action"] = "fire"
            result["reason"] = f"IN ZONE @ {price} (session={session})"
            logger.info(f"🚨 SCANNER: {setup.symbol} {setup.direction} price={price} in zone [{setup.entry_low}-{setup.entry_high}]")

            try:
                broadcast_results = await broadcast_setup_alert(setup, setup.timeframe)
                wa_ok = any(
                    r.get("wa_ok") or r.get("status") == "sent"
                    for r in (broadcast_results or [])
                )
                result["wa_sent"] = wa_ok
                result["broadcast"] = broadcast_results
                if wa_ok:
                    alerts_fired += 1
            except Exception as e:
                result["wa_error"] = str(e)

            cycle_log.append(result)

    tasks = [check_setup(s) for s in setups]
    await asyncio.gather(*tasks)

    # Sort: in-zone first
    cycle_log.sort(key=lambda x: (not x.get("in_zone", False), x.get("symbol", "")))

    return alerts_fired, alerts_blocked, cycle_log


# ── Scanner Loop ──────────────────────────────────────────────────────────────

async def run_alert_scanner(db_factory=None):
    global _stop_event
    _stop_event = asyncio.Event()
    scan_state["running"] = True

    logger.info(f"Live Alert Scanner started (DB-Free) — polling every {SCAN_INTERVAL_SEC}s")

    while not _stop_event.is_set():
        start = datetime.now(timezone.utc)
        scan_state["last_scan_at"] = start.isoformat()

        try:
            fired, blocked, cycle_log = await _run_scan_cycle()
            scan_state["total_cycles"]   += 1
            scan_state["alerts_fired"]   += fired
            scan_state["alerts_blocked"] += blocked
            scan_state["last_cycle_log"]  = cycle_log
            logger.info(
                f"Scanner #{scan_state['total_cycles']}: "
                f"cache={scan_state['cache_size']} checked={scan_state['symbols_checked']} "
                f"fired={fired} blocked={blocked}"
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