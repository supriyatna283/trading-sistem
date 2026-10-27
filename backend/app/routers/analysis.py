"""Analysis API endpoints — Market Structure + Smart Money Concepts + Confluence V3."""

from fastapi import APIRouter, Query
import asyncio
from app.engines.market_data import MarketDataEngine, TIMEFRAME_REGEX, SOURCE_SYNTHETIC
from app.engines.market_structure import MarketStructureAnalyzer
from app.engines.smart_money import SmartMoneyConceptsEngine
from app.engines.confluence import ConfluenceEngine
from app.engines.mtf_confirmation import MTFConfirmationEngine
from app.engines.sentiment import SentimentEngine
from app.engines.news_calendar import NewsCalendarEngine
from app.utils.indicators import detect_candle_pattern, detect_divergence

router = APIRouter(prefix="/api/v1/analysis", tags=["Analysis"])

data_engine = MarketDataEngine()
structure_analyzer = MarketStructureAnalyzer()
smc_engine = SmartMoneyConceptsEngine()
confluence_engine = ConfluenceEngine()
mtf_engine = MTFConfirmationEngine()
sentiment_engine = SentimentEngine()
news_engine = NewsCalendarEngine()


_DEMO_BASE_PRICES = {
    "BTCUSDT": 67000, "ETHUSDT": 3400, "BNBUSDT": 580,
    "SOLUSDT": 145, "XRPUSDT": 0.62,
}


async def _load_candles(symbol: str, timeframe: str, demo: bool, closed_only: bool):
    """
    Load candles for analysis and report their provenance.

    closed_only=True drops the still-forming last candle so detections (FVG,
    candle patterns, divergence, structure) cannot repaint mid-candle.
    """
    sym = symbol.upper()
    if demo:
        df = MarketDataEngine.generate_sample_data(
            symbol=sym, timeframe=timeframe,
            base_price=_DEMO_BASE_PRICES.get(sym, 100),
        )
        source = SOURCE_SYNTHETIC
    else:
        df, source = await data_engine.get_candles_with_source(sym, timeframe)
    if closed_only:
        df = MarketDataEngine.drop_unclosed(df, timeframe)
    return df, source


def _meta(source: str, closed_only: bool) -> dict:
    return {
        "data_source": source,
        "is_synthetic": source == SOURCE_SYNTHETIC,
        "closed_only": closed_only,
    }


@router.get("/structure/{symbol}")
async def analyze_structure(
    symbol: str,
    timeframe: str = Query("1h", pattern=TIMEFRAME_REGEX),
    demo: bool = Query(False),
    closed_only: bool = Query(True, description="Ignore the still-forming candle"),
):
    """Get market structure analysis (HH/HL/LH/LL/BOS/CHOCH)."""
    df, source = await _load_candles(symbol, timeframe, demo, closed_only)
    result = structure_analyzer.analyze(df, symbol.upper(), timeframe)
    # mode="json" -> timestamps serialized as UTC ISO strings with 'Z'
    return {**result.model_dump(mode="json"), **_meta(source, closed_only)}


@router.get("/smc/{symbol}")
async def analyze_smc(
    symbol: str,
    timeframe: str = Query("1h", pattern=TIMEFRAME_REGEX),
    demo: bool = Query(False),
    closed_only: bool = Query(True, description="Ignore the still-forming candle"),
):
    """Get Smart Money Concepts analysis (unmitigated OB, unfilled FVG, Liquidity)."""
    df, source = await _load_candles(symbol, timeframe, demo, closed_only)
    result = smc_engine.analyze(df, symbol.upper(), timeframe)
    return {**result.model_dump(mode="json"), **_meta(source, closed_only)}


@router.get("/patterns/{symbol}")
async def analyze_patterns(
    symbol: str,
    timeframe: str = Query("1h", pattern=TIMEFRAME_REGEX),
    demo: bool = Query(False),
    closed_only: bool = Query(True, description="Ignore the still-forming candle"),
):
    """Get candlestick pattern + RSI/MACD divergence for the latest closed bars."""
    df, source = await _load_candles(symbol, timeframe, demo, closed_only)
    candle = detect_candle_pattern(df)
    divergence = detect_divergence(df)
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "candle_pattern": candle,
        "divergence": divergence,
        **_meta(source, closed_only),
    }


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
