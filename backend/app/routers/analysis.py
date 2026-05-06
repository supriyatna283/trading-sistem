"""Analysis API endpoints — Market Structure + Smart Money Concepts + Confluence V3."""

from fastapi import APIRouter, Query
import asyncio
from app.engines.market_data import MarketDataEngine
from app.engines.market_structure import MarketStructureAnalyzer
from app.engines.smart_money import SmartMoneyConceptsEngine
from app.engines.confluence import ConfluenceEngine
from app.engines.mtf_confirmation import MTFConfirmationEngine
from app.engines.sentiment import SentimentEngine
from app.engines.news_calendar import NewsCalendarEngine

router = APIRouter(prefix="/api/v1/analysis", tags=["Analysis"])

data_engine = MarketDataEngine()
structure_analyzer = MarketStructureAnalyzer()
smc_engine = SmartMoneyConceptsEngine()
confluence_engine = ConfluenceEngine()
mtf_engine = MTFConfirmationEngine()
sentiment_engine = SentimentEngine()
news_engine = NewsCalendarEngine()


@router.get("/structure/{symbol}")
async def analyze_structure(
    symbol: str,
    timeframe: str = Query("1h", regex="^(1m|5m|15m|1h|4h|1d)$"),
    demo: bool = Query(False),
):
    """Get market structure analysis (HH/HL/LH/LL/BOS/CHOCH)."""
    base_prices = {
        "BTCUSDT": 67000, "ETHUSDT": 3400, "BNBUSDT": 580,
        "SOLUSDT": 145, "XRPUSDT": 0.62,
    }
    if demo:
        df = MarketDataEngine.generate_sample_data(
            symbol=symbol.upper(), timeframe=timeframe,
            base_price=base_prices.get(symbol.upper(), 100),
        )
    else:
        df = await data_engine.get_candles(symbol, timeframe)

    result = structure_analyzer.analyze(df, symbol.upper(), timeframe)
    return result.model_dump()


@router.get("/smc/{symbol}")
async def analyze_smc(
    symbol: str,
    timeframe: str = Query("1h", regex="^(1m|5m|15m|1h|4h|1d)$"),
    demo: bool = Query(False),
):
    """Get Smart Money Concepts analysis (unmitigated OB, unfilled FVG, Liquidity)."""
    base_prices = {
        "BTCUSDT": 67000, "ETHUSDT": 3400, "BNBUSDT": 580,
        "SOLUSDT": 145, "XRPUSDT": 0.62,
    }
    if demo:
        df = MarketDataEngine.generate_sample_data(
            symbol=symbol.upper(), timeframe=timeframe,
            base_price=base_prices.get(symbol.upper(), 100),
        )
    else:
        df = await data_engine.get_candles(symbol, timeframe)

    result = smc_engine.analyze(df, symbol.upper(), timeframe)
    return result.model_dump()


@router.get("/confluence/{symbol}")
async def analyze_confluence(
    symbol: str,
    entry_tf: str = Query("1h"),
    demo: bool = Query(False),
):
    """
    Get multi-timeframe confluence analysis with V3 14-point scoring.
    Includes sentiment, news, and MTF confirmation.
    """
    base_prices = {
        "BTCUSDT": 67000, "ETHUSDT": 3400, "BNBUSDT": 580,
        "SOLUSDT": 145, "XRPUSDT": 0.62,
    }
    base = base_prices.get(symbol.upper(), 100)
    candles_by_tf = {}

    if demo:
        for tf in ["1d", "4h", "1h", "15m"]:
            df = MarketDataEngine.generate_sample_data(
                symbol=symbol.upper(), timeframe=tf, base_price=base,
            )
            candles_by_tf[tf] = df
        # No macro data in demo mode
        sentiment_data = None
        news_events = None
    else:
        # Fetch candles + macro context in parallel
        tfs = ["1d", "4h", "1h", "15m"]
        candle_tasks = [data_engine.get_candles(symbol, tf) for tf in tfs]
        sentiment_task = sentiment_engine.get_full_sentiment()
        news_task = news_engine.get_events()

        all_results = await asyncio.gather(
            *candle_tasks, sentiment_task, news_task,
            return_exceptions=True,
        )

        for i, df in enumerate(all_results[:len(tfs)]):
            if not isinstance(df, Exception) and not df.empty:
                candles_by_tf[tfs[i]] = df

        sentiment_data = all_results[len(tfs)] if not isinstance(all_results[len(tfs)], Exception) else None
        news_events = all_results[len(tfs) + 1] if not isinstance(all_results[len(tfs) + 1], Exception) else None

    # MTF Confirmation
    mtf_result = mtf_engine.analyze(candles_by_tf, symbol.upper())

    result = confluence_engine.score(
        candles_by_tf, symbol.upper(), entry_tf,
        sentiment_data=sentiment_data,
        news_events=news_events,
        mtf_result=mtf_result,
    )
    return {
        "confluence": result.model_dump(),
        "mtf": mtf_result,
    }
