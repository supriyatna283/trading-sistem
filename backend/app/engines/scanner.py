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
from app.engines.liquidity_sweep import LiquiditySweepEngine
from app.engines.fvg_breaker import FVGBreakerEngine
from app.engines.pd_zones import PDZoneEngine
from app.engines.setup_generator import calculate_trade_levels, _estimate_atr
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
        self.sweep_engine = LiquiditySweepEngine()
        self.fvg_engine = FVGBreakerEngine()
        self.pd_engine = PDZoneEngine()

    async def scan(
        self, symbols: List[str] = None, use_sample: bool = False, entry_tf: str = "1h"
    ) -> List[Dict]:
        """Scan a list of symbols with full macro + market intel context."""
        if not symbols:
            # Fetch dynamic symbols if no specific list provided
            all_syms = await self.data_engine.fetch_symbols()
            symbols = [s["symbol"] for s in all_syms]

        # --- PERPETUAL LIQUIDITY FILTER ---
        # Curated Top 24 Most Liquid Institutional Perpetual Pairs for fast, high-signal scanning
        PRIORITY_PERPETUALS = [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT",
            "ADAUSDT", "AVAXUSDT", "LINKUSDT", "SUIUSDT", "TONUSDT", "DOTUSDT",
            "NEARUSDT", "LTCUSDT", "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT",
            "FETUSDT", "RENDERUSDT", "TAOUSDT", "WIFUSDT", "AAVEUSDT", "ONDOUSDT",
        ]
        fetched_set = set(symbols)
        filtered = [s for s in PRIORITY_PERPETUALS if s in fetched_set]
        symbols = filtered if filtered else symbols[:24]

        # Fetch macro context + batch market caps once for all symbols (shared data)
        sentiment_data, news_events, btc_dominance = await self._fetch_macro_context(symbols)

        # Higher concurrency (12) since OKX handles parallel candle fetches smoothly
        semaphore = asyncio.Semaphore(12)

        async def _sc(sym):
            async with semaphore:
                return await self._scan_symbol(sym, sentiment_data, news_events, btc_dominance, entry_tf)

        tasks = [_sc(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        final_results = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                symbol = symbols[i]
                logger.error(f"Scan error for {symbol}: {res}")
                final_results.append({
                    "symbol": symbol,
                    "trend": "SIDEWAYS",
                    "latest_price": 0.0,
                    "price_change_24h": 0.0,
                    "liquidity_status": "Error",
                    "setup_status": "Error",
                    "confluence_score": 0,
                    "signal_score": 0,
                    "signal_grade": "NO_TRADE",
                    "score_breakdown": {"STR": 0, "PA": 0, "SMC": 0, "VOL": 0, "TIM": 0, "RR": 0},
                    "hard_rejected": True,
                    "rejection_reasons": [str(res)],
                    "mtf_confirmation": "NONE",
                    "ict_badges": [],
                    "setup": None,
                    "error": str(res),
                })
            else:
                final_results.append(res)

        return final_results

    async def _fetch_macro_context(self, symbols: Optional[List[str]] = None):
        """Fetch sentiment, news, BTC dominance, and batch market caps once (shared across all symbols)."""
        try:
            sentiment_task = self.sentiment_engine.get_full_sentiment()
            news_task = self.news_engine.get_events()
            btc_dom_task = self.intel_engine.get_btc_dominance()
            mcap_batch_task = self.intel_engine.prefetch_market_caps(symbols)

            sentiment_data, news_events, btc_dominance, _ = await asyncio.gather(
                sentiment_task, news_task, btc_dom_task, mcap_batch_task, return_exceptions=True
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
        entry_tf: str = "1h"
    ) -> Dict:
        """Scan a single symbol with full V4 pipeline including market intelligence."""
        candles_by_tf = {}

        # Fetch multiple timeframes in parallel based on entry_tf
        if entry_tf == "15m":
            tfs = ["1d", "1h", "15m"]
        elif entry_tf == "4h":
            tfs = ["1w", "1d", "4h"]
        else:
            tfs = ["1d", "4h", "1h"]
            
        tasks = [self.data_engine.get_candles(symbol, tf, 200) for tf in tfs]
        dfs = await asyncio.gather(*tasks, return_exceptions=True)

        is_synthetic = False
        data_source = "live"
        for i, df in enumerate(dfs):
            if not isinstance(df, Exception) and df is not None and not df.empty:
                tf_name = tfs[i]
                src = str(df.attrs.get("data_source", "live"))
                syn = bool(df.attrs.get("is_synthetic", False)) or src == "synthetic"
                if tf_name == entry_tf:
                    data_source = src
                    is_synthetic = syn
                cleaned = self.data_engine.drop_unclosed(df, tf_name)
                cleaned.attrs["data_source"] = src
                cleaned.attrs["is_synthetic"] = syn
                if not cleaned.empty:
                    candles_by_tf[tf_name] = cleaned

        if not candles_by_tf:
            return {
                "symbol": symbol,
                "trend": "UNKNOWN",
                "liquidity_status": "No data",
                "setup_status": "No data",
                "confluence_score": 0,
            }

        # Use entry_tf for entry analysis
        entry_df = candles_by_tf.get(entry_tf, pd.DataFrame())
        if entry_df.empty:
            entry_df = list(candles_by_tf.values())[0]

        structure = self.structure.analyze(entry_df, symbol, entry_tf)
        smc = self.smc.analyze(entry_df, symbol, entry_tf)

        # MTF Confirmation
        mtf_result = self.mtf_engine.analyze(candles_by_tf, symbol)

        # Price and 24h Change
        latest_price = float(entry_df.iloc[-1]["close"]) if not entry_df.empty else 0

        # Fast local ICT engines (<3ms CPU, 0 network calls): Sweep + FVG/Breaker + PD Zone
        htf_key = "4h" if "4h" in candles_by_tf else ("1d" if "1d" in candles_by_tf else entry_tf)
        htf_df_for_pd = candles_by_tf.get(htf_key, entry_df)
        pd_res = self.pd_engine.analyze(htf_df_for_pd, latest_price, htf_label=htf_key.upper())
        sweep_res = self.sweep_engine.analyze(entry_df)
        fvg_res = self.fvg_engine.analyze(entry_df)

        # ---- Market Intelligence (V4 — Fast Zero-Stall Lookup) ----
        # Market cap is already batch-cached in _fetch_macro_context (0ms lookup)
        mcap_data = await self.intel_engine.get_market_cap(symbol)

        # Calculate S/R and liquidation levels locally (0ms, no API call needed)
        sr_data = self.intel_engine.calculate_support_resistance(entry_df, symbol)
        liq_data = self.intel_engine.calculate_liquidation_levels(latest_price, symbol)

        market_intel_data = {
            "btc_dominance": btc_dominance or {},
            "orderbook": {},
            "liquidation": liq_data,
            "market_cap": mcap_data,
            "support_resistance": sr_data,
        }

        # Confluence scoring (V5)
        conf = self.confluence.score(
            candles_by_tf, symbol, entry_tf,
            sentiment_data=sentiment_data,
            news_events=news_events,
            mtf_result=mtf_result,
            market_intel_data=market_intel_data,
        )

        # Only fetch live L2 orderbook depth when confluence is actionable (>= 10)
        orderbook_data = {}
        if conf.total_score >= 10:
            try:
                orderbook_data = await self.intel_engine.get_order_book_depth(symbol)
                market_intel_data["orderbook"] = orderbook_data
            except Exception:
                orderbook_data = {}

        # Liquidity status (combining SMC + dedicated LiquiditySweepEngine)
        latest_sw = sweep_res.get("latest_sweep") if isinstance(sweep_res, dict) else None
        swept = (
            bool(latest_sw and latest_sw.get("is_confirmed"))
            or any(getattr(l, "swept", False) for l in smc.liquidity_levels)
            or self.smc.check_liquidity_sweep(entry_df, smc.liquidity_levels)
        )
        if latest_sw and latest_sw.get("is_confirmed"):
            sw_side = "SSL Swept (Bullish)" if latest_sw.get("direction_after") == "BUY" else "BSL Swept (Bearish)"
            liq_status = sw_side
        elif swept:
            liq_status = "Liquidity taken"
        elif smc.liquidity_levels:
            above = any(l.type == "EQUAL_HIGH" for l in smc.liquidity_levels)
            below = any(l.type == "EQUAL_LOW" for l in smc.liquidity_levels)
            if above and below:
                liq_status = "Pools above & below"
            elif above:
                liq_status = "BSL Pool above"
            else:
                liq_status = "SSL Pool below"
        else:
            liq_status = "No clear liquidity"

        # Volume Delta Filter (Phase 3) - Only fetch if confluence is decent to save API limits
        volume_delta = None
        if conf.total_score >= 12:
            try:
                from app.engines.order_flow_engine import order_flow_engine
                footprint = await order_flow_engine.get_footprint(symbol, entry_tf, limit=1)
                if footprint and len(footprint) > 0:
                    volume_delta = footprint[-1].get("delta", 0)
            except Exception:
                pass

        # ── Institutional Directional Consensus (Quant + ICT) ──
        # Prevents "SIDEWAYS" trend when HTF/Confluence/ICT have a clear directional setup
        dom_bias = conf.details.get("htf_bias", {}).get("dominant_bias", "SIDEWAYS")
        mtf_dom = mtf_result.get("dominant_bias", "NEUTRAL") if isinstance(mtf_result, dict) else "NEUTRAL"

        dir_votes = 0.0
        if conf.recommendation == "STRONG_BUY":
            dir_votes += 3.5
        elif conf.recommendation == "BUY":
            dir_votes += 2.5
        elif conf.recommendation == "STRONG_SELL":
            dir_votes -= 3.5
        elif conf.recommendation == "SELL":
            dir_votes -= 2.5

        if structure.bias == "BULLISH":
            dir_votes += 1.5
        elif structure.bias == "BEARISH":
            dir_votes -= 1.5

        if dom_bias == "BULLISH":
            dir_votes += 2.0
        elif dom_bias == "BEARISH":
            dir_votes -= 2.0

        if mtf_dom == "BULLISH":
            dir_votes += 1.5
        elif mtf_dom == "BEARISH":
            dir_votes -= 1.5

        if pd_res.signal in ("BUY", "STRONG_BUY"):
            dir_votes += 1.5
        elif pd_res.signal in ("SELL", "STRONG_SELL"):
            dir_votes -= 1.5

        if latest_sw and latest_sw.get("sweep_bar_idx", 0) >= 55:
            if latest_sw.get("direction_after") == "BUY":
                dir_votes += 2.0
            elif latest_sw.get("direction_after") == "SELL":
                dir_votes -= 2.0

        if fvg_res.entry_bias in ("BUY", "STRONG_BUY"):
            dir_votes += 1.5
        elif fvg_res.entry_bias in ("SELL", "STRONG_SELL"):
            dir_votes -= 1.5

        if dir_votes >= 2.0:
            effective_trend = "BULLISH"
            trade_dir = "BUY"
        elif dir_votes <= -2.0:
            effective_trend = "BEARISH"
            trade_dir = "SELL"
        else:
            effective_trend = "SIDEWAYS"
            trade_dir = None

        # Setup generation (V4 — passes market intel for explanation enrichment)
        setup = self.setup_gen.generate(
            symbol, entry_tf, conf, smc, structure, entry_df,
            mtf_result=mtf_result,
            news_events=news_events,
            sentiment_data=sentiment_data,
            market_intel_data=market_intel_data,
            volume_delta=volume_delta,
        )
        setup_dict = setup.model_dump() if setup else None

        price_change_24h = 0.0
        bars_24h = {"5m": 288, "15m": 96, "30m": 48, "1h": 24, "4h": 6, "1d": 1}.get(entry_tf, 24)
        if len(entry_df) > bars_24h:
            price_24h_ago = float(entry_df.iloc[-(bars_24h + 1)]["close"])
            if price_24h_ago > 0:
                price_change_24h = ((latest_price - price_24h_ago) / price_24h_ago) * 100

        # RSI Analysis
        rsi_1h = calculate_rsi(candles_by_tf.get("1h", entry_df), 14)
        rsi_4h = calculate_rsi(candles_by_tf.get("4h", pd.DataFrame()), 14)
        rsi_1d = calculate_rsi(candles_by_tf.get("1d", pd.DataFrame()), 14)

        # Signal status based on RSI strength
        strong_rsi_signal = False
        if rsi_1h is not None:
            if rsi_1h <= 25 or rsi_1h >= 75:
                strong_rsi_signal = True

        # --- Final Hybrid Quant + ICT Scoring & Grade ---
        quant_pct = (conf.total_score / conf.max_score) * 100 if conf.max_score > 0 else 0
        # ICT bonus/alignment weight (PD Zone + OTE + Sweep + FVG/Breaker)
        ict_bonus = 0.0
        if trade_dir == "BUY":
            if pd_res.zone == "DISCOUNT":
                ict_bonus += 6.0
            if pd_res.is_in_ote:
                ict_bonus += 5.0
            if latest_sw and latest_sw.get("direction_after") == "BUY":
                ict_bonus += 6.0
            if fvg_res.nearest_bullish_fvg is not None:
                ict_bonus += 5.0
        elif trade_dir == "SELL":
            if pd_res.zone == "PREMIUM":
                ict_bonus += 6.0
            if pd_res.is_in_ote:
                ict_bonus += 5.0
            if latest_sw and latest_sw.get("direction_after") == "SELL":
                ict_bonus += 6.0
            if fvg_res.nearest_bearish_fvg is not None:
                ict_bonus += 5.0

        signal_score = min(99, round(quant_pct * 0.82 + ict_bonus)) if trade_dir else min(42, round(quant_pct * 0.6))

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

        # SMC: derive from actual SmartMoneyAnalysis V3 attributes
        smc_points = 0.0
        smc_max = 4.0
        active_obs = [ob for ob in getattr(smc, "order_blocks", []) if not getattr(ob, "invalidated", False)]
        unmitigated_obs = [ob for ob in active_obs if not getattr(ob, "mitigated", False)]
        if unmitigated_obs:
            smc_points += 1.5
        elif active_obs:
            smc_points += 0.75

        active_fvgs = [f for f in getattr(smc, "fvgs", []) if not getattr(f, "filled", False)]
        if active_fvgs:
            smc_points += 1.0

        pd_mid = getattr(smc, "premium_discount_mid", None)
        if pd_mid and latest_price > 0:
            in_favorable_pd = (
                (structure.bias == "BULLISH" and latest_price < pd_mid)
                or (structure.bias == "BEARISH" and latest_price > pd_mid)
            )
            if in_favorable_pd:
                smc_points += 1.0
            else:
                smc_points += 0.5

        if swept:
            smc_points += 0.5

        smc_pct = round(min(smc_points, smc_max) / smc_max * 100)

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
            
        # Liquidation Magnet for RR
        liq_low = liq_data.get("cluster_zone", {}).get("low", 0)
        liq_high = liq_data.get("cluster_zone", {}).get("high", 0)
        if structure.bias == "BULLISH" and liq_high > latest_price:
            rr_points += 1  # Strong magnet above
        elif structure.bias == "BEARISH" and liq_low > 0 and liq_low < latest_price:
            rr_points += 1  # Strong magnet below
            
        rr_pct = round(min(rr_points, rr_max) / rr_max * 100)

        score_breakdown = {
            "STR": str_pct,
            "PA":  pa_pct,
            "SMC": smc_pct,
            "VOL": vol_pct,
            "TIM": tim_pct,
            "RR":  rr_pct,
        }

        # Check for hard rejection (ATR-scaled S/R check instead of naive 1.0% wall)
        rejection_reasons = []
        hard_rejected = False
        atr_val = _estimate_atr(entry_df.tail(25)) or (latest_price * 0.008)
        atr_pct = (atr_val / latest_price * 100) if latest_price > 0 else 0.8
        min_sr_clearance_pct = min(0.35, atr_pct * 0.28)

        if is_synthetic:
            hard_rejected = True
            rejection_reasons.append("Synthetic fallback data")

        if not trade_dir or effective_trend == "SIDEWAYS":
            hard_rejected = True
            rejection_reasons.append("Sideways / No directional bias")

        if signal_score < 35:
            hard_rejected = True
            rejection_reasons.append("Low confluence")

        if rsi_1h is not None and trade_dir:
            if trade_dir == "BUY" and rsi_1h > 76:
                hard_rejected = True
                rejection_reasons.append(f"Overbought RSI ({rsi_1h:.0f})")
            elif trade_dir == "SELL" and rsi_1h < 24:
                hard_rejected = True
                rejection_reasons.append(f"Oversold RSI ({rsi_1h:.0f})")

        # Only reject S/R proximity if jammed directly against level (<0.28 ATR) without BOS confirmation
        has_bos = conf.details.get("structure", {}).get("confirmed", False)
        if trade_dir == "BUY" and not has_bos:
            res_dist = sr_data.get("resistance_distance_pct")
            if res_dist is not None and res_dist < min_sr_clearance_pct:
                hard_rejected = True
                rejection_reasons.append("At Immediate Resistance")
        elif trade_dir == "SELL" and not has_bos:
            sup_dist = sr_data.get("support_distance_pct")
            if sup_dist is not None and sup_dist < min_sr_clearance_pct:
                hard_rejected = True
                rejection_reasons.append("At Immediate Support")

        # Build ICT + Quant Badges for Scanner UI (strictly aligned with trade_dir)
        ict_badges: List[str] = []
        if trade_dir == "BUY" and pd_res.zone == "DISCOUNT":
            ict_badges.append(f"Discount{' OTE' if pd_res.is_in_ote else ''}")
        elif trade_dir == "SELL" and pd_res.zone == "PREMIUM":
            ict_badges.append(f"Premium{' OTE' if pd_res.is_in_ote else ''}")
        elif pd_res.is_in_ote:
            ict_badges.append("OTE Zone")
        fib_det = conf.details.get("fibonacci", {})
        if fib_det.get("score", 0) >= 2 and fib_det.get("nearest_level"):
            ict_badges.append(f"Fib {fib_det['nearest_level']}")
        if latest_sw and latest_sw.get("is_confirmed") and (not trade_dir or latest_sw.get("direction_after") == trade_dir):
            ict_badges.append("Liq Sweep")
        if trade_dir == "BUY" and fvg_res.nearest_bullish_fvg is not None:
            ict_badges.append("Bull FVG")
        elif trade_dir == "SELL" and fvg_res.nearest_bearish_fvg is not None:
            ict_badges.append("Bear FVG")
        if fvg_res.nearest_breaker is not None and getattr(fvg_res.nearest_breaker, "type", "") == ("BULLISH" if trade_dir == "BUY" else "BEARISH"):
            ict_badges.append("Breaker")
        dir_obs = [
            ob for ob in unmitigated_obs
            if (trade_dir == "BUY" and getattr(ob, "type", "") == "BULLISH")
            or (trade_dir == "SELL" and getattr(ob, "type", "") == "BEARISH")
        ]
        if dir_obs:
            ict_badges.append(f"{len(dir_obs)} {'Bull' if trade_dir == 'BUY' else 'Bear'} OB")
        elif not trade_dir and unmitigated_obs:
            ict_badges.append(f"{len(unmitigated_obs)} OB")
        if has_bos:
            ict_badges.append("BOS/CHoCH")

        # Ensure actionable directional pairs (score >= 48 & not rejected) always have a validated Trade Plan
        if setup_dict is None and trade_dir in ("BUY", "SELL") and not hard_rejected and signal_score >= 48:
            e_low, e_high, sl_px, tp1_px, tp2_px, tp3_px = calculate_trade_levels(
                trade_dir, latest_price, smc, entry_df
            )
            e_mid = round((e_low + e_high) / 2.0, 6)
            risk_u = abs(e_high - sl_px) if trade_dir == "BUY" else abs(sl_px - e_low)
            rr_val = round(abs(tp2_px - e_high if trade_dir == "BUY" else e_low - tp2_px) / risk_u, 2) if risk_u > 0 else 2.0
            setup_dict = {
                "symbol": symbol,
                "direction": trade_dir,
                "entry_price": e_mid,
                "entry_low": round(e_low, 6),
                "entry_high": round(e_high, 6),
                "stop_loss": round(sl_px, 6),
                "take_profit_1": round(tp1_px, 6),
                "take_profit_2": round(tp2_px, 6),
                "take_profit_3": round(tp3_px, 6),
                "risk_reward": rr_val,
                "risk_pct": round(risk_u / e_mid * 100, 2) if e_mid > 0 else 1.0,
                "setup_type": " + ".join(ict_badges[:3]) if ict_badges else f"{trade_dir} Confluence",
                "confluence_score": conf.total_score,
                "status": "ACTIVE",
                "timeframe": entry_tf,
                "pd_zone": pd_res.zone,
                "in_ote": pd_res.is_in_ote,
            }
        elif setup_dict is not None:
            e_low = float(setup_dict.get("entry_low") or latest_price)
            e_high = float(setup_dict.get("entry_high") or latest_price)
            e_mid = round((e_low + e_high) / 2.0, 6)
            sl_px = float(setup_dict.get("stop_loss") or 0)
            risk_u = abs(e_high - sl_px) if setup_dict.get("direction") == "BUY" else abs(sl_px - e_low)
            setup_dict["entry_price"] = e_mid
            setup_dict["risk_pct"] = round(risk_u / e_mid * 100, 2) if e_mid > 0 else 1.0
            setup_dict["pd_zone"] = pd_res.zone
            setup_dict["in_ote"] = pd_res.is_in_ote
            # Align effective_trend with generated setup direction
            effective_trend = "BULLISH" if setup_dict.get("direction") == "BUY" else "BEARISH"

        # Determine final signal grade & setup status (strictly gated by hard_rejected & setup presence)
        if hard_rejected or effective_trend == "SIDEWAYS" or setup_dict is None:
            signal_grade = "WEAK" if (not hard_rejected and signal_score >= 40) else "NO_TRADE"
            setup_status = rejection_reasons[0] if rejection_reasons else "Waiting trigger"
        else:
            if signal_score >= 72:
                signal_grade = "A+"
            elif signal_score >= 48:
                signal_grade = "VALID"
            else:
                signal_grade = "WEAK"
            setup_status = f"{setup_dict['direction']} · {setup_dict.get('setup_type', 'Ready')}"

        return {
            "symbol": symbol,
            "data_source": data_source,
            "is_synthetic": is_synthetic,
            "trend": effective_trend,
            "latest_price": latest_price,
            "price_change_24h": price_change_24h,
            "liquidity_status": liq_status,
            "setup_status": setup_status,
            "confluence_score": conf.total_score,
            "max_score": conf.max_score,
            "signal_score": signal_score,
            "signal_grade": signal_grade,
            "score_breakdown": score_breakdown,
            "hard_rejected": hard_rejected,
            "rejection_reasons": rejection_reasons,
            "mtf_confirmation": mtf_level,
            "ict_badges": ict_badges,
            "pd_zone": pd_res.zone,
            "in_ote": pd_res.is_in_ote,
            "setup": setup_dict,
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
            # --- New Features ---
            "volume_delta": volume_delta,
            "funding_rate": next((m.get("funding_rate", 0) for m in (sentiment_data.get("market_metrics", []) if sentiment_data else []) if m["symbol"] == symbol), 0),
            "open_interest": next((m.get("open_interest", 0) for m in (sentiment_data.get("market_metrics", []) if sentiment_data else []) if m["symbol"] == symbol), 0),
        }
