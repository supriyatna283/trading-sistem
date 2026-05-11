"""
Market Scanner (V4 - Full Market Intelligence)
================================================
Scans multiple assets using REAL Binance data with full integration of:
- SMC analysis (unmitigated OBs, unfilled FVGs)
- Multi-TF Confluence (24-point system with market intelligence)
- MTF Confirmation engine
- Sentiment analysis (Fear & Greed, Funding, OI via Binance)
- News calendar filter
- Market Intelligence (BTC Dominance, Order Book, Liquidation, MCap, S/R)

Only generates signals with score >= 5/24 and R:R >= 1.5 (maximized logic).
"""

import pandas as pd
import asyncio
import logging
from typing import List, Dict, Optional
from app.engines.market_data import MarketDataEngine
from app.engines.market_structure import MarketStructureAnalyzer
from app.engines.smart_money import SmartMoneyConceptsEngine
from app.engines.confluence import ConfluenceEngine
from app.engines.setup_generator import SetupGenerator
from app.engines.mtf_confirmation import MTFConfirmationEngine
from app.engines.sentiment import SentimentEngine
from app.engines.news_calendar import NewsCalendarEngine
from app.engines.market_intel import MarketIntelEngine
from app.utils.indicators import calculate_rsi

logger = logging.getLogger(__name__)


SCAN_TIMEFRAMES = ["1d", "4h", "1h"]


