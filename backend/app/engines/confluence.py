"""
Multi-Timeframe Confluence Engine (V5 — Fibonacci + MACD + RSI)
================================================================
Signal generation is driven exclusively by THREE indicators:
  1. Fibonacci Retracement — price must be near a key Fib level (0.382/0.5/0.618)
  2. MACD               — histogram direction confirms momentum
  3. RSI                — momentum level + divergence confirms reversal/continuation

All other criteria (HTF bias, SMC, session, news, etc.) serve as
CONTEXTUAL FILTERS only — they add confidence weight but do NOT
generate the signal by themselves.

Scoring system (18 pts max):
  --- Signal Generators (12 pts) ---
  fibonacci_zone       : 4 pts — price at key Fib level (0.382/0.5/0.618)
  macd_signal          : 4 pts — MACD histogram aligned + crossover bonus
  rsi_signal           : 4 pts — RSI zone + divergence confirmation
  --- Context Filters (6 pts) ---
  htf_bias_aligned     : 2 pts — 1D + 4H bias agree
  structure_confirmed  : 1 pt  — BOS or CHOCH on entry TF
  volume_confirmation  : 1 pt  — above-average volume
  session_quality      : 1 pt  — London or NY session active
  news_clear           : 1 pt  — no high-impact event within 2h
  Total MAX SCORE: 18 pts

Trade recommendation thresholds:
  STRONG_BUY / STRONG_SELL : score >= 14  AND all 3 signal generators scored > 0
  BUY / SELL                : score >= 10  AND at least 2 signal generators scored > 0
  NEUTRAL                   : otherwise
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.engines.market_structure import MarketStructureAnalyzer
from app.engines.smart_money import SmartMoneyConceptsEngine
from app.schemas.market_data import MarketBias, SmartMoneyAnalysis
from app.schemas.trade_setup import ConfluenceResult
from app.utils.indicators import (
    calculate_rsi, calculate_macd, calculate_fibonacci,
    detect_divergence,
)


TIMEFRAMES = ["1d", "4h", "1h", "15m", "5m"]

# Signal Generator weights (12 pts) + Context Filter weights (6 pts)
SCORE_WEIGHTS = {
    # Signal Generators
    "fibonacci_zone":       4,   # Price at key Fib level (0.382 / 0.5 / 0.618)
    "macd_signal":          4,   # MACD aligned + histogram momentum
    "rsi_signal":           4,   # RSI zone + divergence bonus

    # Context Filters
    "htf_bias_aligned":     2,   # 1D and 4H bias agree
    "structure_confirmed":  1,   # BOS or CHOCH on entry TF
    "volume_confirmation":  1,   # Volume spike confirms move
    "session_quality":      1,   # London / NY session active
    "news_clear":           1,   # No high-impact event within 2h
}

MAX_SCORE = sum(SCORE_WEIGHTS.values())  # 18

# Session windows (UTC hours)
LONDON_SESSION = (8, 16)    # 08:00 - 16:00 UTC
NY_SESSION     = (13, 21)   # 13:00 - 21:00 UTC


class ConfluenceEngine:
    """
    V5 - Signal generated solely by Fibonacci, MACD, and RSI.
    All other criteria are contextual filters that add confidence weight.
    """

    def __init__(self, min_confluence_score: int = 10):
        self.structure_analyzer = MarketStructureAnalyzer()
        self.smc_engine = SmartMoneyConceptsEngine()
        self.min_confluence_score = min_confluence_score

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
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
        Score confluence for a trade setup.

        Signal is driven by Fibonacci, MACD, and RSI.
        Context filters (HTF bias, structure, volume, session, news) add
        additional confidence points but cannot trigger a signal on their own.

        Returns a ConfluenceResult with score, details, and recommendation.
        """
        details: Dict = {}
        total_score = 0
        signal_scores: Dict[str, int] = {}   # track each signal generator score

        # Entry timeframe data
        entry_df = candles_by_tf.get(entry_timeframe, pd.DataFrame())
        if entry_df.empty:
            return ConfluenceResult(
                symbol=symbol, total_score=0, max_score=MAX_SCORE,
                details=details, recommendation="NEUTRAL",
            )

        # Determine dominant HTF bias (for alignment checks)
        htf_biases: Dict[str, str] = {}
        for tf in ["1d", "4h"]:
            df_tf = candles_by_tf.get(tf, pd.DataFrame())
            if not df_tf.empty:
                bias_obj = self.structure_analyzer.analyze(df_tf, symbol, tf)
                htf_biases[tf] = bias_obj.bias

        # Dominant bias: prefer HTF agreement, fall back to entry TF structure
        htf_non_sw = [b for b in htf_biases.values() if b != "SIDEWAYS"]
        if len(htf_non_sw) >= 1 and len(set(htf_non_sw)) == 1:
            dominant_bias = htf_non_sw[0]
        else:
            entry_structure = self.structure_analyzer.analyze(entry_df, symbol, entry_timeframe)
            dominant_bias = entry_structure.bias

        # ==============================================================
        # SIGNAL GENERATOR 1 — FIBONACCI RETRACEMENT
        # ==============================================================
        fib_data = calculate_fibonacci(entry_df, lookback=60)
        fib_score = self._score_fibonacci(fib_data, dominant_bias)
        total_score += fib_score
        signal_scores["fibonacci"] = fib_score
        details["fibonacci"] = {
            "swing_high":            fib_data.get("swing_high"),
            "swing_low":             fib_data.get("swing_low"),
            "direction":             fib_data.get("direction"),
            "retracement_levels":    fib_data.get("retracement_levels", {}),
            "extension_levels":      fib_data.get("extension_levels", {}),
            "price_zone":            fib_data.get("price_zone"),
            "nearest_level":         fib_data.get("nearest_level"),
            "nearest_distance_pct":  fib_data.get("nearest_distance_pct"),
            "is_near_key_level":     fib_data.get("is_near_key_level", False),
            "score":                 fib_score,
            "max":                   SCORE_WEIGHTS["fibonacci_zone"],
        }

        # ==============================================================
        # SIGNAL GENERATOR 2 — MACD
        # ==============================================================
        macd_line, signal_line, hist = calculate_macd(entry_df)
        macd_score = self._score_macd(macd_line, signal_line, hist, dominant_bias)
        total_score += macd_score
        signal_scores["macd"] = macd_score
        details["macd"] = {
            "macd_line":   macd_line,
            "signal_line": signal_line,
            "histogram":   hist,
            "aligned":     macd_score >= 2,
            "crossover":   macd_score == SCORE_WEIGHTS["macd_signal"],
            "score":       macd_score,
            "max":         SCORE_WEIGHTS["macd_signal"],
        }

        # ==============================================================
        # SIGNAL GENERATOR 3 — RSI (with divergence bonus)
        # ==============================================================
        rsi_value = calculate_rsi(entry_df)
        div_data  = detect_divergence(entry_df)
        rsi_score = self._score_rsi(rsi_value, div_data, dominant_bias)
        total_score += rsi_score
        signal_scores["rsi"] = rsi_score
        details["rsi"] = {
            "value":           rsi_value,
            "aligned":         rsi_score >= 2,
            "divergence_type": div_data.get("type", "none"),
            "rsi_divergence":  div_data.get("rsi_divergence", False),
            "macd_divergence": div_data.get("macd_divergence", False),
            "div_strength":    div_data.get("strength", 0),
            "score":           rsi_score,
            "max":             SCORE_WEIGHTS["rsi_signal"],
        }

        # ==============================================================
        # CONTEXT FILTER 1 — HTF Bias Alignment
        # ==============================================================
        htf_aligned = self._check_htf_alignment(htf_biases)
        htf_score   = SCORE_WEIGHTS["htf_bias_aligned"] if htf_aligned else 0
        total_score += htf_score
        details["htf_bias"] = {
            "aligned": htf_aligned,
            "biases":  htf_biases,
            "dominant_bias": dominant_bias,
            "score":   htf_score,
        }

        # ==============================================================
        # CONTEXT FILTER 2 — Market Structure (BOS / CHOCH)
        # ==============================================================
        structure = self.structure_analyzer.analyze(entry_df, symbol, entry_timeframe)
        structure_ok = any(
            l.label in ("BOS", "CHOCH") for l in structure.structure_labels[-3:]
        )
        struct_score = SCORE_WEIGHTS["structure_confirmed"] if structure_ok else 0
        total_score += struct_score
        details["structure"] = {
            "confirmed": structure_ok,
            "bias":      structure.bias,
            "score":     struct_score,
        }

        # ==============================================================
        # CONTEXT FILTER 3 — Volume Confirmation
        # ==============================================================
        volume_ok = self._check_volume_confirmation(entry_df, symbol)
        vol_score = SCORE_WEIGHTS["volume_confirmation"] if volume_ok else 0
        total_score += vol_score
        details["volume"] = {
            "confirmed": volume_ok,
            "score":     vol_score,
        }

        # ==============================================================
        # CONTEXT FILTER 4 — Session Quality
        # ==============================================================
        session_ok = self._check_session_quality(entry_df)
        sess_score = SCORE_WEIGHTS["session_quality"] if session_ok else 0
        total_score += sess_score
        details["session"] = {
            "in_session": session_ok,
            "score":      sess_score,
        }

        # ==============================================================
        # CONTEXT FILTER 5 — News Clear
        # ==============================================================
        news_ok = self._check_news_clear(news_events)
        news_score = SCORE_WEIGHTS["news_clear"] if news_ok else 0
        total_score += news_score
        details["news"] = {
            "clear": news_ok,
            "score": news_score,
        }

        # Final recommendation
        recommendation = self._get_recommendation(
            total_score, dominant_bias, signal_scores
        )

        return ConfluenceResult(
            symbol=symbol,
            total_score=total_score,
            max_score=MAX_SCORE,
            details=details,
            recommendation=recommendation,
        )

    # ------------------------------------------------------------------
    # Signal Generator Scorers
    # ------------------------------------------------------------------

    def _score_fibonacci(self, fib_data: Dict, bias: str) -> int:
        """
        Score Fibonacci signal (0-4 pts).

        4 pts — price within 0.5% of 0.618 (golden ratio) AND bias aligns
        3 pts — price within 1.0% of 0.382 or 0.5 AND bias aligns
        2 pts — price within 2.0% of ANY key level (0.382/0.5/0.618)
        1 pt  — price within 3.0% of any Fib level
        0 pts — not near any key Fib level
        """
        if not fib_data or not fib_data.get("retracement_levels"):
            return 0

        dist = fib_data.get("nearest_distance_pct")
        nearest = fib_data.get("nearest_level")
        fib_dir = fib_data.get("direction")

        if dist is None or nearest is None:
            return 0

        # Bias alignment: fib direction must agree with dominant bias
        bias_aligned = (
            (bias == "BULLISH" and fib_dir == "UP") or
            (bias == "BEARISH" and fib_dir == "DOWN")
        )

        # Golden ratio 0.618 — strongest reversal/continuation level
        if nearest == "0.618" and dist < 0.5 and bias_aligned:
            return 4
        if nearest in ("0.382", "0.5") and dist < 1.0 and bias_aligned:
            return 3
        if nearest in ("0.382", "0.5", "0.618") and dist < 2.0:
            return 2
        if dist < 3.0:
            return 1
        return 0

    def _score_macd(
        self,
        macd_line: Optional[float],
        signal_line: Optional[float],
        hist: Optional[float],
        bias: str,
    ) -> int:
        """
        Score MACD signal (0-4 pts).

        4 pts — histogram aligned + fresh crossover detected
        2 pts — histogram aligned with bias
        0 pts — histogram opposes bias or unavailable
        """
        if hist is None or macd_line is None or signal_line is None:
            return 0

        hist_aligned = (
            (bias == "BULLISH" and hist > 0) or
            (bias == "BEARISH" and hist < 0)
        )

        if not hist_aligned:
            return 0

        # Detect fresh crossover: histogram is in early stage (< 30% of macd range)
        crossover = False
        if bias == "BULLISH" and macd_line > signal_line and macd_line != 0:
            crossover = abs(hist) < abs(macd_line) * 0.3
        elif bias == "BEARISH" and macd_line < signal_line and macd_line != 0:
            crossover = abs(hist) < abs(macd_line) * 0.3

        return SCORE_WEIGHTS["macd_signal"] if crossover else 2

    def _score_rsi(
        self,
        rsi_value: Optional[float],
        div_data: Dict,
        bias: str,
    ) -> int:
        """
        Score RSI signal (0-4 pts).

        4 pts — RSI in ideal zone + both RSI & MACD divergence confirmed
        3 pts — RSI in ideal zone + RSI-only divergence
        2 pts — RSI in ideal zone (no divergence)
        1 pt  — RSI in acceptable zone (not extreme)
        0 pts — RSI extreme or unavailable

        Ideal zones:
          BULLISH: RSI 25-55 (oversold-to-neutral; room to run up)
          BEARISH: RSI 45-75 (overbought-to-neutral; room to fall)
        """
        if rsi_value is None:
            return 0

        rsi_divergence  = div_data.get("rsi_divergence", False)
        macd_divergence = div_data.get("macd_divergence", False)
        div_type        = div_data.get("type", "none")

        # Divergence alignment with bias
        div_aligned = (
            (bias == "BULLISH" and div_type == "bullish") or
            (bias == "BEARISH" and div_type == "bearish")
        )

        in_ideal_zone = False
        in_acceptable_zone = False
        if bias == "BULLISH":
            in_ideal_zone      = 25.0 <= rsi_value <= 55.0
            in_acceptable_zone = 25.0 < rsi_value < 70.0
        elif bias == "BEARISH":
            in_ideal_zone      = 45.0 <= rsi_value <= 75.0
            in_acceptable_zone = 30.0 < rsi_value < 75.0

        if in_ideal_zone and div_aligned and rsi_divergence and macd_divergence:
            return 4
        if in_ideal_zone and div_aligned and rsi_divergence:
            return 3
        if in_ideal_zone:
            return 2
        if in_acceptable_zone:
            return 1
        return 0

    # ------------------------------------------------------------------
    # Context Filter Helpers
    # ------------------------------------------------------------------

    def _check_htf_alignment(self, htf_biases: Dict[str, str]) -> bool:
        """At least one HTF agrees on direction (not all sideways/opposing)."""
        biases = list(htf_biases.values())
        if not biases:
            return False
        if len(biases) == 1:
            return biases[0] != "SIDEWAYS"
        non_sw = [b for b in biases if b != "SIDEWAYS"]
        if not non_sw:
            return False
        if len(non_sw) == 1:
            return True   # 1 directional + 1 sideways = tradeable
        return len(set(non_sw)) == 1   # both must agree

    def _check_volume_confirmation(self, df: pd.DataFrame, symbol: str = "") -> bool:
        """
        Above-average volume confirms the move.
        Thresholds: BTC/ETH/BNB -> 1.3x, Tier2 -> 1.5x, Alts -> 1.8x
        """
        if df.empty or len(df) < 20 or "volume" not in df.columns:
            return False

        volumes = df["volume"].astype(float).values
        avg_vol = np.mean(volumes[-20:])
        last_vol = volumes[-1]

        tier1 = {"BTCUSDT", "ETHUSDT", "BNBUSDT"}
        tier2 = {"SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT"}
        if symbol.upper() in tier1:
            threshold = 1.3
        elif symbol.upper() in tier2:
            threshold = 1.5
        else:
            threshold = 1.8

        return last_vol > avg_vol * threshold

    def _check_session_quality(self, df: pd.DataFrame) -> bool:
        """Trade only during London (08-16 UTC) or NY (13-21 UTC) session."""
        if df.empty or "open_time" not in df.columns:
            return True   # don't penalize if time unavailable
        try:
            last_time = pd.Timestamp(df.iloc[-1]["open_time"])
            hour = last_time.hour if last_time.tzinfo is None else last_time.tz_convert("UTC").hour
            return LONDON_SESSION[0] <= hour < LONDON_SESSION[1] or NY_SESSION[0] <= hour < NY_SESSION[1]
        except Exception:
            return True

    def _check_news_clear(self, news_events: Optional[List[Dict]]) -> bool:
        """No high-impact event within 2 hours of now."""
        if news_events is None:
            return True
        now = datetime.now(timezone.utc)
        for event in news_events:
            if event.get("impact_level", 0) < 3:
                continue
            try:
                event_dt = datetime.fromisoformat(event["date"])
                if event_dt.tzinfo is None:
                    event_dt = event_dt.replace(tzinfo=timezone.utc)
                if abs((event_dt - now).total_seconds()) < 7200:
                    return False
            except Exception:
                continue
        return True

    # ------------------------------------------------------------------
    # Recommendation Logic
    # ------------------------------------------------------------------

    def _get_recommendation(
        self,
        score: int,
        dominant_bias: str,
        signal_scores: Dict[str, int],
    ) -> str:
        """
        Generate recommendation based on score AND signal generator activity.

        STRONG_BUY/STRONG_SELL : score >= 14  AND all 3 generators scored > 0
        BUY/SELL                : score >= 10  AND >= 2 generators scored > 0
        NEUTRAL                 : otherwise
        """
        active_generators = sum(1 for s in signal_scores.values() if s > 0)

        if score >= 14 and active_generators == 3:
            return "STRONG_BUY" if dominant_bias == "BULLISH" else "STRONG_SELL"
        if score >= 10 and active_generators >= 2:
            return "BUY" if dominant_bias == "BULLISH" else "SELL"
        return "NEUTRAL"
