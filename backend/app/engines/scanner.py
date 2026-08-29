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
    """V5 — Scans multiple assets with full market intelligence integration."""

    def __init__(self, redis_client=None):
        self.data_engine = MarketDataEngine(redis_client=redis_client)
        self.structure = MarketStructureAnalyzer()
        self.smc = SmartMoneyConceptsEngine()
        self.confluence = ConfluenceEngine()
        # FIX #3: Threshold 12/18 (consistent with Setups page). Old 16/18 was too strict.
        self.setup_gen = SetupGenerator(min_confluence_score=12, min_rr=1.5)
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

        # --- PERPETUAL LIQUIDITY FILTER ---
        # Only scan pairs that meet minimum liquidity requirements.
        # This prevents false signals from illiquid markets.
        PRIORITY_PERPETUALS = [
            # Major
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
            # Large Cap
            "ADAUSDT", "AVAXUSDT", "DOGEUSDT", "DOTUSDT", "LINKUSDT",
            # FIX #4: MATIC renamed to POL on Binance (Aug 2024)
            "POLUSDT", "UNIUSDT", "AAVEUSDT", "ATOMUSDT", "LTCUSDT",
            "NEARUSDT", "FILUSDT", "APTUSDT", "ARBUSDT", "OPUSDT",
            "INJUSDT", "SUIUSDT", "TIAUSDT", "WIFUSDT", "JUPUSDT",
            # DeFi
            "SEIUSDT", "STRKUSDT", "PYTHUSDT", "JITOUSDT",
        ]
        # Intersect: keep only pairs that are both in the fetched list AND in our priority list
        # If the list is smaller than priority list (e.g. new pairs), allow it through
        fetched_set = set(symbols)
        filtered = [s for s in PRIORITY_PERPETUALS if s in fetched_set]
        # If filter yields nothing (API returned different symbols), use the raw list capped at 50
        symbols = filtered if filtered else symbols[:50]

        # Fetch macro context once for all symbols (shared data)
        sentiment_data, news_events, btc_dominance = await self._fetch_macro_context()

        # FIX #9: Limit to 6 concurrent to avoid Binance rate-limit on HF Spaces
        semaphore = asyncio.Semaphore(6)

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

        # Volume Delta Filter (Phase 3) - Only fetch if confluence is decent to save API limits
        volume_delta = None
        if conf.total_score >= 12:
            try:
                from app.engines.order_flow_engine import order_flow_engine
                footprint = await order_flow_engine.get_footprint(symbol, "1h", limit=1)
                if footprint and len(footprint) > 0:
                    volume_delta = footprint[-1].get("delta", 0)
            except Exception as e:
                pass

        # Setup generation (V4 — passes market intel for explanation enrichment)
        setup = self.setup_gen.generate(
            symbol, "1h", conf, smc, structure, entry_df,
            mtf_result=mtf_result,
            news_events=news_events,
            sentiment_data=sentiment_data,
            market_intel_data=market_intel_data,
            volume_delta=volume_delta,
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

        # --- Final Scoring & Grade ---
        # Scale 18-point score to 100-point scale
        signal_score = round((conf.total_score / conf.max_score) * 100) if conf.max_score > 0 else 0

        # FIX #1 + #5: score_breakdown now uses ACTUAL keys from confluence.py details.
        # Confluence.py only writes: fibonacci, macd, rsi, htf_bias, structure, volume, session, news
        # SMC and RR are derived from smc analysis + mtf + market intel objects.
        det = conf.details

        # PA = Signal Generators: Fibonacci(4) + MACD(4) + RSI(4) = max 12
        pa_raw = (det.get("fibonacci", {}).get("score", 0)
                  + det.get("macd", {}).get("score", 0)
                  + det.get("rsi", {}).get("score", 0))
        pa_pct = round(pa_raw / 12 * 100)

        # STR = HTF Bias(2) + Structure(1) = max 3
        str_raw = (det.get("htf_bias", {}).get("score", 0)
                   + det.get("structure", {}).get("score", 0))
        str_pct = round(str_raw / 3 * 100)

        # VOL = Volume(1) = max 1 (either 0 or 100)
        vol_pct = round(det.get("volume", {}).get("score", 0) * 100)

        # TIM = Session(1) + News(1) = max 2
        tim_raw = (det.get("session", {}).get("score", 0)
                   + det.get("news", {}).get("score", 0))
        tim_pct = round(tim_raw / 2 * 100)

        # SMC: derive from actual SMC analysis object (not confluence details)
        smc_points = 0
        smc_max = 4
        if hasattr(smc, "unmitigated_ob_count") and smc.unmitigated_ob_count > 0:
            smc_points += 2
        if hasattr(smc, "unfilled_fvg_count") and smc.unfilled_fvg_count > 0:
            smc_points += 1
        if hasattr(smc, "pd_zone") and smc.pd_zone in ("DISCOUNT", "PREMIUM"):
            smc_points += 1
        smc_pct = round(smc_points / smc_max * 100)

        # RR: derive from MTF + order book + S/R proximity
        rr_points = 0
        rr_max = 4
        # FIX #6: mtf_result is a dict (MTFConfirmationEngine.analyze returns dict)
        mtf_level = mtf_result.get("confirmation_level", "NONE") if isinstance(mtf_result, dict) else "NONE"
        if mtf_level == "STRONG":
            rr_points += 2
        elif mtf_level == "MODERATE":
            rr_points += 1
        if isinstance(orderbook_data, dict) and orderbook_data.get("bias") in ("BULLISH", "BEARISH"):
            rr_points += 1
        sr_dist = sr_data.get("support_distance_pct", 100) if structure.bias == "BULLISH" else sr_data.get("resistance_distance_pct", 100)
        if sr_dist is not None and sr_dist < 1.5:
            rr_points += 1  # Price very near key S/R level — RR favorable
        rr_pct = round(min(rr_points, rr_max) / rr_max * 100)

        score_breakdown = {
            "STR": str_pct,
            "PA":  pa_pct,
            "SMC": smc_pct,
            "VOL": vol_pct,
            "TIM": tim_pct,
            "RR":  rr_pct,
        }

        # Determine signal grade
        if signal_score >= 75:
            signal_grade = "A+"
        elif signal_score >= 50:
            signal_grade = "VALID"
        elif signal_score >= 35:
            signal_grade = "WEAK"
        else:
            signal_grade = "NO_TRADE"

        # Check for hard rejection (e.g. against major trend or extreme RSI)
        rejection_reasons = []
        hard_rejected = False
        
        if signal_score < 25:
            hard_rejected = True
            rejection_reasons.append("Low confluence")
        
        if rsi_1h is not None:
            if structure.bias == "BULLISH" and rsi_1h > 75:
                hard_rejected = True
                rejection_reasons.append("Overbought RSI")
            if structure.bias == "BEARISH" and rsi_1h < 25:
                hard_rejected = True
                rejection_reasons.append("Oversold RSI")

        return {
            "symbol": symbol,
            "trend": structure.bias,
            "latest_price": latest_price,
            "price_change_24h": price_change_24h,
            "liquidity_status": liq_status,
            "setup_status": setup_status,
            "confluence_score": conf.total_score,
            "max_score": conf.max_score,
            "signal_score": signal_score, # For frontend progress bar (0-100)
            "signal_grade": signal_grade, # For frontend badge
            "score_breakdown": score_breakdown, # For LayerBreakdown component
            "hard_rejected": hard_rejected,
            "rejection_reasons": rejection_reasons,
            "mtf_confirmation": mtf_level,
            "setup": setup.model_dump() if setup else None,
            "rsi_1h": rsi_1h,
            "rsi_4h": rsi_4h,
            "rsi_1d": rsi_1d,
            "strong_rsi_signal": strong_rsi_signal,
            "last_scan_at": pd.Timestamp.utcnow().isoformat(),
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
