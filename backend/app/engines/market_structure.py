"""
Market Structure Analyzer
=========================
Detects swing points (HH, HL, LH, LL), Break of Structure (BOS),
Change of Character (CHOCH), and Market Structure Shift (MSS).
Determines market bias (Bullish / Bearish / Sideways).
"""

import pandas as pd
import numpy as np
from typing import List, Tuple
from app.schemas.market_data import SwingPoint, StructureLabel, MarketBias


class MarketStructureAnalyzer:
    """Analyzes market structure using price action swing points."""

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
    # Swing point detection
    # ------------------------------------------------------------------
    def _find_swing_points(self, df: pd.DataFrame) -> List[SwingPoint]:
        """Identify swing highs and lows using local extremes."""
        highs = df["high"].values
        lows = df["low"].values
        n = len(df)
        lb = self.swing_lookback
        swings: List[SwingPoint] = []

        for i in range(lb, n - lb):
            # Swing High: high[i] is the max of the surrounding window
            if highs[i] == max(highs[i - lb : i + lb + 1]):
                time_val = df.iloc[i]["open_time"] if "open_time" in df.columns else None
                swings.append(SwingPoint(
                    index=i, price=float(highs[i]), type="HIGH",
                    time=time_val,
                ))
            # Swing Low: low[i] is the min of the surrounding window
            if lows[i] == min(lows[i - lb : i + lb + 1]):
                time_val = df.iloc[i]["open_time"] if "open_time" in df.columns else None
                swings.append(SwingPoint(
                    index=i, price=float(lows[i]), type="LOW",
                    time=time_val,
                ))

        # Sort by index
        swings.sort(key=lambda s: s.index)
        return swings

    # ------------------------------------------------------------------
    # Structure labeling (HH / HL / LH / LL / BOS / CHOCH)
    # ------------------------------------------------------------------
    def _label_structure(
        self, swings: List[SwingPoint], df: pd.DataFrame
    ) -> List[StructureLabel]:
        """Label swing points as HH/HL/LH/LL and detect BOS/CHOCH."""
        labels: List[StructureLabel] = []
        if len(swings) < 2:
            return labels

        prev_high: SwingPoint | None = None
        prev_low: SwingPoint | None = None
        prev_trend = "NEUTRAL"

        for sw in swings:
            if sw.type == "HIGH":
                if prev_high is not None:
                    if sw.price > prev_high.price:
                        label = "HH"
                    else:
                        label = "LH"
                    labels.append(StructureLabel(
                        index=sw.index, label=label,
                        price=sw.price, time=sw.time,
                    ))

                    # Check for CHOCH / BOS
                    new_trend = "BULLISH" if label == "HH" else "BEARISH"
                    if prev_trend != "NEUTRAL" and new_trend != prev_trend:
                        labels.append(StructureLabel(
                            index=sw.index, label="CHOCH",
                            price=sw.price, time=sw.time,
                        ))
                    elif prev_trend == new_trend and label == "HH":
                        # BOS = continuation beyond the last high (only on HH)
                        labels.append(StructureLabel(
                            index=sw.index, label="BOS",
                            price=sw.price, time=sw.time,
                        ))
                    prev_trend = new_trend
                prev_high = sw

            elif sw.type == "LOW":
                if prev_low is not None:
                    if sw.price > prev_low.price:
                        label = "HL"
                    else:
                        label = "LL"
                    labels.append(StructureLabel(
                        index=sw.index, label=label,
                        price=sw.price, time=sw.time,
                    ))

                    new_trend = "BULLISH" if label == "HL" else "BEARISH"
                    if prev_trend != "NEUTRAL" and new_trend != prev_trend:
                        labels.append(StructureLabel(
                            index=sw.index, label="CHOCH",
                            price=sw.price, time=sw.time,
                        ))
                    prev_trend = new_trend
                prev_low = sw

        return labels

    # ------------------------------------------------------------------
    # Bias determination
    # ------------------------------------------------------------------
    def _determine_bias(self, labels: List[StructureLabel]) -> str:
        """Determine overall market bias from the last several structure labels."""
        if not labels:
            return "SIDEWAYS"

        # Take the last 6 labels to determine the current market phase
        recent = labels[-6:]
        bullish_count = sum(1 for l in recent if l.label in ("HH", "HL"))
        bearish_count = sum(1 for l in recent if l.label in ("LH", "LL"))

        # Check for recent CHOCH — indicates a potential shift
        has_recent_choch = any(l.label == "CHOCH" for l in labels[-3:])

        if has_recent_choch:
            # If CHOCH occurred recently, the bias just shifted
            last_label = [l for l in recent if l.label in ("HH", "HL", "LH", "LL")]
            if last_label:
                if last_label[-1].label in ("HH", "HL"):
                    return "BULLISH"
                else:
                    return "BEARISH"
            return "SIDEWAYS"

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
