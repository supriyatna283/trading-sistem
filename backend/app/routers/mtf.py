"""MTF Confirmation API Router"""

from fastapi import APIRouter, Query
import asyncio
from app.engines.mtf_confirmation import MTFConfirmationEngine
from app.engines.market_data import MarketDataEngine

router = APIRouter(prefix="/api/v1/analysis/mtf", tags=["Multi-Timeframe"])

mtf_engine = MTFConfirmationEngine()
data_engine = MarketDataEngine()

TIMEFRAMES = ["1d", "4h", "1h", "15m", "5m"]


@router.get("/{symbol}")
async def get_mtf_analysis(
    symbol: str,
    limit: int = Query(200, ge=50, le=500),
):
    """Full multi-timeframe analysis for a symbol across 1D/4H/1H/15m/5m."""
    tasks = [data_engine.get_candles(symbol.upper(), tf, limit) for tf in TIMEFRAMES]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    candles_by_tf = {}
    for tf, result in zip(TIMEFRAMES, results):
        if isinstance(result, Exception) or result is None:
            import pandas as pd
            candles_by_tf[tf] = pd.DataFrame()
        else:
            candles_by_tf[tf] = result

    analysis = mtf_engine.analyze(candles_by_tf, symbol.upper())
    return {"mtf": analysis}


@router.get("/batch/all")
async def get_mtf_batch(
    symbols: str = Query("BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT"),
):
    """Run MTF analysis for multiple symbols (comma-separated)."""
    symbol_list = [s.strip().upper() for s in symbols.split(",")][:10]

    async def analyze_symbol(sym: str):
        tasks = [data_engine.get_candles(sym, tf, 200) for tf in TIMEFRAMES]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        candles_by_tf = {}
        for tf, result in zip(TIMEFRAMES, results):
            if isinstance(result, Exception) or result is None:
                import pandas as pd
                candles_by_tf[tf] = pd.DataFrame()
            else:
                candles_by_tf[tf] = result
        return mtf_engine.analyze(candles_by_tf, sym)

    batch_results = await asyncio.gather(*[analyze_symbol(s) for s in symbol_list])
    return {"results": list(batch_results)}
