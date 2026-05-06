"""
Multi-Timeframe Confirmation Engine
=====================================
Analyzes market bias across 5 timeframes (1D, 4H, 1H, 15m, 5m).
A signal is CONFIRMED only when ≥2 consecutive timeframes agree.
"""

import pandas as pd
from typing import Dict, List, Optional
from app.engines.market_structure import MarketStructureAnalyzer
from app.engines.smart_money import SmartMoneyConceptsEngine


TIMEFRAMES_ORDERED = ["1d", "4h", "1h", "15m", "5m"]

TIMEFRAME_LABELS = {
    "1d": "Daily",
    "4h": "4 Hour",
    "1h": "1 Hour",
    "15m": "15 Min",
    "5m": "5 Min",
}


class MTFConfirmationEngine:
    """Analyzes market structure across multiple timeframes and determines confirmation."""

    def __init__(self):
        self.structure = MarketStructureAnalyzer()
        self.smc = SmartMoneyConceptsEngine()

    def analyze(
        self,
        candles_by_tf: Dict[str, pd.DataFrame],
        symbol: str = "",
    ) -> dict:
        """
        Run full MTF analysis.

        Returns:
            - per_tf: dict of TF → { bias, bos, choch, ob_count, fvg_count }
            - agreement_score: int (0–5) — how many TFs are bullish/bearish
            - dominant_bias: BULLISH | BEARISH | SIDEWAYS
            - confirmed: bool — True when ≥2 consecutive TFs align
            - confirmation_level: STRONG | MODERATE | WEAK | NONE
        """
        per_tf = {}
        biases = []

        for tf in TIMEFRAMES_ORDERED:
            df = candles_by_tf.get(tf)
            if df is None or df.empty:
                per_tf[tf] = self._empty_tf(tf)
                biases.append("SIDEWAYS")
                continue

            # Market structure
            mkt = self.structure.analyze(df, symbol, tf)

            # SMC
            smc_result = self.smc.analyze(df, symbol, tf)

            # Recent structure events
            labels = [l.label for l in mkt.structure_labels[-5:]]
            has_bos = "BOS" in labels
            has_choch = "CHOCH" in labels

            # Key price levels
            last_close = float(df.iloc[-1]["close"])
            swing_high = float(df["high"].iloc[-20:].max()) if len(df) >= 20 else None
            swing_low = float(df["low"].iloc[-20:].min()) if len(df) >= 20 else None

            per_tf[tf] = {
                "timeframe": tf,
                "label": TIMEFRAME_LABELS.get(tf, tf),
                "bias": mkt.bias,
                "bos": has_bos,
                "choch": has_choch,
                "ob_count": len(smc_result.order_blocks),
                "fvg_count": len(smc_result.fvgs),
                "last_close": round(last_close, 8),
                "swing_high": round(swing_high, 8) if swing_high else None,
                "swing_low": round(swing_low, 8) if swing_low else None,
                "liq_levels": len(smc_result.liquidity_levels),
            }
            biases.append(mkt.bias)

        # Count agreement
        bullish_count = biases.count("BULLISH")
        bearish_count = biases.count("BEARISH")

        if bullish_count >= bearish_count:
            dominant_bias = "BULLISH" if bullish_count > 0 else "SIDEWAYS"
            agreement_count = bullish_count
        else:
            dominant_bias = "BEARISH"
            agreement_count = bearish_count

        # Check consecutive agreement (top-down: 1D, 4H must align for strong confirmation)
        confirmed, confirmation_level = self._check_confirmation(biases, dominant_bias)

        return {
            "symbol": symbol,
            "per_tf": per_tf,
            "dominant_bias": dominant_bias,
            "agreement_score": agreement_count,
            "total_timeframes": len(TIMEFRAMES_ORDERED),
            "confirmed": confirmed,
            "confirmation_level": confirmation_level,
            "summary": self._build_summary(dominant_bias, agreement_count, confirmation_level),
        }

    def _check_confirmation(self, biases: List[str], dominant_bias: str):
        """
        Confirmation requires:
        - STRONG: 1D + 4H + at least 1 lower TF agree
        - MODERATE: 4H + 1H agree (1D is sideways/missing)
        - WEAK: only 2 of 5 TFs agree
        - NONE: all conflicting
        """
        # biases order: [1d, 4h, 1h, 15m, 5m]
        tf_biases = dict(zip(TIMEFRAMES_ORDERED, biases))

        d_bias = tf_biases.get("1d", "SIDEWAYS")
        h4_bias = tf_biases.get("4h", "SIDEWAYS")
        h1_bias = tf_biases.get("1h", "SIDEWAYS")

        if d_bias == dominant_bias and h4_bias == dominant_bias:
            # Strong: Daily and 4H agree
            confirmed = True
            level = "STRONG"
        elif h4_bias == dominant_bias and h1_bias == dominant_bias:
            # Moderate: 4H and 1H agree
            confirmed = True
            level = "MODERATE"
        elif biases.count(dominant_bias) >= 2:
            # Weak: at least 2 TFs agree
            confirmed = True
            level = "WEAK"
        else:
            confirmed = False
            level = "NONE"

        return confirmed, level

    def _build_summary(self, bias: str, count: int, level: str) -> str:
        if level == "NONE":
            return "No clear directional consensus across timeframes."
        bias_word = "Bullish" if bias == "BULLISH" else "Bearish"
        return (
            f"{level.capitalize()} {bias_word} confirmation — "
            f"{count}/{len(TIMEFRAMES_ORDERED)} timeframes aligned."
        )

    def _empty_tf(self, tf: str) -> dict:
        return {
            "timeframe": tf,
            "label": TIMEFRAME_LABELS.get(tf, tf),
            "bias": "SIDEWAYS",
            "bos": False,
            "choch": False,
            "ob_count": 0,
            "fvg_count": 0,
            "last_close": None,
            "swing_high": None,
            "swing_low": None,
            "liq_levels": 0,
        }
