"""Scanner API endpoints — V5 uses real Binance data by default."""

import asyncio
from fastapi import APIRouter, Depends, Query, HTTPException
from app.engines.scanner import MarketScanner
from app.security import require_api_key, rate_limit
import time
from datetime import datetime, timezone

router = APIRouter(prefix="/api/v1/scanner", tags=["Market Scanner"])

scanner = MarketScanner()

_last_scan_time = {}
_SCAN_COOLDOWN = 300  # 5 minutes
_last_results = {}
_last_scan_at = {}
_scan_locks: dict[str, asyncio.Lock] = {}
_bg_refreshing: set[str] = set()


async def _refresh_scan_cache(entry_tf: str) -> list:
    lock = _scan_locks.setdefault(entry_tf, asyncio.Lock())
    async with lock:
        now = time.time()
        if now - _last_scan_time.get(entry_tf, 0.0) < 30 and _last_results.get(entry_tf):
            return _last_results[entry_tf]
        results = await scanner.scan(entry_tf=entry_tf)
        _last_results[entry_tf] = results
        _last_scan_time[entry_tf] = time.time()
        _last_scan_at[entry_tf] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return results


async def _bg_refresh_wrapper(entry_tf: str):
    try:
        await _refresh_scan_cache(entry_tf)
    finally:
        _bg_refreshing.discard(entry_tf)


@router.get("")
async def get_scanner_results(entry_tf: str = "1h"):
    """Get the latest scanner results with Stale-While-Revalidate and single-flight deduplication."""
    now = time.time()
    last_time = _last_scan_time.get(entry_tf, 0.0)
    last_res = _last_results.get(entry_tf, [])
    last_at = _last_scan_at.get(entry_tf, "")

    # 1. Fresh cache hit -> instant response
    if now - last_time < _SCAN_COOLDOWN and last_res:
        return {"results": last_res, "cached": True, "last_scan_at": last_at, "entry_tf": entry_tf}

    # 2. Stale-While-Revalidate: if we have prior results, return immediately and refresh in background
    if last_res:
        if entry_tf not in _bg_refreshing:
            _bg_refreshing.add(entry_tf)
            asyncio.create_task(_bg_refresh_wrapper(entry_tf))
        return {"results": last_res, "cached": True, "stale_revalidating": True, "last_scan_at": last_at, "entry_tf": entry_tf}

    # 3. Cold cache: deduplicate concurrent initial scans via _refresh_scan_cache lock
    try:
        results = await _refresh_scan_cache(entry_tf)
        return {"results": results, "cached": False, "last_scan_at": _last_scan_at.get(entry_tf, ""), "entry_tf": entry_tf}
    except Exception as e:
        if last_res:
            return {"results": last_res, "cached": True, "last_scan_at": last_at, "entry_tf": entry_tf}
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run", dependencies=[Depends(require_api_key), Depends(rate_limit("scanner_run", max_calls=4, window_sec=60))])
async def run_scanner(
    symbols: list[str] = None,
    entry_tf: str = "1h",
):
    """Trigger a manual scan of specific symbols using real data."""
    global _last_scan_time, _last_results, _last_scan_at
    now = time.time()
    last_time = _last_scan_time.get(entry_tf, 0.0)
    
    if now - last_time < 30:  # Hard minimum 30s between manual triggers
        remaining = int(30 - (now - last_time))
        raise HTTPException(status_code=429, detail=f"Rate limited. Try again in {remaining}s.")

    results = await scanner.scan(symbols=symbols, entry_tf=entry_tf)

    if not symbols:
        _last_results[entry_tf] = results
        _last_scan_time[entry_tf] = now
        _last_scan_at[entry_tf] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {"results": results, "cached": False, "last_scan_at": _last_scan_at.get(entry_tf, ""), "entry_tf": entry_tf}
