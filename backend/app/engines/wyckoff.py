"""
Wyckoff Pattern Detector
=========================
Implements Richard Wyckoff's Method for identifying:

Accumulation Schematic (Markup setup):
  PS  → Preliminary Support
  SC  → Selling Climax
  AR  → Automatic Rally
  ST  → Secondary Test
  SOT → Spring or Shakeout (optional)
  SOS → Sign of Strength
  LPS → Last Point of Support
  [MARKUP BEGINS]

Distribution Schematic (Markdown setup):
  PSY → Preliminary Supply
  BC  → Buying Climax
  AR  → Automatic Reaction
  ST  → Secondary Test
  UTAD→ Upthrust After Distribution (optional)
  SOW → Sign of Weakness
  LPSY→ Last Point of Supply
  [MARKDOWN BEGINS]

Phase Detection: A → B → C → D → E
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict


@dataclass
class WyckoffEvent:
    """A single Wyckoff schematic event."""
    name: str           # "SC", "AR", "ST", etc.
    bar_idx: int
    price: float
    volume: float
    description: str
    phase: str          # "A" | "B" | "C" | "D" | "E"


@dataclass
class WyckoffResult:
    # Current detection
    schematic: str          # "ACCUMULATION" | "DISTRIBUTION" | "NONE"
    phase: str              # "A" | "B" | "C" | "D" | "E" | "NONE"
    phase_confidence: int   # 0-100
    is_actionable: bool     # In phase C or D = entry opportunity
    signal: str             # "STRONG_BUY" | "BUY" | "NEUTRAL" | "SELL" | "STRONG_SELL"

    # Range boundaries
    trading_range_high: float
    trading_range_low: float
    range_size: float

    # Key events detected
    events: List[WyckoffEvent] = field(default_factory=list)

    # Cause & Effect
    cause_bars: int = 0         # How many bars in trading range (cause)
    effect_projection: float = 0.0  # Projected price target (effect)

    # Spring / UTAD
    spring_detected: bool = False
    utad_detected: bool = False
    spring_price: Optional[float] = None

    description: str = ""
    confluence_score: int = 0


class WyckoffEngine:
    """
    Detects Wyckoff accumulation and distribution schematics from OHLCV data.
    Uses structural analysis: swing highs/lows, volume climaxes, phase transitions.
    """

    def analyze(self, df: pd.DataFrame, lookback: int = 100) -> WyckoffResult:
        if df is None or len(df) < 30:
            return self._empty()

        df = df.tail(lookback).copy().reset_index(drop=True)
        highs  = df["high"].astype(float).values
        lows   = df["low"].astype(float).values
        closes = df["close"].astype(float).values
        vols   = df["volume"].astype(float).values if "volume" in df.columns else np.ones(len(df))
        n = len(df)

        atr     = self._atr(highs, lows, closes)
        avg_vol = float(np.mean(vols))

        # Step 1: Find trading range (support / resistance)
        tr_high, tr_low, tr_start = self._find_trading_range(highs, lows, closes, atr)
        range_size = tr_high - tr_low

        if range_size <= 0 or tr_start < 0:
            return self._empty()

        # Step 2: Classify as Accumulation or Distribution
        schematic = self._classify_schematic(
            closes, vols, tr_high, tr_low, tr_start, avg_vol
        )

        # Step 3: Detect key events
        events = []
        if schematic == "ACCUMULATION":
            events = self._detect_accumulation_events(
                highs, lows, closes, vols, tr_high, tr_low, tr_start, atr, avg_vol
            )
        elif schematic == "DISTRIBUTION":
            events = self._detect_distribution_events(
                highs, lows, closes, vols, tr_high, tr_low, tr_start, atr, avg_vol
            )

        # Step 4: Determine current phase
        phase, phase_conf = self._determine_phase(events, schematic, n)

        # Step 5: Spring / UTAD detection (Phase C)
        spring_detected = False
        utad_detected   = False
        spring_price    = None

        for i in range(tr_start, n):
            if schematic == "ACCUMULATION":
                # Spring: wick below TR low then closes back above
                if lows[i] < tr_low * 0.998 and closes[i] > tr_low:
                    spring_detected = True
                    spring_price    = lows[i]
            elif schematic == "DISTRIBUTION":
                # UTAD: wick above TR high then closes back below
                if highs[i] > tr_high * 1.002 and closes[i] < tr_high:
                    utad_detected = True
                    spring_price  = highs[i]

        # Step 6: Cause & Effect projection
        cause_bars = n - tr_start
        point_count = cause_bars
        if schematic == "ACCUMULATION":
            effect_projection = tr_low + (range_size * point_count / 10)
        elif schematic == "DISTRIBUTION":
            effect_projection = tr_high - (range_size * point_count / 10)
        else:
            effect_projection = closes[-1]

        # Step 7: Signal + Actionability
        is_actionable = phase in ("C", "D")
        if schematic == "ACCUMULATION":
            if phase == "D":
                signal = "STRONG_BUY"
            elif phase == "C" and spring_detected:
                signal = "BUY"
            else:
                signal = "NEUTRAL"
        elif schematic == "DISTRIBUTION":
            if phase == "D":
                signal = "STRONG_SELL"
            elif phase == "C" and utad_detected:
                signal = "SELL"
            else:
                signal = "NEUTRAL"
        else:
            signal = "NEUTRAL"

        # Confluence score
        score = 0
        if schematic != "NONE": score += 1
        if phase in ("C", "D", "E"): score += 2
        if spring_detected or utad_detected: score += 2

        desc_map = {
            "ACCUMULATION": f"Wyckoff Accumulation — Phase {phase}. {'Spring detected! Entry zone active.' if spring_detected else 'Building cause for markup.'}",
            "DISTRIBUTION": f"Wyckoff Distribution — Phase {phase}. {'UTAD detected! Short entry zone.' if utad_detected else 'Building cause for markdown.'}",
            "NONE": "No Wyckoff pattern detected in lookback window.",
        }

        return WyckoffResult(
            schematic=schematic,
            phase=phase,
            phase_confidence=phase_conf,
            is_actionable=is_actionable,
            signal=signal,
            trading_range_high=round(tr_high, 6),
            trading_range_low=round(tr_low, 6),
            range_size=round(range_size, 6),
            events=events,
            cause_bars=cause_bars,
            effect_projection=round(effect_projection, 6),
            spring_detected=spring_detected,
            utad_detected=utad_detected,
            spring_price=round(spring_price, 6) if spring_price else None,
            description=desc_map.get(schematic, ""),
            confluence_score=score,
        )

    # ─────────────────── pattern logic ───────────────────

    def _find_trading_range(self, highs, lows, closes, atr) -> Tuple[float, float, int]:
        """Find the horizontal trading range (tight range = TR)."""
        n = len(closes)
        best_start = -1
        best_range = (0, 0)
        best_consistency = 0

        window = min(40, n // 2)

        for start in range(n - window, n - 10):
            seg_highs = highs[start:]
            seg_lows  = lows[start:]
            h = float(seg_highs.max())
            l = float(seg_lows.min())
            r = h - l
            consistency = 1 - (r / (atr * 20)) if atr > 0 else 0

            if consistency > best_consistency and r > atr * 2:
                best_consistency = consistency
                best_range = (h, l)
                best_start = start

        return best_range[0], best_range[1], best_start

    def _classify_schematic(self, closes, vols, tr_high, tr_low, tr_start, avg_vol):
        """Accumulation vs Distribution based on pre-TR trend + volume."""
        if tr_start <= 0:
            return "NONE"

        # Trend before trading range
        pre_close_start = closes[max(0, tr_start - 20)]
        pre_close_end   = closes[tr_start]
        prior_trend     = pre_close_end - pre_close_start

        # Current price vs midpoint
        mid = (tr_high + tr_low) / 2
        current = closes[-1]

        # Volume trend within TR
        if tr_start < len(vols):
            tr_vols = vols[tr_start:]
            first_half_vol = np.mean(tr_vols[:len(tr_vols)//2]) if len(tr_vols) > 4 else avg_vol
            second_half_vol = np.mean(tr_vols[len(tr_vols)//2:]) if len(tr_vols) > 4 else avg_vol
            vol_increasing = second_half_vol > first_half_vol
        else:
            vol_increasing = False

        # ACCUMULATION: preceded by downtrend + price bottoming + vol spike on lows
        if prior_trend < 0 and current < mid:
            return "ACCUMULATION"
        # DISTRIBUTION: preceded by uptrend + price topping + vol spike on highs
        elif prior_trend > 0 and current > mid:
            return "DISTRIBUTION"
        # Default based on trend
        elif prior_trend < 0:
            return "ACCUMULATION"
        elif prior_trend > 0:
            return "DISTRIBUTION"
        return "NONE"

    def _detect_accumulation_events(
        self, highs, lows, closes, vols, tr_high, tr_low, tr_start, atr, avg_vol
    ) -> List[WyckoffEvent]:
        events = []
        n = len(closes)

        # SC: Selling Climax — highest volume bar near TR low
        max_vol_idx = tr_start + int(np.argmax(vols[tr_start:])) if tr_start < n else 0
        if max_vol_idx < n and lows[max_vol_idx] <= tr_low * 1.02:
            events.append(WyckoffEvent("SC", max_vol_idx, lows[max_vol_idx], vols[max_vol_idx],
                                       "Selling Climax — high volume reversal at low", "A"))

        # AR: Automatic Rally — first strong up move after SC
        if events:
            sc_idx = events[0].bar_idx
            for i in range(sc_idx + 1, min(sc_idx + 15, n)):
                if closes[i] > tr_low + (tr_high - tr_low) * 0.4:
                    events.append(WyckoffEvent("AR", i, closes[i], vols[i],
                                               "Automatic Rally — bounce from SC", "A"))
                    break

        # ST: Secondary Test — re-test of SC low with lower volume
        if len(events) >= 2:
            ar_idx = events[1].bar_idx
            for i in range(ar_idx + 1, min(ar_idx + 20, n)):
                if lows[i] <= tr_low * 1.015 and vols[i] < avg_vol:
                    events.append(WyckoffEvent("ST", i, lows[i], vols[i],
                                               "Secondary Test — low volume re-test of SC", "B"))
                    break

        # SOS: Sign of Strength — strong up move breaking AR high
        for i in range(tr_start + 5, n - 2):
            if highs[i] > tr_high * 0.998 and vols[i] > avg_vol * 1.3:
                events.append(WyckoffEvent("SOS", i, highs[i], vols[i],
                                           "Sign of Strength — breakout above TR high", "D"))
                break

        return events

    def _detect_distribution_events(
        self, highs, lows, closes, vols, tr_high, tr_low, tr_start, atr, avg_vol
    ) -> List[WyckoffEvent]:
        events = []
        n = len(closes)

        # BC: Buying Climax — highest volume near TR high
        max_vol_idx = tr_start + int(np.argmax(vols[tr_start:])) if tr_start < n else 0
        if max_vol_idx < n and highs[max_vol_idx] >= tr_high * 0.98:
            events.append(WyckoffEvent("BC", max_vol_idx, highs[max_vol_idx], vols[max_vol_idx],
                                       "Buying Climax — high volume rejection at high", "A"))

        # AR: Automatic Reaction
        if events:
            bc_idx = events[0].bar_idx
            for i in range(bc_idx + 1, min(bc_idx + 15, n)):
                if closes[i] < tr_high - (tr_high - tr_low) * 0.3:
                    events.append(WyckoffEvent("AR", i, closes[i], vols[i],
                                               "Automatic Reaction — drop from BC", "A"))
                    break

        # ST: Secondary Test
        if len(events) >= 2:
            ar_idx = events[1].bar_idx
            for i in range(ar_idx + 1, min(ar_idx + 20, n)):
                if highs[i] >= tr_high * 0.985 and vols[i] < avg_vol:
                    events.append(WyckoffEvent("ST", i, highs[i], vols[i],
                                               "Secondary Test — low volume re-test of BC", "B"))
                    break

        # SOW: Sign of Weakness — breakdown below TR low
        for i in range(tr_start + 5, n - 2):
            if lows[i] < tr_low * 1.002 and vols[i] > avg_vol * 1.3:
                events.append(WyckoffEvent("SOW", i, lows[i], vols[i],
                                           "Sign of Weakness — breakdown below TR low", "D"))
                break

        return events

    def _determine_phase(self, events: List[WyckoffEvent], schematic: str, n: int) -> Tuple[str, int]:
        """Determine current Wyckoff phase from detected events."""
        if not events:
            return "A", 30

        event_names = [e.name for e in events]
        phases_seen = set(e.phase for e in events)

        if schematic == "ACCUMULATION":
            if "SOS" in event_names:
                return "D", 85
            elif "ST" in event_names:
                return "C", 70
            elif "AR" in event_names:
                return "B", 55
            elif "SC" in event_names:
                return "A", 40
        elif schematic == "DISTRIBUTION":
            if "SOW" in event_names:
                return "D", 85
            elif "ST" in event_names:
                return "C", 70
            elif "AR" in event_names:
                return "B", 55
            elif "BC" in event_names:
                return "A", 40

        return "A", 25

    def _atr(self, highs, lows, closes, period=14):
        if len(closes) < 2:
            return 1.0
        trs = [
            max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            for i in range(1, len(closes))
        ]
        return float(np.mean(trs[-period:])) if trs else 1.0

    def _empty(self):
        return WyckoffResult(
            schematic="NONE", phase="NONE", phase_confidence=0,
            is_actionable=False, signal="NEUTRAL",
            trading_range_high=0, trading_range_low=0, range_size=0,
            events=[], description="Insufficient data for Wyckoff analysis.",
            confluence_score=0,
        )

    def to_dict(self, r: WyckoffResult) -> dict:
        return {
            "schematic":         r.schematic,
            "phase":             r.phase,
            "phase_confidence":  r.phase_confidence,
            "is_actionable":     r.is_actionable,
            "signal":            r.signal,
            "trading_range": {
                "high":          r.trading_range_high,
                "low":           r.trading_range_low,
                "size":          r.range_size,
            },
            "cause_and_effect": {
                "cause_bars":        r.cause_bars,
                "effect_projection": r.effect_projection,
            },
            "spring":            r.spring_detected,
            "utad":              r.utad_detected,
            "spring_price":      r.spring_price,
            "description":       r.description,
            "confluence_score":  r.confluence_score,
            "events": [
                {
                    "name":        e.name,
                    "bar_idx":     e.bar_idx,
                    "price":       e.price,
                    "phase":       e.phase,
                    "description": e.description,
                }
                for e in r.events
            ],
        }
