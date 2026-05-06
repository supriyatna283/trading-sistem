"""
Custom Strategy Builder Engine (V2)
======================================
Allows composing strategies from toggleable indicator blocks.
Each block has configurable parameters and returns pass/fail + reason.

V2: Added session_filter, news_filter, sentiment_filter blocks.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from app.engines.market_structure import MarketStructureAnalyzer
from app.engines.smart_money import SmartMoneyConceptsEngine


# Session windows (UTC hours)
LONDON_SESSION = (8, 16)
NY_SESSION = (13, 21)

# --- Available Blocks ---
AVAILABLE_BLOCKS = {
    "htf_bias": {
        "name": "HTF Bias Alignment",
        "description": "1D and 4H timeframes must agree on direction",
        "category": "structure",
        "params": {
            "required_tfs": {"type": "list", "default": ["1d", "4h"], "options": ["1d", "4h", "1h"]},
        },
    },
    "order_block": {
        "name": "Order Block Zone",
        "description": "Price must be inside an unmitigated Order Block",
        "category": "smc",
        "params": {
            "min_body_ratio": {"type": "float", "default": 0.5, "min": 0.3, "max": 0.95},
        },
    },
    "fvg": {
        "name": "Fair Value Gap",
        "description": "An unfilled Fair Value Gap must exist in the trade direction",
        "category": "smc",
        "params": {
            "min_gap_atr_ratio": {"type": "float", "default": 0.3, "min": 0.1, "max": 2.0},
        },
    },
    "liquidity_sweep": {
        "name": "Liquidity Sweep",
        "description": "Price must have swept a liquidity level before entry",
        "category": "smc",
        "params": {
            "lookback": {"type": "int", "default": 20, "min": 5, "max": 50},
        },
    },
    "bos_choch": {
        "name": "Structure Break (BOS/CHOCH)",
        "description": "A Break of Structure or Change of Character must be present",
        "category": "structure",
        "params": {
            "lookback_candles": {"type": "int", "default": 5, "min": 2, "max": 15},
        },
    },
    "premium_discount": {
        "name": "Premium/Discount Zone",
        "description": "Buy in discount zone, sell in premium zone",
        "category": "smc",
        "params": {},
    },
    "volume_spike": {
        "name": "Volume Confirmation",
        "description": "Recent candle must have above-average volume",
        "category": "volume",
        "params": {
            "multiplier": {"type": "float", "default": 2.0, "min": 1.1, "max": 3.0},
            "lookback": {"type": "int", "default": 20, "min": 10, "max": 50},
        },
    },
    "rsi_filter": {
        "name": "RSI Filter",
        "description": "RSI must be in oversold (BUY) or overbought (SELL) zone",
        "category": "indicator",
        "params": {
            "period": {"type": "int", "default": 14, "min": 5, "max": 30},
            "oversold": {"type": "int", "default": 30, "min": 15, "max": 40},
            "overbought": {"type": "int", "default": 70, "min": 60, "max": 85},
        },
    },
    "session_filter": {
        "name": "Session Filter",
        "description": "Only trade during London or New York active sessions",
        "category": "timing",
        "params": {
            "sessions": {"type": "list", "default": ["london", "ny"], "options": ["london", "ny", "asia"]},
        },
    },
    "news_filter": {
        "name": "News Event Filter",
        "description": "Block signals near high-impact economic events",
        "category": "timing",
        "params": {
            "buffer_hours": {"type": "int", "default": 2, "min": 1, "max": 6},
        },
    },
    "sentiment_filter": {
        "name": "Sentiment Alignment",
        "description": "Check Fear & Greed Index and funding rates alignment",
        "category": "macro",
        "params": {
            "extreme_fear_threshold": {"type": "int", "default": 20, "min": 10, "max": 30},
            "extreme_greed_threshold": {"type": "int", "default": 80, "min": 70, "max": 90},
        },
    },
}

DEFAULT_STRATEGY = {
    "name": "Default SMC Strategy V3",
    "description": "Smart Money Concepts strategy with full confluence + macro filters",
    "min_score": 8,
    "blocks": [
        {"id": "htf_bias", "enabled": True, "weight": 2, "params": {}},
        {"id": "order_block", "enabled": True, "weight": 2, "params": {}},
        {"id": "fvg", "enabled": True, "weight": 1, "params": {}},
        {"id": "liquidity_sweep", "enabled": True, "weight": 2, "params": {}},
        {"id": "bos_choch", "enabled": True, "weight": 1, "params": {}},
        {"id": "premium_discount", "enabled": True, "weight": 1, "params": {}},
        {"id": "volume_spike", "enabled": True, "weight": 1, "params": {}},
        {"id": "session_filter", "enabled": True, "weight": 1, "params": {}},
        {"id": "news_filter", "enabled": True, "weight": 1, "params": {}},
        {"id": "sentiment_filter", "enabled": True, "weight": 1, "params": {}},
    ],
}


class StrategyBuilderEngine:
    """Evaluates custom strategies against live market data."""

    def __init__(self):
        self.structure = MarketStructureAnalyzer()
        self.smc = SmartMoneyConceptsEngine()

    def get_available_blocks(self) -> List[Dict]:
        """Return the catalogue of available indicator blocks."""
        result = []
        for block_id, info in AVAILABLE_BLOCKS.items():
            result.append({"id": block_id, **info})
        return result

    def evaluate(
        self,
        strategy: Dict[str, Any],
        candles_by_tf: Dict[str, pd.DataFrame],
        symbol: str = "",
        entry_tf: str = "1h",
        news_events: Optional[List[Dict]] = None,
        sentiment_data: Optional[Dict] = None,
    ) -> Dict:
        """
        Evaluate a strategy config against real candle data.
        Returns: score, max_score, pass/fail per block, recommendation.
        """
        blocks = [b for b in strategy.get("blocks", []) if b.get("enabled", True)]
        min_score = strategy.get("min_score", 8)

        entry_df = candles_by_tf.get(entry_tf, pd.DataFrame())
        if entry_df.empty:
            return self._empty_result(symbol, strategy)

        smc_result = self.smc.analyze(entry_df, symbol, entry_tf)
        structure_result = self.structure.analyze(entry_df, symbol, entry_tf)

        total_score = 0
        max_score = 0
        block_results = []

        for block in blocks:
            block_id = block.get("id")
            weight = block.get("weight", 1)
            params = block.get("params", {})
            max_score += weight

            passed, reason = self._evaluate_block(
                block_id, params, candles_by_tf, entry_df,
                smc_result, structure_result, entry_tf,
                news_events=news_events, sentiment_data=sentiment_data,
            )

            if passed:
                total_score += weight

            block_results.append({
                "id": block_id,
                "name": AVAILABLE_BLOCKS.get(block_id, {}).get("name", block_id),
                "passed": passed,
                "reason": reason,
                "weight": weight,
                "score": weight if passed else 0,
            })

        recommendation = self._get_recommendation(
            total_score, min_score, structure_result.bias
        )

        return {
            "symbol": symbol,
            "entry_tf": entry_tf,
            "strategy_name": strategy.get("name", "Custom"),
            "total_score": total_score,
            "max_score": max_score,
            "min_score": min_score,
            "passed": total_score >= min_score,
            "recommendation": recommendation,
            "block_results": block_results,
            "bias": structure_result.bias,
        }

    def _evaluate_block(
        self, block_id: str, params: Dict,
        candles_by_tf: Dict, entry_df: pd.DataFrame,
        smc_result, structure_result, entry_tf: str,
        news_events: Optional[List[Dict]] = None,
        sentiment_data: Optional[Dict] = None,
    ):
        """Evaluate a single block. Returns (passed: bool, reason: str)."""
        try:
            if block_id == "htf_bias":
                required_tfs = params.get("required_tfs", ["1d", "4h"])
                htf_biases = {}
                for tf in required_tfs:
                    df = candles_by_tf.get(tf)
                    if df is not None and not df.empty:
                        b = self.structure.analyze(df, "", tf)
                        htf_biases[tf] = b.bias
                aligned = len(set(htf_biases.values())) == 1 and list(htf_biases.values())[0] != "SIDEWAYS"
                return aligned, f"HTF biases: {htf_biases}"

            elif block_id == "order_block":
                if entry_df.empty or not smc_result.order_blocks:
                    return False, "No order blocks found"
                # Only consider unmitigated OBs
                valid_obs = [ob for ob in smc_result.order_blocks if not ob.mitigated]
                if not valid_obs:
                    return False, "All OBs are mitigated"
                last_close = float(entry_df.iloc[-1]["close"])
                for ob in reversed(valid_obs[-10:]):
                    if ob.low <= last_close <= ob.high:
                        return True, f"Price in fresh {ob.type} OB ({ob.low:.4f}–{ob.high:.4f})"
                return False, f"Price not in any unmitigated OB zone ({len(valid_obs)} fresh OBs)"

            elif block_id == "fvg":
                # Only count unfilled FVGs aligned with bias
                aligned = [f for f in smc_result.fvgs
                          if f.type == structure_result.bias and not f.filled]
                passed = len(aligned) > 0
                return passed, f"{len(aligned)} unfilled aligned FVGs" if passed else "No unfilled aligned FVGs"

            elif block_id == "liquidity_sweep":
                swept = self.smc.check_liquidity_sweep(entry_df, smc_result.liquidity_levels)
                return len(swept) > 0, f"{len(swept)} levels swept" if swept else "No sweep detected"

            elif block_id == "bos_choch":
                lookback = params.get("lookback_candles", 5)
                labels = [l.label for l in structure_result.structure_labels[-lookback:]]
                has_event = "BOS" in labels or "CHOCH" in labels
                event = "BOS" if "BOS" in labels else ("CHOCH" if "CHOCH" in labels else "none")
                return has_event, f"Recent structure event: {event}"

            elif block_id == "premium_discount":
                if entry_df.empty or smc_result.premium_discount_mid is None:
                    return False, "Cannot determine zone"
                last_close = float(entry_df.iloc[-1]["close"])
                mid = smc_result.premium_discount_mid
                bias = structure_result.bias
                if bias == "BULLISH" and last_close < mid:
                    return True, f"Price in discount ({last_close:.4f} < mid {mid:.4f})"
                if bias == "BEARISH" and last_close > mid:
                    return True, f"Price in premium ({last_close:.4f} > mid {mid:.4f})"
                zone = "discount" if last_close < mid else "premium"
                return False, f"Price in {zone} but bias is {bias}"

            elif block_id == "volume_spike":
                multiplier = params.get("multiplier", 2.0)
                lookback = params.get("lookback", 20)
                if "volume" not in entry_df.columns or len(entry_df) < lookback:
                    return False, "Insufficient volume data"
                vols = entry_df["volume"].astype(float).values
                avg = np.mean(vols[-lookback:])
                last = vols[-1]
                ratio = round(last / avg, 2) if avg > 0 else 0
                passed = ratio >= multiplier
                return passed, f"Volume ratio: {ratio}x (need {multiplier}x)"

            elif block_id == "rsi_filter":
                period = params.get("period", 14)
                oversold = params.get("oversold", 30)
                overbought = params.get("overbought", 70)
                rsi = self._calc_rsi(entry_df, period)
                if rsi is None:
                    return False, "Could not calculate RSI"
                bias = structure_result.bias
                if bias == "BULLISH" and rsi <= oversold:
                    return True, f"RSI {rsi:.1f} in oversold zone"
                if bias == "BEARISH" and rsi >= overbought:
                    return True, f"RSI {rsi:.1f} in overbought zone"
                return False, f"RSI {rsi:.1f} not in required zone for {bias}"

            elif block_id == "session_filter":
                return self._evaluate_session_filter(entry_df, params)

            elif block_id == "news_filter":
                return self._evaluate_news_filter(news_events, params)

            elif block_id == "sentiment_filter":
                return self._evaluate_sentiment_filter(
                    sentiment_data, structure_result.bias, params
                )

            return False, f"Unknown block: {block_id}"
        except Exception as e:
            return False, f"Error: {e}"

    # ------------------------------------------------------------------
    # New V2 Block Evaluators
    # ------------------------------------------------------------------
    def _evaluate_session_filter(self, entry_df: pd.DataFrame, params: Dict):
        """Check if current time is within active trading sessions."""
        if entry_df.empty or "open_time" not in entry_df.columns:
            return True, "Cannot determine session, allowing"
        try:
            last_time = pd.Timestamp(entry_df.iloc[-1]["open_time"])
            if last_time.tzinfo is None:
                hour = last_time.hour
            else:
                hour = last_time.tz_convert("UTC").hour

            sessions = params.get("sessions", ["london", "ny"])
            session_ranges = {
                "london": LONDON_SESSION,
                "ny": NY_SESSION,
                "asia": (0, 8),  # 00:00 - 08:00 UTC
            }
            for sess in sessions:
                start, end = session_ranges.get(sess, (0, 24))
                if start <= hour < end:
                    return True, f"In {sess.upper()} session (hour={hour} UTC)"
            return False, f"Outside active sessions (hour={hour} UTC)"
        except Exception as e:
            return True, f"Session check error: {e}"

    def _evaluate_news_filter(self, news_events: Optional[List[Dict]], params: Dict):
        """Check that no high-impact news is within buffer_hours."""
        if news_events is None:
            return True, "No news data available, allowing"

        buffer_hours = params.get("buffer_hours", 2)
        buffer_seconds = buffer_hours * 3600
        now = datetime.now(timezone.utc)

        for event in news_events:
            if event.get("impact_level", 0) < 3:
                continue
            try:
                event_dt = datetime.fromisoformat(event["date"])
                if event_dt.tzinfo is None:
                    event_dt = event_dt.replace(tzinfo=timezone.utc)
                diff = abs((event_dt - now).total_seconds())
                if diff < buffer_seconds:
                    return False, f"High-impact: '{event.get('title', 'Unknown')}' within {buffer_hours}h"
            except Exception:
                continue
        return True, f"No high-impact news within {buffer_hours}h"

    def _evaluate_sentiment_filter(
        self, sentiment_data: Optional[Dict], bias: str, params: Dict
    ):
        """Check macro sentiment alignment."""
        if sentiment_data is None:
            return True, "No sentiment data available, allowing"

        try:
            fng = sentiment_data.get("fear_and_greed", {})
            fng_value = fng.get("value", 50)
            fear_threshold = params.get("extreme_fear_threshold", 20)
            greed_threshold = params.get("extreme_greed_threshold", 80)

            if bias == "BULLISH" and fng_value > greed_threshold:
                return False, f"F&G {fng_value} (Extreme Greed) — too risky for longs"
            if bias == "BEARISH" and fng_value < fear_threshold:
                return False, f"F&G {fng_value} (Extreme Fear) — too risky for shorts"

            # Check funding
            metrics = sentiment_data.get("market_metrics", [])
            if metrics:
                avg_funding = sum(m.get("funding_rate", 0) for m in metrics) / len(metrics)
                if bias == "BULLISH" and avg_funding > 0.001:
                    return False, f"Avg funding {avg_funding:.4f} — overcrowded longs"
                if bias == "BEARISH" and avg_funding < -0.001:
                    return False, f"Avg funding {avg_funding:.4f} — overcrowded shorts"

            return True, f"F&G: {fng_value} ({fng.get('classification', 'N/A')})"
        except Exception as e:
            return True, f"Sentiment check error: {e}"

    # ------------------------------------------------------------------
    # Shared utilities
    # ------------------------------------------------------------------
    def _calc_rsi(self, df: pd.DataFrame, period: int = 14) -> Optional[float]:
        if len(df) < period + 1:
            return None
        closes = df["close"].astype(float).values
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 2)

    def _get_recommendation(self, score: int, min_score: int, bias: str) -> str:
        if score < min_score:
            return "NEUTRAL"
        if bias == "BULLISH":
            return "BUY" if score < min_score + 2 else "STRONG_BUY"
        if bias == "BEARISH":
            return "SELL" if score < min_score + 2 else "STRONG_SELL"
        return "NEUTRAL"

    def _empty_result(self, symbol: str, strategy: Dict) -> Dict:
        return {
            "symbol": symbol,
            "strategy_name": strategy.get("name", "Custom"),
            "total_score": 0,
            "max_score": 0,
            "min_score": strategy.get("min_score", 8),
            "passed": False,
            "recommendation": "NEUTRAL",
            "block_results": [],
            "bias": "SIDEWAYS",
        }
