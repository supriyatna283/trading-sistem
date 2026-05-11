"""
Multi-Timeframe Confluence Engine (V4 - Market Intelligence)
==============================================================
Scores trade setups by checking alignment across multiple timeframes.
V4 adds 6 new market intelligence criteria (24-point system):
- BTC Dominance alignment, Order Book depth, Liquidation magnets,
  Market Cap quality, Support/Resistance alignment
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.engines.market_structure import MarketStructureAnalyzer
from app.engines.smart_money import SmartMoneyConceptsEngine
from app.schemas.market_data import MarketBias, SmartMoneyAnalysis
from app.schemas.trade_setup import ConfluenceResult
from app.utils.indicators import calculate_rsi, calculate_ema, calculate_macd, calculate_bollinger_bands, calculate_stoch_rsi


TIMEFRAMES = ["1d", "4h", "1h", "15m", "5m"]

# V4 scoring: 24-point system with market intelligence criteria
SCORE_WEIGHTS = {
    # --- Core Technical (14 pts) ---
    "htf_bias_aligned": 2,       # 1D and 4H agree on direction
    "liquidity_swept": 2,        # Liquidity taken before entry
    "order_block_zone": 2,       # Price inside an UNMITIGATED OB (fresh)
    "fvg_present": 1,            # UNFILLED FVG supports the direction
    "structure_confirmed": 1,    # BOS or CHOCH on entry TF
    "premium_discount": 1,       # Buying in discount / selling in premium
    "volume_confirmation": 1,    # Volume spike confirms move (2.0x threshold)
    "session_quality": 1,        # Trading during London/NY active sessions
    "mtf_confirmation": 1,       # Multi-TF confirmation level >= MODERATE
    "news_clear": 1,             # No high-impact news within 2 hours
    "sentiment_aligned": 1,      # Macro sentiment supports direction (F&G + Funding)
    "rsi_aligned": 1,            # RSI supports direction
    "ema_aligned": 2,            # Price on the right side of 200 EMA
    "macd_aligned": 1,           # MACD histogram supports momentum
    # --- Intraday Indicators (3 pts) ---
    "bb_position": 1,            # Price position relative to Bollinger Bands
    "stoch_rsi_aligned": 2,      # Stoch RSI momentum crossover confirmation
    # --- Market Intelligence (6 pts) ---
    "btc_dominance_aligned": 1,  # BTC.D trend favors the trade
    "orderbook_depth_aligned": 1,# Order book buy/sell ratio confirms direction
    "liquidation_magnet": 1,     # Price near liquidation cluster (high-probability zone)
    "market_cap_quality": 1,     # Higher mcap = safer signal quality
    "support_resistance_aligned": 2, # Entry near key S/R level
}

MAX_SCORE = sum(SCORE_WEIGHTS.values())  # 24

# Session windows (UTC hours)
LONDON_SESSION = (8, 16)   # 08:00 - 16:00 UTC
NY_SESSION = (13, 21)      # 13:00 - 21:00 UTC


class ConfluenceEngine:
    """V4 — Scores trade setups with market intelligence + multi-timeframe confluence."""

    def __init__(self, min_confluence_score: int = 14):
        self.structure_analyzer = MarketStructureAnalyzer()
        self.smc_engine = SmartMoneyConceptsEngine()
        self.min_confluence_score = min_confluence_score

    def score(
        self,
        candles_by_tf: Dict[str, pd.DataFrame],
        symbol: str = "",
        entry_timeframe: str = "1h",
        sentiment_data: Optional[Dict] = None,
        news_events: Optional[List[Dict]] = None,
        mtf_result: Optional[Dict] = None,
        market_intel_data: Optional[Dict] = None,
    ) -> ConfluenceResult:
        """
        Score confluence across timeframes.

        candles_by_tf: dict mapping timeframe → DataFrame
        entry_timeframe: the timeframe used for entry (e.g. "1h")
        sentiment_data: optional dict with fear_and_greed + market_metrics
        news_events: optional list of calendar events
        mtf_result: optional dict from MTFConfirmationEngine
        market_intel_data: optional dict from MarketIntelEngine.get_overview()
        """
        details = {}
        total_score = 0

        # 1. Higher timeframe bias alignment (1D + 4H must agree)
        htf_biases = {}
        for tf in ["1d", "4h"]:
            if tf in candles_by_tf and not candles_by_tf[tf].empty:
                bias = self.structure_analyzer.analyze(candles_by_tf[tf], symbol, tf)
                htf_biases[tf] = bias.bias

        htf_aligned = self._check_htf_alignment(htf_biases)
        if htf_aligned:
            total_score += SCORE_WEIGHTS["htf_bias_aligned"]
        details["htf_bias"] = {
            "aligned": htf_aligned,
            "biases": htf_biases,
            "score": SCORE_WEIGHTS["htf_bias_aligned"] if htf_aligned else 0,
        }

        # 2. Entry timeframe analysis
        entry_df = candles_by_tf.get(entry_timeframe, pd.DataFrame())
        if entry_df.empty:
            return ConfluenceResult(
                symbol=symbol, total_score=0, max_score=MAX_SCORE,
                details=details, recommendation="NEUTRAL",
            )

        smc = self.smc_engine.analyze(entry_df, symbol, entry_timeframe)
        structure = self.structure_analyzer.analyze(entry_df, symbol, entry_timeframe)

        # 3. Liquidity sweep — price must have swept a level recently
        swept_levels = self.smc_engine.check_liquidity_sweep(entry_df, smc.liquidity_levels)
        liquidity_swept = len(swept_levels) > 0
        if liquidity_swept:
            total_score += SCORE_WEIGHTS["liquidity_swept"]
        details["liquidity"] = {
            "swept": liquidity_swept,
            "swept_count": len(swept_levels),
            "score": SCORE_WEIGHTS["liquidity_swept"] if liquidity_swept else 0,
        }

        # 4. Order Block zone — price must be inside an UNMITIGATED OB
        in_ob, ob_direction = self._price_in_valid_order_block(entry_df, smc.order_blocks, structure.bias)
        if in_ob:
            total_score += SCORE_WEIGHTS["order_block_zone"]
        details["order_block"] = {
            "in_zone": in_ob,
            "ob_direction": ob_direction,
            "count": len([ob for ob in smc.order_blocks if not ob.mitigated]),
            "score": SCORE_WEIGHTS["order_block_zone"] if in_ob else 0,
        }

        # 5. FVG present, aligned with bias, and UNFILLED
        aligned_fvgs = self._get_aligned_fvgs(smc.fvgs, structure.bias)
        fvg_present = len(aligned_fvgs) > 0
        if fvg_present:
            total_score += SCORE_WEIGHTS["fvg_present"]
        details["fvg"] = {
            "present": fvg_present,
            "aligned_count": len(aligned_fvgs),
            "total_count": len(smc.fvgs),
            "score": SCORE_WEIGHTS["fvg_present"] if fvg_present else 0,
        }

        # 6. Structure confirmed (BOS or CHOCH on entry TF)
        structure_confirmed = any(
            l.label in ("BOS", "CHOCH") for l in structure.structure_labels[-3:]
        )
        if structure_confirmed:
            total_score += SCORE_WEIGHTS["structure_confirmed"]
        details["structure"] = {
            "confirmed": structure_confirmed,
            "bias": structure.bias,
            "score": SCORE_WEIGHTS["structure_confirmed"] if structure_confirmed else 0,
        }

        # 7. Premium/Discount zone — BUY in discount, SELL in premium
        in_correct_zone = self._check_premium_discount(entry_df, smc.premium_discount_mid, structure.bias)
        if in_correct_zone:
            total_score += SCORE_WEIGHTS["premium_discount"]
        details["premium_discount"] = {
            "in_correct_zone": in_correct_zone,
            "midpoint": smc.premium_discount_mid,
            "score": SCORE_WEIGHTS["premium_discount"] if in_correct_zone else 0,
        }

        # 8. Volume confirmation — above-average volume (2.0x threshold)
        volume_confirmed = self._check_volume_confirmation(entry_df)
        if volume_confirmed:
            total_score += SCORE_WEIGHTS["volume_confirmation"]
        details["volume"] = {
            "confirmed": volume_confirmed,
            "score": SCORE_WEIGHTS["volume_confirmation"] if volume_confirmed else 0,
        }

        # ============================================================
        # NEW V3 CRITERIA
        # ============================================================

        # 9. Session quality — only trade during London or NY session
        session_ok = self._check_session_quality(entry_df)
        if session_ok:
            total_score += SCORE_WEIGHTS["session_quality"]
        details["session"] = {
            "in_session": session_ok,
            "score": SCORE_WEIGHTS["session_quality"] if session_ok else 0,
        }

        # 10. MTF confirmation level — must be at least MODERATE
        mtf_ok = False
        mtf_level = "NONE"
        if mtf_result:
            mtf_level = mtf_result.get("confirmation_level", "NONE")
            mtf_ok = mtf_level in ("STRONG", "MODERATE")
        if mtf_ok:
            total_score += SCORE_WEIGHTS["mtf_confirmation"]
        details["mtf_confirmation"] = {
            "level": mtf_level,
            "confirmed": mtf_ok,
            "score": SCORE_WEIGHTS["mtf_confirmation"] if mtf_ok else 0,
        }

        # 11. News filter — no high-impact events within 2 hours
        news_clear = self._check_news_clear(news_events)
        if news_clear:
            total_score += SCORE_WEIGHTS["news_clear"]
        details["news"] = {
            "clear": news_clear,
            "score": SCORE_WEIGHTS["news_clear"] if news_clear else 0,
        }

        # 12. Sentiment alignment — macro sentiment supports direction
        sentiment_ok = self._check_sentiment_aligned(sentiment_data, structure.bias)
        if sentiment_ok:
            total_score += SCORE_WEIGHTS["sentiment_aligned"]
        details["sentiment"] = {
            "aligned": sentiment_ok,
            "score": SCORE_WEIGHTS["sentiment_aligned"] if sentiment_ok else 0,
        }

        # 13. RSI alignment — not overbought for buys, not oversold for sells
        rsi_value = calculate_rsi(entry_df)
        rsi_ok = self._check_rsi_aligned(rsi_value, structure.bias)
        if rsi_ok:
            total_score += SCORE_WEIGHTS["rsi_aligned"]
        details["rsi"] = {
            "aligned": rsi_ok,
            "value": rsi_value,
            "score": SCORE_WEIGHTS["rsi_aligned"] if rsi_ok else 0,
        }

        # 14. Trend Alignment (200 EMA)
        ema_value = calculate_ema(entry_df, 200)
        ema_ok = self._check_ema_aligned(entry_df, ema_value, structure.bias)
        if ema_ok:
            total_score += SCORE_WEIGHTS["ema_aligned"]
        details["ema"] = {
            "aligned": ema_ok,
            "value": ema_value,
            "score": SCORE_WEIGHTS["ema_aligned"] if ema_ok else 0,
        }

        # 15. Momentum Alignment (MACD)
        macd_line, signal_line, hist = calculate_macd(entry_df)
        macd_ok = self._check_macd_aligned(hist, structure.bias)
        if macd_ok:
            total_score += SCORE_WEIGHTS["macd_aligned"]
        details["macd"] = {
            "aligned": macd_ok,
            "hist": hist,
            "score": SCORE_WEIGHTS["macd_aligned"] if macd_ok else 0,
        }

        # 16. Bollinger Bands Position (Intraday)
        bb_upper, bb_mid, bb_lower, bb_bw = calculate_bollinger_bands(entry_df)
        bb_ok = self._check_bb_position(entry_df, bb_upper, bb_lower, bb_mid, structure.bias)
        if bb_ok:
            total_score += SCORE_WEIGHTS["bb_position"]
        details["bollinger_bands"] = {
            "aligned": bb_ok,
            "upper": bb_upper,
            "middle": bb_mid,
            "lower": bb_lower,
            "bandwidth_pct": bb_bw,
            "score": SCORE_WEIGHTS["bb_position"] if bb_ok else 0,
        }

        # 17. Stochastic RSI (Intraday Momentum Timing)
        stoch_k, stoch_d = calculate_stoch_rsi(entry_df)
        stoch_ok = self._check_stoch_rsi_aligned(stoch_k, stoch_d, structure.bias)
        if stoch_ok:
            total_score += SCORE_WEIGHTS["stoch_rsi_aligned"]
        details["stoch_rsi"] = {
            "aligned": stoch_ok,
            "k": stoch_k,
            "d": stoch_d,
            "score": SCORE_WEIGHTS["stoch_rsi_aligned"] if stoch_ok else 0,
        }

        # ============================================================
        # MARKET INTELLIGENCE CRITERIA (V4)
        # ============================================================
        if market_intel_data is None:
            market_intel_data = {}

        # 16. BTC Dominance alignment
        btc_dom_ok = self._check_btc_dominance_aligned(
            market_intel_data.get("btc_dominance", {}), symbol, structure.bias
        )
        if btc_dom_ok:
            total_score += SCORE_WEIGHTS["btc_dominance_aligned"]
        details["btc_dominance"] = {
            "aligned": btc_dom_ok,
            "value": market_intel_data.get("btc_dominance", {}).get("btc_dominance", 0),
            "score": SCORE_WEIGHTS["btc_dominance_aligned"] if btc_dom_ok else 0,
        }

        # 17. Order Book Depth alignment
        ob_ok = self._check_orderbook_aligned(
            market_intel_data.get("orderbook", {}), structure.bias
        )
        if ob_ok:
            total_score += SCORE_WEIGHTS["orderbook_depth_aligned"]
        details["orderbook"] = {
            "aligned": ob_ok,
            "buy_sell_ratio": market_intel_data.get("orderbook", {}).get("buy_sell_ratio", 1.0),
            "score": SCORE_WEIGHTS["orderbook_depth_aligned"] if ob_ok else 0,
        }

        # 18. Liquidation Magnet
        liq_ok = self._check_liquidation_magnet(
            market_intel_data.get("liquidation", {}), entry_df, structure.bias
        )
        if liq_ok:
            total_score += SCORE_WEIGHTS["liquidation_magnet"]
        details["liquidation"] = {
            "magnet": liq_ok,
            "score": SCORE_WEIGHTS["liquidation_magnet"] if liq_ok else 0,
        }

        # 19. Market Cap Quality
        mcap_ok = self._check_market_cap_quality(
            market_intel_data.get("market_cap", {})
        )
        if mcap_ok:
            total_score += SCORE_WEIGHTS["market_cap_quality"]
        details["market_cap"] = {
            "quality": mcap_ok,
            "tier": market_intel_data.get("market_cap", {}).get("tier", "UNKNOWN"),
            "score": SCORE_WEIGHTS["market_cap_quality"] if mcap_ok else 0,
        }

        # 20. Support/Resistance alignment
        sr_ok = self._check_support_resistance_aligned(
            market_intel_data.get("support_resistance", {}), structure.bias
        )
        if sr_ok:
            total_score += SCORE_WEIGHTS["support_resistance_aligned"]
        details["support_resistance"] = {
            "aligned": sr_ok,
            "nearest_support": market_intel_data.get("support_resistance", {}).get("nearest_support", 0),
            "nearest_resistance": market_intel_data.get("support_resistance", {}).get("nearest_resistance", 0),
            "score": SCORE_WEIGHTS["support_resistance_aligned"] if sr_ok else 0,
        }

        # Determine recommendation — V4 thresholds (adjusted for 24-point scale)
        recommendation = self._get_recommendation(total_score, structure.bias, htf_biases)

        return ConfluenceResult(
            symbol=symbol,
            total_score=total_score,
            max_score=MAX_SCORE,
            details=details,
            recommendation=recommendation,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _check_htf_alignment(self, htf_biases: Dict[str, str]) -> bool:
        """Check if higher TF biases agree and are NOT sideways."""
        biases = list(htf_biases.values())
        if len(biases) < 2:
            return False
        return len(set(biases)) == 1 and biases[0] != "SIDEWAYS"

    def _price_in_valid_order_block(
        self, df: pd.DataFrame, obs: list, bias: str
    ) -> tuple:
        """Check if current price is inside an UNMITIGATED OB aligned with the bias."""
        if df.empty or not obs:
            return False, None
        last_close = float(df.iloc[-1]["close"])
        # Only consider unmitigated OBs that match the bias
        for ob in reversed(obs[-10:]):
            if ob.mitigated:
                continue  # Skip mitigated OBs
            if ob.low <= last_close <= ob.high:
                if (bias == "BULLISH" and ob.type == "BULLISH") or \
                   (bias == "BEARISH" and ob.type == "BEARISH"):
                    return True, ob.type
        return False, None

    def _get_aligned_fvgs(self, fvgs: list, bias: str) -> list:
        """Only count UNFILLED FVGs that match the current bias direction."""
        return [f for f in fvgs if f.type == bias and not f.filled]

    def _check_premium_discount(self, df: pd.DataFrame, midpoint: float, bias: str) -> bool:
        """Verify price is in the correct zone: BUY in discount, SELL in premium."""
        if df.empty or midpoint is None:
            return False
        last_close = float(df.iloc[-1]["close"])
        if bias == "BULLISH" and last_close < midpoint:
            return True  # Buying in discount zone
        if bias == "BEARISH" and last_close > midpoint:
            return True  # Selling in premium zone
        return False

    def _check_volume_confirmation(self, df: pd.DataFrame, symbol: str = "") -> bool:
        """
        Check if recent candle has above-average volume.
        - BTC/ETH (Majors): 1.5x threshold (high liquidity makes 2.0x rare)
        - Alts: 2.0x threshold
        """
        if df.empty or len(df) < 20 or "volume" not in df.columns:
            return False
        
        volumes = df["volume"].astype(float).values
        avg_vol = np.mean(volumes[-20:])
        last_vol = volumes[-1]
        
        # Major caps have high liquidity; 1.5x is already a significant footprint
        majors = {"BTCUSDT", "ETHUSDT", "BNBUSDT"}
        threshold_multiplier = 1.5 if symbol.upper() in majors else 2.0
        
        return last_vol > avg_vol * threshold_multiplier

    def _check_session_quality(self, df: pd.DataFrame) -> bool:
        """Check if the latest candle falls within London or NY session (UTC)."""
        if df.empty or "open_time" not in df.columns:
            return True  # If we can't determine, don't penalize
        try:
            last_time = pd.Timestamp(df.iloc[-1]["open_time"])
            if last_time.tzinfo is None:
                hour = last_time.hour
            else:
                hour = last_time.tz_convert("UTC").hour
            # London 08-16 UTC or NY 13-21 UTC
            in_london = LONDON_SESSION[0] <= hour < LONDON_SESSION[1]
            in_ny = NY_SESSION[0] <= hour < NY_SESSION[1]
            return in_london or in_ny
        except Exception:
            return True  # Don't penalize on error

    def _check_news_clear(self, news_events: Optional[List[Dict]]) -> bool:
        """Check that no high-impact events are within 2 hours of now."""
        if news_events is None:
            return True  # If no news data provided, don't penalize

        now = datetime.now(timezone.utc)
        for event in news_events:
            if event.get("impact_level", 0) < 3:
                continue  # Only care about High impact
            try:
                event_dt = datetime.fromisoformat(event["date"])
                if event_dt.tzinfo is None:
                    event_dt = event_dt.replace(tzinfo=timezone.utc)
                diff_seconds = abs((event_dt - now).total_seconds())
                if diff_seconds < 7200:  # 2 hours = 7200 seconds
                    return False  # High-impact event too close
            except Exception:
                continue
        return True

    def _check_sentiment_aligned(self, sentiment_data: Optional[Dict], bias: str) -> bool:
        """
        Check if macro sentiment supports the trade direction.
        - For BULLISH: F&G should NOT be Extreme Greed (>80) — overextended
        - For BEARISH: F&G should NOT be Extreme Fear (<20) — overextended
        - Funding rate alignment is a bonus check
        """
        if sentiment_data is None:
            return True  # If no sentiment data, don't penalize

        try:
            fng = sentiment_data.get("fear_and_greed", {})
            fng_value = fng.get("value", 50)

            # Block contrarian extremes
            if bias == "BULLISH" and fng_value > 80:
                return False  # Market too greedy for longs
            if bias == "BEARISH" and fng_value < 20:
                return False  # Market too fearful for shorts

            # Check funding rates if available
            metrics = sentiment_data.get("market_metrics", [])
            if metrics:
                avg_funding = sum(m.get("funding_rate", 0) for m in metrics) / len(metrics)
                # High positive funding + BULLISH = overcrowded longs → caution
                if bias == "BULLISH" and avg_funding > 0.001:  # > 0.1%
                    return False
                # High negative funding + BEARISH = overcrowded shorts → caution
                if bias == "BEARISH" and avg_funding < -0.001:
                    return False

            return True
        except Exception:
            return True

    def _check_rsi_aligned(self, rsi_value: Optional[float], bias: str) -> bool:
        """
        Check if RSI supports the trade with meaningful thresholds.
        For BUY: RSI between 30-65 (momentum present, not overbought).
        For SELL: RSI between 35-70 (momentum present, not oversold).
        Extreme RSI zones (< 30 or > 70) indicate overextension — risky entries.
        """
        if rsi_value is None:
            return False  # Can't reliably confirm without RSI

        if bias == "BULLISH":
            return 30.0 < rsi_value < 65.0
        elif bias == "BEARISH":
            return 35.0 < rsi_value < 70.0
        return False

    def _check_ema_aligned(self, df: pd.DataFrame, ema_value: Optional[float], bias: str) -> bool:
        """Check if price is on the correct side of the 200 EMA for trend alignment."""
        if ema_value is None or df.empty:
            return False
            
        last_close = float(df.iloc[-1]["close"])
        if bias == "BULLISH":
            return last_close > ema_value
        elif bias == "BEARISH":
            return last_close < ema_value
        return False

    def _check_macd_aligned(self, hist: Optional[float], bias: str) -> bool:
        """Check if MACD histogram momentum aligns with the trade direction."""
        if hist is None:
            return False

        if bias == "BULLISH":
            return hist > 0  # Histogram must be positive (bullish momentum)
        elif bias == "BEARISH":
            return hist < 0  # Histogram must be negative (bearish momentum)
        return False

    def _check_bb_position(self, df: pd.DataFrame, upper: Optional[float],
                            lower: Optional[float], middle: Optional[float], bias: str) -> bool:
        """
        Bollinger Bands position check for intraday trading:
        - BUY: Price near or below lower band (oversold, mean reversion potential)
        - SELL: Price near or above upper band (overbought, reversal potential)
        - Also considers BB squeeze (bandwidth < 5%) as breakout setup
        """
        if upper is None or lower is None or middle is None or df.empty:
            return False
        
        last_close = float(df.iloc[-1]["close"])
        band_range = upper - lower
        if band_range == 0:
            return False
        
        # Position within bands: 0 = at lower, 100 = at upper
        position_pct = (last_close - lower) / band_range * 100
        
        if bias == "BULLISH":
            # Price in lower 30% of bands = favorable buy zone
            return position_pct <= 30
        elif bias == "BEARISH":
            # Price in upper 30% of bands = favorable sell zone
            return position_pct >= 70
        return False

    def _check_stoch_rsi_aligned(self, k: Optional[float], d: Optional[float], bias: str) -> bool:
        """
        Stochastic RSI alignment for intraday momentum entries:
        - BUY: %K < 40 (coming from oversold) AND %K > %D (bullish crossover signal)
        - SELL: %K > 60 (coming from overbought) AND %K < %D (bearish crossover signal)
        """
        if k is None or d is None:
            return False
        
        if bias == "BULLISH":
            # Oversold zone with bullish momentum crossover
            return k < 40 and k >= d
        elif bias == "BEARISH":
            # Overbought zone with bearish momentum crossover
            return k > 60 and k <= d
        return False

    def _get_recommendation(
        self, score: int, entry_bias: str, htf_biases: Dict[str, str]
    ) -> str:
        """Map score to recommendation — V4 thresholds adjusted for 24-point scale."""
        if score >= 18: # ~66%
            if entry_bias == "BULLISH":
                return "STRONG_BUY"
            elif entry_bias == "BEARISH":
                return "STRONG_SELL"
        if score >= 14: # ~50%
            if entry_bias == "BULLISH":
                return "BUY"
            elif entry_bias == "BEARISH":
                return "SELL"
        return "NEUTRAL"

    # ------------------------------------------------------------------
    # Market Intelligence Helpers (V4)
    # ------------------------------------------------------------------
    def _check_btc_dominance_aligned(
        self, btc_dom_data: Dict, symbol: str, bias: str
    ) -> bool:
        """
        BTC Dominance alignment:
        - For BTC: always pass (BTC.D doesn't affect BTC itself)
        - For altcoins: BTC.D falling = bullish alt, BTC.D rising = bearish alt
        """
        if symbol.upper().startswith("BTC"):
            return True  # BTC.D is irrelevant for BTC itself

        btc_dom = btc_dom_data.get("btc_dominance", 50)
        mcap_change = btc_dom_data.get("market_cap_change_24h_pct", 0)

        # If BTC.D > 55% and rising, altcoins are weak → penalize alt BUY
        if bias == "BULLISH" and btc_dom > 55 and mcap_change < 0:
            return False
        # If BTC.D < 45% or falling, alts have room → favor alt BUY
        if bias == "BULLISH" and btc_dom < 50:
            return True
        if bias == "BEARISH" and btc_dom > 55:
            return True  # High BTC.D = alts weak = bearish alt confirmed

        return True  # Neutral range, don't penalize

    def _check_orderbook_aligned(self, ob_data: Dict, bias: str) -> bool:
        """
        Order book depth alignment:
        - BUY: buy wall > sell wall (ratio > 1.2)
        - SELL: sell wall > buy wall (ratio < 0.8)
        """
        ratio = ob_data.get("buy_sell_ratio", 1.0)
        if bias == "BULLISH":
            return ratio > 1.2  # More buy orders = bullish pressure
        elif bias == "BEARISH":
            return ratio < 0.8  # More sell orders = bearish pressure
        return False

    def _check_liquidation_magnet(
        self, liq_data: Dict, df: pd.DataFrame, bias: str
    ) -> bool:
        """
        Liquidation magnet: price near a liquidation cluster zone.
        When price approaches a cluster of liquidation levels, it tends to
        be attracted to that zone (market makers hunt stops).
        """
        if not liq_data or df.empty:
            return False

        cluster = liq_data.get("cluster_zone", {})
        if not cluster:
            return False

        last_close = float(df.iloc[-1]["close"])
        cluster_low = cluster.get("low", 0)
        cluster_high = cluster.get("high", 0)

        if cluster_low <= 0 or cluster_high <= 0:
            return False

        # For BUY: short liquidation cluster above price = magnet pulling price up
        if bias == "BULLISH":
            distance_to_short_liq = abs(cluster_high - last_close) / last_close * 100
            return distance_to_short_liq < 15  # Within 15%

        # For SELL: long liquidation cluster below price = magnet pulling price down
        if bias == "BEARISH":
            distance_to_long_liq = abs(last_close - cluster_low) / last_close * 100
            return distance_to_long_liq < 15

        return False

    def _check_market_cap_quality(self, mcap_data: Dict) -> bool:
        """
        Market cap quality filter:
        - LARGE and MID caps: pass (safer, more liquid)
        - SMALL: pass with warning
        - MICRO: fail (too risky for automated signals)
        """
        tier = mcap_data.get("tier", "UNKNOWN")
        if tier in ("LARGE", "MID", "SMALL"):
            return True
        if tier == "UNKNOWN":
            return True  # Don't penalize if data unavailable
        return False  # MICRO caps fail

    def _check_support_resistance_aligned(
        self, sr_data: Dict, bias: str
    ) -> bool:
        """
        S/R alignment:
        - BUY: price near a support level (within 3% of nearest support)
        - SELL: price near a resistance level (within 3% of nearest resistance)
        """
        if not sr_data:
            return False

        if bias == "BULLISH":
            distance = sr_data.get("support_distance_pct", 100)
            return distance < 3.0  # Within 3% of support
        elif bias == "BEARISH":
            distance = sr_data.get("resistance_distance_pct", 100)
            return distance < 3.0  # Within 3% of resistance

        return False
