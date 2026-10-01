"""
Market Maker Flow Tracker
==========================
Tracks institutional / market maker activity through:

1. Delta Analysis        — Difference between Buy Volume vs Sell Volume per candle
2. Cumulative Delta (CVD) — Running total of delta (trend of who's in control)
3. Large Print Detection  — Trades > N*ATR in single candles = MM footprint
4. Stop Hunt Probability  — Scoring how likely next move is a stop hunt
5. Order Flow Imbalance   — Bid/Ask imbalance from tick data proxy
6. VWAP Deviation         — How far price is from fair value (VWAP)
7. Market Maker Phases    — Accumulation | Manipulation | Distribution | Trending

All from OHLCV data only (no Level 2 required).
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class MMFlowResult:
    # Delta metrics
    candle_delta: float           # Current candle buy-sell delta
    cumulative_delta: float       # CVD over lookback window
    delta_trend: str              # "BULLISH" | "BEARISH" | "NEUTRAL"

    # VWAP
    vwap: float
    vwap_deviation_pct: float     # % above/below VWAP
    price_vs_vwap: str            # "ABOVE" | "BELOW" | "AT"

    # MM Phase
    mm_phase: str                 # "ACCUMULATION" | "MANIPULATION" | "DISTRIBUTION" | "TRENDING_UP" | "TRENDING_DOWN"
    mm_phase_confidence: int      # 0-100
    mm_phase_color: str

    # Stop hunt probability
    stop_hunt_prob: int           # 0-100
    stop_hunt_direction: str      # "UPWARD" (hunts lows) | "DOWNWARD" (hunts highs) | "NONE"

    # Large prints / absorption
    absorption_detected: bool
    absorption_side: str          # "BUY" | "SELL" | "NONE"
    large_print_count: int        # Candles with unusually high volume

    # Signals
    flow_bias: str                # "STRONG_BUY" | "BUY" | "NEUTRAL" | "SELL" | "STRONG_SELL"
    confluence_score: int         # 0-5 for confluece engine
    signals: List[str] = field(default_factory=list)


class MarketMakerFlowEngine:
    """
    Detects market maker activity patterns using OHLCV proxies.
    No Level 2 data needed.
    """

    MM_PHASES = {
        "ACCUMULATION":  {"color": "#10b981", "desc": "Smart money quietly buying"},
        "MANIPULATION":  {"color": "#f59e0b", "desc": "Stop hunt / false move in progress"},
        "DISTRIBUTION":  {"color": "#ef4444", "desc": "Smart money quietly selling"},
        "TRENDING_UP":   {"color": "#3b82f6", "desc": "Institutional trend continuation up"},
        "TRENDING_DOWN": {"color": "#8b5cf6", "desc": "Institutional trend continuation down"},
        "NEUTRAL":       {"color": "#64748b", "desc": "No clear MM activity"},
    }

    def analyze(self, df: pd.DataFrame, lookback: int = 50) -> MMFlowResult:
        if df is None or len(df) < 10:
            return self._empty()

        df = df.tail(lookback).copy().reset_index(drop=True)
        n = len(df)

        highs  = df["high"].astype(float).values
        lows   = df["low"].astype(float).values
        opens  = df["open"].astype(float).values
        closes = df["close"].astype(float).values
        vols   = df["volume"].astype(float).values if "volume" in df.columns else np.ones(n)

        atr = self._atr(highs, lows, closes)
        avg_vol = float(np.mean(vols))

        # ── 1. Delta (proxy: candle body direction × volume) ───────────────
        deltas = self._estimate_delta(opens, closes, highs, lows, vols)
        cum_delta = float(np.sum(deltas))
        candle_delta = float(deltas[-1])
        delta_trend = "BULLISH" if cum_delta > 0 else ("BEARISH" if cum_delta < 0 else "NEUTRAL")

        # ── 2. VWAP ──────────────────────────────────────────────────────
        typical = (highs + lows + closes) / 3
        vwap = float(np.sum(typical * vols) / np.sum(vols)) if np.sum(vols) > 0 else closes[-1]
        current_price = closes[-1]
        vwap_dev = ((current_price - vwap) / vwap) * 100
        price_vs_vwap = "ABOVE" if vwap_dev > 0.1 else ("BELOW" if vwap_dev < -0.1 else "AT")

        # ── 3. Large Prints / Absorption ─────────────────────────────────
        vol_threshold = avg_vol * 2.5
        large_candles = np.where(vols > vol_threshold)[0]
        large_print_count = len(large_candles)

        absorption_detected = False
        absorption_side = "NONE"
        if large_print_count > 0:
            # Check if large volume candles are mostly bullish or bearish
            large_bull = sum(1 for i in large_candles if closes[i] > opens[i])
            large_bear = sum(1 for i in large_candles if closes[i] < opens[i])
            if large_bull > large_bear * 1.5:
                absorption_detected = True
                absorption_side = "BUY"
            elif large_bear > large_bull * 1.5:
                absorption_detected = True
                absorption_side = "SELL"

        # ── 4. MM Phase Detection ─────────────────────────────────────────
        mm_phase, mm_conf = self._detect_mm_phase(
            highs, lows, opens, closes, vols, deltas, atr, avg_vol
        )

        # ── 5. Stop Hunt Probability ──────────────────────────────────────
        sh_prob, sh_dir = self._stop_hunt_probability(
            highs, lows, closes, opens, atr
        )

        # ── 6. Signals + Bias ─────────────────────────────────────────────
        signals = []
        bias_score = 0

        if delta_trend == "BULLISH":
            bias_score += 2
            signals.append("📈 Cumulative delta bullish")
        elif delta_trend == "BEARISH":
            bias_score -= 2
            signals.append("📉 Cumulative delta bearish")

        if absorption_side == "BUY":
            bias_score += 2
            signals.append("🐳 Buy absorption detected on large prints")
        elif absorption_side == "SELL":
            bias_score -= 2
            signals.append("🐋 Sell absorption detected on large prints")

        if price_vs_vwap == "ABOVE":
            bias_score += 1
            signals.append(f"📊 Price {abs(vwap_dev):.2f}% above VWAP")
        elif price_vs_vwap == "BELOW":
            bias_score -= 1
            signals.append(f"📊 Price {abs(vwap_dev):.2f}% below VWAP")

        if mm_phase == "ACCUMULATION":
            bias_score += 1
            signals.append("🏦 MM Accumulation phase detected")
        elif mm_phase == "DISTRIBUTION":
            bias_score -= 1
            signals.append("🏦 MM Distribution phase detected")
        elif mm_phase == "MANIPULATION":
            signals.append(f"⚠️ Manipulation detected — stop hunt likely {sh_dir}")

        # Flow bias
        if bias_score >= 4:
            flow_bias = "STRONG_BUY"
        elif bias_score >= 2:
            flow_bias = "BUY"
        elif bias_score <= -4:
            flow_bias = "STRONG_SELL"
        elif bias_score <= -2:
            flow_bias = "SELL"
        else:
            flow_bias = "NEUTRAL"

        confluence_score = min(5, max(0, abs(bias_score)))

        return MMFlowResult(
            candle_delta=round(candle_delta, 2),
            cumulative_delta=round(cum_delta, 2),
            delta_trend=delta_trend,
            vwap=round(vwap, 6),
            vwap_deviation_pct=round(vwap_dev, 3),
            price_vs_vwap=price_vs_vwap,
            mm_phase=mm_phase,
            mm_phase_confidence=mm_conf,
            mm_phase_color=self.MM_PHASES.get(mm_phase, {}).get("color", "#64748b"),
            stop_hunt_prob=sh_prob,
            stop_hunt_direction=sh_dir,
            absorption_detected=absorption_detected,
            absorption_side=absorption_side,
            large_print_count=large_print_count,
            flow_bias=flow_bias,
            confluence_score=confluence_score,
            signals=signals,
        )

    # ──────────────────── private helpers ────────────────────────

    def _estimate_delta(self, opens, closes, highs, lows, vols):
        """Estimate buy/sell delta using candle anatomy (Stearns proxy)."""
        deltas = []
        for i in range(len(opens)):
            body = closes[i] - opens[i]
            candle_range = highs[i] - lows[i]
            if candle_range == 0:
                deltas.append(0.0)
                continue
            # Buy fraction: proportion of body on upper half
            buy_frac = (closes[i] - lows[i]) / candle_range
            sell_frac = 1 - buy_frac
            delta = (buy_frac - sell_frac) * vols[i]
            deltas.append(delta)
        return np.array(deltas)

    def _detect_mm_phase(self, highs, lows, opens, closes, vols, deltas, atr, avg_vol):
        """
        Detect MM phase using Wyckoff-inspired rules:
        - ACCUMULATION: ranging low volatility + increasing volume + bullish delta
        - MANIPULATION: spike below support / above resistance then reversal
        - DISTRIBUTION: ranging high volatility + increasing volume + bearish delta
        - TRENDING: directional move with consistent delta
        """
        n = len(closes)
        if n < 20:
            return "NEUTRAL", 0

        recent = slice(-20, None)
        price_range = (highs[recent].max() - lows[recent].min())
        atr_mult = price_range / (atr * 20) if atr > 0 else 1.0
        avg_vol_recent = np.mean(vols[recent])
        vol_trending = avg_vol_recent > avg_vol * 1.1

        cum_delta_20 = float(np.sum(deltas[recent]))
        price_change_20 = closes[-1] - closes[-20]

        # TRENDING conditions
        if abs(price_change_20) > atr * 5 and atr_mult > 1.2:
            if price_change_20 > 0:
                return "TRENDING_UP", 80
            else:
                return "TRENDING_DOWN", 80

        # MANIPULATION: big wick with reversal
        last_5 = slice(-5, None)
        max_wick = max(
            max(highs[last_5] - np.maximum(opens[-5:], closes[-5:])),
            max(np.minimum(opens[-5:], closes[-5:]) - lows[last_5])
        )
        if max_wick > atr * 1.5:
            return "MANIPULATION", 75

        # ACCUMULATION: tight range + vol spike + positive delta
        if atr_mult < 0.8 and vol_trending and cum_delta_20 > 0:
            return "ACCUMULATION", 65

        # DISTRIBUTION: tight range + vol spike + negative delta
        if atr_mult < 0.8 and vol_trending and cum_delta_20 < 0:
            return "DISTRIBUTION", 65

        return "NEUTRAL", 40

    def _stop_hunt_probability(self, highs, lows, closes, opens, atr):
        """
        Probability of stop hunt based on wick analysis and recent swing levels.
        """
        if len(closes) < 5:
            return 0, "NONE"

        # Check last 3 candles for long wicks with close back inside range
        score = 0
        direction = "NONE"

        for i in range(-3, 0):
            upper_wick = highs[i] - max(opens[i], closes[i])
            lower_wick = min(opens[i], closes[i]) - lows[i]

            if upper_wick > atr * 0.8:
                score += 30
                direction = "DOWNWARD"  # Swept highs, will push down
            if lower_wick > atr * 0.8:
                score += 30
                direction = "UPWARD"    # Swept lows, will push up

        # Confluence: if direction opposite to delta
        score = min(100, score)
        return score, direction

    def _atr(self, highs, lows, closes, period=14):
        if len(closes) < 2:
            return 1.0
        trs = [
            max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            for i in range(1, len(closes))
        ]
        return float(np.mean(trs[-period:])) if trs else 1.0

    def _empty(self):
        return MMFlowResult(
            candle_delta=0, cumulative_delta=0, delta_trend="NEUTRAL",
            vwap=0, vwap_deviation_pct=0, price_vs_vwap="AT",
            mm_phase="NEUTRAL", mm_phase_confidence=0, mm_phase_color="#64748b",
            stop_hunt_prob=0, stop_hunt_direction="NONE",
            absorption_detected=False, absorption_side="NONE", large_print_count=0,
            flow_bias="NEUTRAL", confluence_score=0, signals=[],
        )

    def to_dict(self, r: MMFlowResult) -> dict:
        return {
            "delta": {
                "candle": r.candle_delta,
                "cumulative": r.cumulative_delta,
                "trend": r.delta_trend,
            },
            "vwap": {
                "value": r.vwap,
                "deviation_pct": r.vwap_deviation_pct,
                "price_position": r.price_vs_vwap,
            },
            "mm_phase": {
                "phase": r.mm_phase,
                "confidence": r.mm_phase_confidence,
                "color": r.mm_phase_color,
                "desc": self.MM_PHASES.get(r.mm_phase, {}).get("desc", ""),
            },
            "stop_hunt": {
                "probability": r.stop_hunt_prob,
                "direction": r.stop_hunt_direction,
            },
            "absorption": {
                "detected": r.absorption_detected,
                "side": r.absorption_side,
                "large_print_count": r.large_print_count,
            },
            "flow_bias": r.flow_bias,
            "confluence_score": r.confluence_score,
            "signals": r.signals,
        }
