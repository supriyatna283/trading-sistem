"""
Market Structure Analyzer (V3 - Close-Break BOS / CHOCH)
========================================================
Detects swing points (HH, HL, LH, LL) and places Break of Structure (BOS) /
Change of Character (CHOCH) at the exact candle whose CLOSE breaks the prior
swing high or swing low — including live breaks after the most recent confirmed
swing so fresh breakouts/reversals are not delayed by `swing_lookback` bars.
"""

import pandas as pd
import numpy as np
from typing import List, Optional
from app.schemas.market_data import SwingPoint, StructureLabel, MarketBias


class MarketStructureAnalyzer:
    """Analyzes market structure using price action swing points and close breaks."""

    def __init__(self, swing_lookback: int = 5):
        self.swing_lookback = swing_lookback

    def analyze(self, df: pd.DataFrame, symbol: str = "", timeframe: str = "") -> MarketBias:
        """Full market structure analysis producing a MarketBias result."""
        if df.empty or len(df) < self.swing_lookback * 2 + 1:
            return MarketBias(
                symbol=symbol, timeframe=timeframe, bias="SIDEWAYS",
                structure_labels=[], swing_points=[],
            )

        swings = self._find_swing_points(df)
        labels = self._label_structure(swings, df)
        bias = self._determine_bias(labels)

        return MarketBias(
            symbol=symbol,
            timeframe=timeframe,
            bias=bias,
            structure_labels=labels,
            swing_points=swings,
        )

    # ------------------------------------------------------------------
    # Swing point detection (with duplicate plateau suppression)
    # ------------------------------------------------------------------
    def _find_swing_points(self, df: pd.DataFrame) -> List[SwingPoint]:
        """Identify swing highs and lows using local extremes without plateau duplicates."""
        highs = df["high"].astype(float).values
        lows = df["low"].astype(float).values
        n = len(df)
        lb = self.swing_lookback
        swings: List[SwingPoint] = []
        last_high_idx = -lb - 1
        last_low_idx = -lb - 1

        candidates: List[SwingPoint] = []
        for i in range(lb, n - lb):
            win_h = highs[i - lb : i + lb + 1]
            win_l = lows[i - lb : i + lb + 1]

            is_high = (
                highs[i] == max(win_h)
                and highs[i] > min(win_h[:lb])
                and highs[i] > min(win_h[lb + 1 :])
                and (i - last_high_idx) >= lb
            )
            is_low = (
                lows[i] == min(win_l)
                and lows[i] < max(win_l[:lb])
                and lows[i] < max(win_l[lb + 1 :])
                and (i - last_low_idx) >= lb
            )

            time_val = df.iloc[i]["open_time"] if "open_time" in df.columns else None
            if is_high and is_low:
                # Resolve same-bar outside bar by alternating against prior candidate
                if candidates and candidates[-1].type == "HIGH":
                    is_high = False
                else:
                    is_low = False

            if is_high:
                candidates.append(SwingPoint(
                    index=i, price=float(highs[i]), type="HIGH", time=time_val,
                ))
                last_high_idx = i
            elif is_low:
                candidates.append(SwingPoint(
                    index=i, price=float(lows[i]), type="LOW", time=time_val,
                ))
                last_low_idx = i

        # Normalize into alternating HIGH / LOW swings (keep more extreme on consecutive same-type)
        for cand in candidates:
            if not swings:
                swings.append(cand)
            elif swings[-1].type == cand.type:
                if cand.type == "HIGH" and cand.price >= swings[-1].price:
                    swings[-1] = cand
                elif cand.type == "LOW" and cand.price <= swings[-1].price:
                    swings[-1] = cand
            else:
                swings.append(cand)

        return swings

    # ------------------------------------------------------------------
    # Structure labeling (HH / HL / LH / LL + Close-Break BOS / CHOCH)
    # ------------------------------------------------------------------
    def _label_structure(
        self, swings: List[SwingPoint], df: pd.DataFrame
    ) -> List[StructureLabel]:
        """
        1. Label confirmed swing points as HH/HL/LH/LL.
        2. Emit BOS / CHOCH at the first candle whose CLOSE breaks the prior
           swing high (bullish break) or prior swing low (bearish break):
           - Bullish break when prior trend is BULLISH -> BOS
           - Bullish break when prior trend is BEARISH -> CHOCH
           - Bearish break when prior trend is BEARISH -> BOS
           - Bearish break when prior trend is BULLISH -> CHOCH
        3. Also scan bars after the last confirmed swing up to the end of `df`
           so a fresh close break is reported immediately without waiting `lb` bars.
        """
        labels: List[StructureLabel] = []
        if len(swings) < 2:
            return labels

        closes = df["close"].astype(float).values
        has_time = "open_time" in df.columns
        n = len(df)

        prev_high: Optional[SwingPoint] = None
        prev_low: Optional[SwingPoint] = None
        trend = "NEUTRAL"  # "BULLISH" | "BEARISH" | "NEUTRAL"
        broken_high_idx: set[int] = set()
        broken_low_idx: set[int] = set()

        for sw in swings:
            if sw.type == "HIGH":
                if prev_high is not None:
                    s_label = "HH" if sw.price > prev_high.price else "LH"
                    labels.append(StructureLabel(
                        index=sw.index, label=s_label, price=sw.price, time=sw.time,
                    ))

                    if s_label == "HH" and prev_high.index not in broken_high_idx:
                        brk_idx = self._find_close_break(
                            closes, prev_high.index + 1, sw.index, prev_high.price, "UP"
                        )
                        if brk_idx is not None:
                            broken_high_idx.add(prev_high.index)
                            brk_time = df.iloc[brk_idx]["open_time"] if has_time else sw.time
                            brk_label = "CHOCH" if trend == "BEARISH" else "BOS"
                            labels.append(StructureLabel(
                                index=brk_idx,
                                label=brk_label,
                                price=prev_high.price,
                                time=brk_time,
                            ))
                            trend = "BULLISH"
                    elif s_label == "LH" and trend == "NEUTRAL":
                        trend = "BEARISH"
                    elif s_label == "HH" and trend == "NEUTRAL":
                        trend = "BULLISH"
                prev_high = sw

            elif sw.type == "LOW":
                if prev_low is not None:
                    s_label = "HL" if sw.price > prev_low.price else "LL"
                    labels.append(StructureLabel(
                        index=sw.index, label=s_label, price=sw.price, time=sw.time,
                    ))

                    if s_label == "LL" and prev_low.index not in broken_low_idx:
                        brk_idx = self._find_close_break(
                            closes, prev_low.index + 1, sw.index, prev_low.price, "DOWN"
                        )
                        if brk_idx is not None:
                            broken_low_idx.add(prev_low.index)
                            brk_time = df.iloc[brk_idx]["open_time"] if has_time else sw.time
                            brk_label = "CHOCH" if trend == "BULLISH" else "BOS"
                            labels.append(StructureLabel(
                                index=brk_idx,
                                label=brk_label,
                                price=prev_low.price,
                                time=brk_time,
                            ))
                            trend = "BEARISH"
                    elif s_label == "HL" and trend == "NEUTRAL":
                        trend = "BULLISH"
                    elif s_label == "LL" and trend == "NEUTRAL":
                        trend = "BEARISH"
                prev_low = sw

        # ── Live tail scan: detect close break after the last confirmed swing ──
        if prev_high is not None and prev_high.index not in broken_high_idx:
            brk_idx = self._find_close_break(
                closes, prev_high.index + 1, n - 1, prev_high.price, "UP"
            )
            if brk_idx is not None:
                brk_time = df.iloc[brk_idx]["open_time"] if has_time else prev_high.time
                brk_label = "CHOCH" if trend == "BEARISH" else "BOS"
                labels.append(StructureLabel(
                    index=brk_idx, label=brk_label, price=prev_high.price, time=brk_time,
                ))
                trend = "BULLISH"

        if prev_low is not None and prev_low.index not in broken_low_idx:
            brk_idx = self._find_close_break(
                closes, prev_low.index + 1, n - 1, prev_low.price, "DOWN"
            )
            if brk_idx is not None:
                brk_time = df.iloc[brk_idx]["open_time"] if has_time else prev_low.time
                brk_label = "CHOCH" if trend == "BULLISH" else "BOS"
                labels.append(StructureLabel(
                    index=brk_idx, label=brk_label, price=prev_low.price, time=brk_time,
                ))

        labels.sort(key=lambda l: l.index)
        return labels

    @staticmethod
    def _find_close_break(
        closes, start_idx: int, end_idx: int, level: float, direction: str
    ) -> Optional[int]:
        """Return first bar index in [start_idx, end_idx] whose close breaks `level`."""
        if start_idx > end_idx:
            return None
        for k in range(start_idx, end_idx + 1):
            if direction == "UP" and closes[k] > level:
                return k
            if direction == "DOWN" and closes[k] < level:
                return k
        return None

    # ------------------------------------------------------------------
    # Bias determination
    # ------------------------------------------------------------------
    def _determine_bias(self, labels: List[StructureLabel]) -> str:
        """Determine overall market bias from recent structure swings and breaks."""
        if not labels:
            return "SIDEWAYS"

        recent = labels[-6:]
        bullish_count = sum(1 for l in recent if l.label in ("HH", "HL"))
        bearish_count = sum(1 for l in recent if l.label in ("LH", "LL"))

        # Check for recent CHOCH or BOS in the last 3 structure events
        for l in reversed(labels[-3:]):
            if l.label in ("CHOCH", "BOS"):
                # Find the swing or break direction at/near this event
                swings_up_to = [x for x in labels if x.index <= l.index and x.label in ("HH", "HL", "LH", "LL")]
                if swings_up_to:
                    last_sw = swings_up_to[-1]
                    if l.label == "BOS":
                        return "BULLISH" if last_sw.label in ("HH", "HL") else "BEARISH"
                    else:  # CHOCH flips against prior structure if break happened in tail
                        if l.price >= last_sw.price:
                            return "BULLISH"
                        return "BEARISH"

        if bullish_count > bearish_count + 1:
            return "BULLISH"
        elif bearish_count > bullish_count + 1:
            return "BEARISH"
        else:
            return "SIDEWAYS"

    # ------------------------------------------------------------------
    # Multi-timeframe combined bias
    # ------------------------------------------------------------------
    def multi_tf_bias(
        self, analyses: dict[str, MarketBias]
    ) -> dict:
        """Combine biases from multiple timeframes into a summary."""
        biases = {tf: a.bias for tf, a in analyses.items()}
        bullish = sum(1 for b in biases.values() if b == "BULLISH")
        bearish = sum(1 for b in biases.values() if b == "BEARISH")
        total = len(biases)

        if bullish > total / 2:
            overall = "BULLISH"
        elif bearish > total / 2:
            overall = "BEARISH"
        else:
            overall = "SIDEWAYS"

        return {
            "timeframes": biases,
            "overall_bias": overall,
            "bullish_count": bullish,
            "bearish_count": bearish,
        }