class MarketScanner:
    """V4 — Scans multiple assets with full market intelligence integration."""

    def __init__(self, redis_client=None):
        self.data_engine = MarketDataEngine(redis_client=redis_client)
        self.structure = MarketStructureAnalyzer()
        self.smc = SmartMoneyConceptsEngine()
        self.confluence = ConfluenceEngine()
        self.setup_gen = SetupGenerator(min_confluence_score=12, min_rr=1.8)
        self.mtf_engine = MTFConfirmationEngine()
        self.sentiment_engine = SentimentEngine()
        self.news_engine = NewsCalendarEngine()
        self.intel_engine = MarketIntelEngine()

    async def scan(
        self, symbols: List[str] = None, use_sample: bool = False
    ) -> List[Dict]:
        """Scan a list of symbols with full macro + market intel context."""
        if not symbols:
            # Fetch dynamic symbols if no specific list provided
            all_syms = await self.data_engine.fetch_symbols()
            symbols = [s["symbol"] for s in all_syms]

        # Fetch macro context once for all symbols (shared data)
        sentiment_data, news_events, btc_dominance = await self._fetch_macro_context()

        # Run with concurrency limit to avoid overwhelming resources
        semaphore = asyncio.Semaphore(15)

        async def _sc(sym):
            async with semaphore:
                return await self._scan_symbol(sym, sentiment_data, news_events, btc_dominance)

        tasks = [_sc(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        final_results = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                symbol = symbols[i]
                logger.error(f"Scan error for {symbol}: {res}")
                final_results.append({
                    "symbol": symbol,
                    "trend": "UNKNOWN",
                    "liquidity_status": "Error",
                    "setup_status": "Error",
                    "confluence_score": 0,
                    "error": str(res),
                })
            else:
                final_results.append(res)

        return final_results

    async def _fetch_macro_context(self):
        """Fetch sentiment, news, and BTC dominance data once (shared across all symbols)."""
        try:
            sentiment_task = self.sentiment_engine.get_full_sentiment()
            news_task = self.news_engine.get_events()
            btc_dom_task = self.intel_engine.get_btc_dominance()

            sentiment_data, news_events, btc_dominance = await asyncio.gather(
                sentiment_task, news_task, btc_dom_task, return_exceptions=True
            )
            if isinstance(sentiment_data, Exception):
                logger.warning(f"Sentiment fetch failed: {sentiment_data}")
                sentiment_data = None
            if isinstance(news_events, Exception):
                logger.warning(f"News fetch failed: {news_events}")
                news_events = None
            if isinstance(btc_dominance, Exception):
                logger.warning(f"BTC dominance fetch failed: {btc_dominance}")
                btc_dominance = {}
        except Exception as e:
            logger.warning(f"Macro context fetch failed: {e}")
            sentiment_data = None
            news_events = None
            btc_dominance = {}
        return sentiment_data, news_events, btc_dominance

    async def _scan_symbol(
        self, symbol: str,
        sentiment_data: Optional[Dict] = None,
        news_events: Optional[List[Dict]] = None,
        btc_dominance: Optional[Dict] = None,
    ) -> Dict:
        """Scan a single symbol with full V4 pipeline including market intelligence."""
        candles_by_tf = {}

        # Fetch multiple timeframes in parallel
        tfs = ["1d", "4h", "1h"]
        tasks = [self.data_engine.get_candles(symbol, tf, 200) for tf in tfs]
        dfs = await asyncio.gather(*tasks, return_exceptions=True)

        for i, df in enumerate(dfs):
            if not isinstance(df, Exception) and not df.empty:
                candles_by_tf[tfs[i]] = df

        if not candles_by_tf:
            return {
                "symbol": symbol,
                "trend": "UNKNOWN",
                "liquidity_status": "No data",
                "setup_status": "No data",
                "confluence_score": 0,
            }

        # Use 1h for entry analysis
        entry_df = candles_by_tf.get("1h", pd.DataFrame())
        if entry_df.empty:
            entry_df = list(candles_by_tf.values())[0]

        structure = self.structure.analyze(entry_df, symbol, "1h")
        smc = self.smc.analyze(entry_df, symbol, "1h")

        # MTF Confirmation
        mtf_result = self.mtf_engine.analyze(candles_by_tf, symbol)

        # Price and 24h Change
        latest_price = float(entry_df.iloc[-1]["close"]) if not entry_df.empty else 0

        # ---- Market Intelligence (V4) ----
        # Fetch per-symbol data: order book, S/R, liquidation, market cap
        try:
            orderbook_task = self.intel_engine.get_order_book_depth(symbol)
            mcap_task = self.intel_engine.get_market_cap(symbol)
            orderbook_data, mcap_data = await asyncio.gather(
                orderbook_task, mcap_task, return_exceptions=True
            )
            if isinstance(orderbook_data, Exception):
                orderbook_data = {}
            if isinstance(mcap_data, Exception):
                mcap_data = {}
        except Exception:
            orderbook_data = {}
            mcap_data = {}

        # Calculate S/R and liquidation levels (no API call needed)
        sr_data = self.intel_engine.calculate_support_resistance(entry_df, symbol)
        liq_data = self.intel_engine.calculate_liquidation_levels(latest_price, symbol)

        # Build market_intel_data dict for confluence scoring
        market_intel_data = {
            "btc_dominance": btc_dominance or {},
            "orderbook": orderbook_data,
            "liquidation": liq_data,
            "market_cap": mcap_data,
            "support_resistance": sr_data,
        }

        # Confluence scoring (V4 — 24-point system with market intelligence)
        conf = self.confluence.score(
            candles_by_tf, symbol, "1h",
            sentiment_data=sentiment_data,
            news_events=news_events,
            mtf_result=mtf_result,
            market_intel_data=market_intel_data,
        )

        # Liquidity status
        swept = self.smc.check_liquidity_sweep(entry_df, smc.liquidity_levels)
        if swept:
            liq_status = "Liquidity taken"
        elif smc.liquidity_levels:
            above = any(l.type == "EQUAL_HIGH" for l in smc.liquidity_levels)
            below = any(l.type == "EQUAL_LOW" for l in smc.liquidity_levels)
            if above and below:
                liq_status = "Liquidity above & below"
            elif above:
                liq_status = "Liquidity above"
            else:
                liq_status = "Liquidity below"
        else:
            liq_status = "No clear liquidity"

        # Setup generation (V4 — passes market intel for explanation enrichment)
        setup = self.setup_gen.generate(
            symbol, "1h", conf, smc, structure, entry_df,
            mtf_result=mtf_result,
            news_events=news_events,
            sentiment_data=sentiment_data,
            market_intel_data=market_intel_data,
        )
        if setup:
            setup_status = f"{setup.direction} setup"
        elif conf.total_score >= 10:
            setup_status = "Setup forming"
        else:
            setup_status = "No setup"

        price_change_24h = 0
        if len(entry_df) >= 24:
            price_24h_ago = float(entry_df.iloc[-24]["close"])
            if price_24h_ago > 0:
                price_change_24h = ((latest_price - price_24h_ago) / price_24h_ago) * 100

        # RSI Analysis
        rsi_1h = calculate_rsi(candles_by_tf.get("1h", pd.DataFrame()), 14)
        rsi_4h = calculate_rsi(candles_by_tf.get("4h", pd.DataFrame()), 14)
        rsi_1d = calculate_rsi(candles_by_tf.get("1d", pd.DataFrame()), 14)

        # Signal status based on RSI strength
        strong_rsi_signal = False
        if rsi_1h is not None:
            if rsi_1h <= 25 or rsi_1h >= 75:
                strong_rsi_signal = True

        return {
            "symbol": symbol,
            "trend": structure.bias,
            "latest_price": latest_price,
            "price_change_24h": price_change_24h,
            "liquidity_status": liq_status,
            "setup_status": setup_status,
            "confluence_score": conf.total_score,
            "max_score": conf.max_score,
            "mtf_confirmation": mtf_result.get("confirmation_level", "NONE"),
            "setup": setup.model_dump() if setup else None,
            "rsi_1h": rsi_1h,
            "rsi_4h": rsi_4h,
            "rsi_1d": rsi_1d,
            "strong_rsi_signal": strong_rsi_signal,
            # --- Market Intelligence (V4) ---
            "btc_dominance": (btc_dominance or {}).get("btc_dominance", 0),
            "orderbook_ratio": orderbook_data.get("buy_sell_ratio", 1.0) if isinstance(orderbook_data, dict) else 1.0,
            "orderbook_bias": orderbook_data.get("bias", "NEUTRAL") if isinstance(orderbook_data, dict) else "NEUTRAL",
            "nearest_support": sr_data.get("nearest_support", 0),
            "nearest_resistance": sr_data.get("nearest_resistance", 0),
            "support_distance_pct": sr_data.get("support_distance_pct", 0),
            "resistance_distance_pct": sr_data.get("resistance_distance_pct", 0),
            "liquidation_cluster_low": liq_data.get("cluster_zone", {}).get("low", 0),
            "liquidation_cluster_high": liq_data.get("cluster_zone", {}).get("high", 0),
            "market_cap_tier": mcap_data.get("tier", "UNKNOWN") if isinstance(mcap_data, dict) else "UNKNOWN",
            "market_cap_usd": mcap_data.get("market_cap_usd", 0) if isinstance(mcap_data, dict) else 0,
        }
