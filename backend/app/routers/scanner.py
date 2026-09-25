"""Scanner API endpoints — V5 uses real Binance data by default."""

from fastapi import APIRouter, Query, HTTPException
from app.engines.scanner import MarketScanner
import time
from datetime import datetime, timezone

router = APIRouter(prefix="/api/v1/scanner", tags=["Market Scanner"])

scanner = MarketScanner()

# FIX #2: Rate limiter extended to 300s (5 min) — scanner scans 29 pairs × 3 TF each
# Running more frequently is pointless and bogs down HF Spaces.
_last_scan_time = {}
_SCAN_COOLDOWN = 300  # 5 minutes
_last_results = {}
_last_scan_at = {}


@router.get("")
async def get_scanner_results(entry_tf: str = "1h"):
    """Get the latest scanner results. Returns cached data if scan ran within last 5 min."""
    global _last_scan_time, _last_results, _last_scan_at
    now = time.time()
    
    last_time = _last_scan_time.get(entry_tf, 0.0)
    last_res = _last_results.get(entry_tf, [])
    last_at = _last_scan_at.get(entry_tf, "")

    # Return cache if fresh enough
    if now - last_time < _SCAN_COOLDOWN and last_res:
        return {"results": last_res, "cached": True, "last_scan_at": last_at, "entry_tf": entry_tf}

    try:
        results = await scanner.scan(entry_tf=entry_tf)
        _last_results[entry_tf] = results
        _last_scan_time[entry_tf] = now
        _last_scan_at[entry_tf] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {"results": results, "cached": False, "last_scan_at": _last_scan_at[entry_tf], "entry_tf": entry_tf}
    except Exception as e:
        if last_res:
            return {"results": last_res, "cached": True, "last_scan_at": last_at, "entry_tf": entry_tf}
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run")
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
