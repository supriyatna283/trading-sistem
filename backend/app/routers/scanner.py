"""Scanner API endpoints — V2 uses real Binance data by default."""

from fastapi import APIRouter, Query, HTTPException
from app.engines.scanner import MarketScanner
import time

router = APIRouter(prefix="/api/v1/scanner", tags=["Market Scanner"])

scanner = MarketScanner()

# Simple rate limiter and cache
_last_scan_time = 0.0
_SCAN_COOLDOWN = 30  # seconds
_last_results = []


@router.get("")
async def get_scanner_results():
    """Get the latest scanner results for all watchlist symbols using real data."""
    global _last_scan_time, _last_results
    now = time.time()
    
    # If within cooldown and we have cached results, return them instead of throwing 429
    if now - _last_scan_time < _SCAN_COOLDOWN and _last_results:
        return {"results": _last_results}
        
    try:
        results = await scanner.scan()
        _last_results = results
        _last_scan_time = now
        return {"results": results}
    except Exception as e:
        # Fallback to cache if possible
        if _last_results:
            return {"results": _last_results}
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run")
async def run_scanner(
    symbols: list[str] = None,
):
    """Trigger a manual scan of specific symbols using real data."""
    global _last_scan_time, _last_results
    now = time.time()
    if now - _last_scan_time < _SCAN_COOLDOWN:
        remaining = int(_SCAN_COOLDOWN - (now - _last_scan_time))
        raise HTTPException(status_code=429, detail=f"Rate limited. Try again in {remaining}s.")
    
    results = await scanner.scan(symbols=symbols)
    
    # Update cache if it was a full scan
    if not symbols:
        _last_results = results
        _last_scan_time = now
        
    return {"results": results}
