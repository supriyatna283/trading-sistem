"""Scanner API endpoints — V5 uses real Binance data by default."""

from fastapi import APIRouter, Query, HTTPException
from app.engines.scanner import MarketScanner
import time
from datetime import datetime, timezone

router = APIRouter(prefix="/api/v1/scanner", tags=["Market Scanner"])

scanner = MarketScanner()

# FIX #2: Rate limiter extended to 300s (5 min) — scanner scans 29 pairs × 3 TF each
# Running more frequently is pointless and bogs down HF Spaces.
_last_scan_time = 0.0
_SCAN_COOLDOWN = 300  # 5 minutes
_last_results = []
_last_scan_at: str = ""


@router.get("")
async def get_scanner_results():
    """Get the latest scanner results. Returns cached data if scan ran within last 5 min."""
    global _last_scan_time, _last_results, _last_scan_at
    now = time.time()

    # Return cache if fresh enough
    if now - _last_scan_time < _SCAN_COOLDOWN and _last_results:
        return {"results": _last_results, "cached": True, "last_scan_at": _last_scan_at}

    try:
        results = await scanner.scan()
        _last_results = results
        _last_scan_time = now
        _last_scan_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {"results": results, "cached": False, "last_scan_at": _last_scan_at}
    except Exception as e:
        if _last_results:
            return {"results": _last_results, "cached": True, "last_scan_at": _last_scan_at}
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run")
async def run_scanner(
    symbols: list[str] = None,
):
    """Trigger a manual scan of specific symbols using real data."""
    global _last_scan_time, _last_results, _last_scan_at
    now = time.time()
    if now - _last_scan_time < 30:  # Hard minimum 30s between manual triggers
        remaining = int(30 - (now - _last_scan_time))
        raise HTTPException(status_code=429, detail=f"Rate limited. Try again in {remaining}s.")

    results = await scanner.scan(symbols=symbols)

    if not symbols:
        _last_results = results
        _last_scan_time = now
        _last_scan_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {"results": results, "cached": False, "last_scan_at": _last_scan_at}
