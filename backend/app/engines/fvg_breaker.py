"""
Fair Value Gap (FVG) + Breaker Block Engine
============================================
ICT Core Concepts:

FAIR VALUE GAP (FVG / Imbalance):
  A 3-candle pattern where candle[i-1].high < candle[i+1].low (Bullish FVG)
  or candle[i-1].low > candle[i+1].high (Bearish FVG).
  Price leaves an "unfilled" gap — this is where Smart Money expects price
  to return and react (acts as a magnet).

  Types:
  - Bullish FVG: gap between candle[i-1].high and candle[i+1].low
  - Bearish FVG: gap between candle[i-1].low and candle[i+1].high
  - Inversion FVG (IFVG): FVG that has been violated — now acts as opposite
  - Consequent Encroachment (CE): midpoint of FVG — 50% level (key entry)

BREAKER BLOCK:
  A failed Order Block — when an OB is swept through (broken), it becomes
  a BREAKER BLOCK. Price often comes back to test the breaker before
  continuing in the new direction.

  Formation:
  1. Identify an OB (bullish or bearish)
  2. Price breaks THROUGH the OB (not just wicking)
  3. The violated OB becomes a "breaker"
  4. On the first pullback back to the breaker → enter in direction of the break

  ICT Rule: "The block that broke is now the breaker. It will attract price
  back for one final test before the real move."

REJECTION BLOCK:
  Upper or lower wick heavy candle where the wick acted as the "supply/demand"
  area — treated similarly to OBs.

Output:
  - List of active FVGs (with CE level, status: fresh/partial/filled)
  - List of Breaker Blocks (with direction, strength)
  - Current price position relative to nearest FVG
  - Confluence scoring for entry setups
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────────────────

@dataclass
class FVG:
    """A Fair Value Gap instance."""
    id: int
    type: str               # "BULLISH" | "BEARISH"
    gap_high: float         # Top of FVG zone
    gap_low: float          # Bottom of FVG zone
    ce_level: float         # Consequent Encroachment (midpoint)
    size: float             # Gap size in price
    size_atr_mult: float    # Gap size as multiple of ATR
    bar_idx: int            # Index of the middle candle (impulse candle)
    status: str             # "FRESH" | "PARTIAL" | "FILLED" | "INVERTED"
    is_inverted: bool       # Has become an IFVG (Inversion FVG)
    fill_pct: float         # How much of the gap has been filled (0-1)
    displacement_vol: float # Volume of the middle impulse candle
    is_institutional: bool  # Large gap (> 1.5x ATR) = institutional imbalance
    strength: int           # 0-100 strength score


@dataclass
class BreakerBlock:
    """A failed Order Block that became a Breaker."""
    id: int
    type: str               # "BULLISH_BREAKER" | "BEARISH_BREAKER"
    # Original OB zone
    ob_high: float
    ob_low: float
    # Break level (candle that violated the OB)
    break_candle_idx: int
    break_price: float
    break_direction: str    # "UPWARD" | "DOWNWARD"
    # Status
    status: str             # "ACTIVE" | "TESTED" | "USED"
    has_returned: bool      # Has price come back to test it?
    midpoint: float         # Midpoint of the original OB
    strength: int           # 0-100


@dataclass
class FVGAnalysisResult:
    # FVG lists
    bullish_fvgs: List[FVG]
    bearish_fvgs: List[FVG]
    all_fvgs: List[FVG]      # Sorted by strength desc

    # Breaker blocks
    bullish_breakers: List[BreakerBlock]
    bearish_breakers: List[BreakerBlock]
    all_breakers: List[BreakerBlock]

    # Current context
    current_price: float
    nearest_bullish_fvg: Optional[FVG]
    nearest_bearish_fvg: Optional[FVG]
    nearest_breaker: Optional[BreakerBlock]

    # Stats
    total_fvgs: int
    fresh_fvgs: int
    inverted_fvgs: int
    total_breakers: int

    # Signals
    fvg_signal: str         # "PRICE_IN_FVG" | "FVG_ABOVE" | "FVG_BELOW" | "NEUTRAL"
    breaker_signal: str     # "PRICE_AT_BREAKER" | "BREAKER_ABOVE" | "BREAKER_BELOW" | "NEUTRAL"
    entry_bias: str         # "BUY" | "SELL" | "NEUTRAL"
    confluence_score: int   # 0-5

    signals: List[str] = field(default_factory=list)
    setup_quality: str = "NONE"  # "A+" | "A" | "B" | "C" | "NONE"


# ─────────────────────────────────────────────────────────
# FVG Engine
# ─────────────────────────────────────────────────────────

class FVGBreakerEngine:
    """
    Detects Fair Value Gaps and Breaker Blocks from OHLCV data.
    Core ICT concepts implementation.
    """

    def __init__(self, min_gap_atr_mult: float = 0.1):
        """
        Args:
            min_gap_atr_mult: Minimum FVG size as multiple of ATR to be considered valid.
                              0.1 = gap must be at least 10% of ATR (filters noise)
        """
        self.min_gap_atr_mult = min_gap_atr_mult

    def analyze(
        self,
        df: pd.DataFrame,
        lookback: int = 100,
        order_blocks: Optional[List] = None,
    ) -> FVGAnalysisResult:
        """
        Main analysis — detect FVGs and Breakers from OHLCV dataframe.

        Args:
            df: OHLCV dataframe
            lookback: How many candles to look back for FVGs
            order_blocks: Optional list of OrderBlock objects from ob_strength engine
                         (used to detect breakers)
        """
        if df is None or len(df) < 5:
            return self._empty()

        df = df.tail(lookback).copy().reset_index(drop=True)
        n = len(df)

        highs  = df["high"].astype(float).values
        lows   = df["low"].astype(float).values
        opens  = df["open"].astype(float).values
        closes = df["close"].astype(float).values
        vols   = df["volume"].astype(float).values if "volume" in df.columns else np.ones(n)

        current_price = float(closes[-1])
        atr = self._atr(highs, lows, closes)

        # ── 1. Detect FVGs ─────────────────────────────────────
        bullish_fvgs, bearish_fvgs = self._detect_fvgs(
            highs, lows, opens, closes, vols, atr
        )

        # ── 2. Update FVG status (filled/partial/inverted) ─────
        bullish_fvgs = self._update_fvg_status(bullish_fvgs, highs, lows, closes)
        bearish_fvgs = self._update_fvg_status(bearish_fvgs, highs, lows, closes)

        # ── 3. Detect Breaker Blocks ───────────────────────────
        bullish_breakers, bearish_breakers = self._detect_breakers(
            highs, lows, closes, atr
        )

        # ── 4. Find nearest FVGs to current price ──────────────
        active_bull_fvgs = [f for f in bullish_fvgs if f.status != "FILLED"]
        active_bear_fvgs = [f for f in bearish_fvgs if f.status != "FILLED"]
        all_fvgs = sorted(
            active_bull_fvgs + active_bear_fvgs,
            key=lambda f: f.strength, reverse=True
        )

        # Nearest bullish FVG below price
        bull_below = [f for f in active_bull_fvgs if f.gap_high < current_price]
        nearest_bull = max(bull_below, key=lambda f: f.gap_high) if bull_below else None

        # Nearest bearish FVG above price
        bear_above = [f for f in active_bear_fvgs if f.gap_low > current_price]
        nearest_bear = min(bear_above, key=lambda f: f.gap_low) if bear_above else None

        # Breakers near price
        all_breakers = sorted(
            bullish_breakers + bearish_breakers,
            key=lambda b: b.strength, reverse=True
        )
        near_breaker = self._nearest_breaker(all_breakers, current_price)

        # ── 5. Signals & Entry Bias ────────────────────────────
        signals = []
        bias_score = 0
        fvg_signal = "NEUTRAL"
        breaker_signal = "NEUTRAL"

        # Check if price is IN an FVG
        in_bull_fvg = any(f.gap_low <= current_price <= f.gap_high for f in active_bull_fvgs)
        in_bear_fvg = any(f.gap_low <= current_price <= f.gap_high for f in active_bear_fvgs)

        if in_bull_fvg:
            fvg_signal = "PRICE_IN_FVG"
            bias_score += 2
            signals.append("✅ Price currently inside Bullish FVG — BUY zone")
        elif in_bear_fvg:
            fvg_signal = "PRICE_IN_FVG"
            bias_score -= 2
            signals.append("🔴 Price currently inside Bearish FVG — SELL zone")
        elif nearest_bull:
            dist = (current_price - nearest_bull.gap_high) / current_price * 100
            fvg_signal = "FVG_BELOW"
            signals.append(f"📊 Bullish FVG {dist:.2f}% below — magnet target")
            if dist < 1.0:
                bias_score += 1
        elif nearest_bear:
            dist = (nearest_bear.gap_low - current_price) / current_price * 100
            fvg_signal = "FVG_ABOVE"
            signals.append(f"📊 Bearish FVG {dist:.2f}% above — magnet target")
            if dist < 1.0:
                bias_score -= 1

        # Check breaker proximity
        if near_breaker:
            dist = abs(current_price - near_breaker.midpoint) / current_price * 100
            if dist < 0.5:
                breaker_signal = "PRICE_AT_BREAKER"
                if near_breaker.type == "BULLISH_BREAKER":
                    bias_score += 2
                    signals.append(f"🧱 Price AT Bullish Breaker Block — strong BUY zone")
                else:
                    bias_score -= 2
                    signals.append(f"🧱 Price AT Bearish Breaker Block — strong SELL zone")
            elif near_breaker.type == "BULLISH_BREAKER":
                breaker_signal = "BREAKER_BELOW"
                signals.append(f"🧱 Bullish Breaker {dist:.2f}% below price")
            else:
                breaker_signal = "BREAKER_ABOVE"
                signals.append(f"🧱 Bearish Breaker {dist:.2f}% above price")

        # Institutional FVG bonus
        inst_fvgs = [f for f in all_fvgs if f.is_institutional]
        if inst_fvgs:
            signals.append(f"🐳 {len(inst_fvgs)} Institutional FVG(s) detected (>1.5x ATR)")
            bias_score += 1 if inst_fvgs[0].type == "BULLISH" else -1

        # Entry bias
        if bias_score >= 3:
            entry_bias = "BUY"
        elif bias_score <= -3:
            entry_bias = "SELL"
        else:
            entry_bias = "NEUTRAL"

        # Setup quality
        abs_score = abs(bias_score)
        setup_quality = ("A+" if abs_score >= 4 else "A" if abs_score >= 3 else
                         "B"  if abs_score >= 2 else "C" if abs_score >= 1 else "NONE")

        return FVGAnalysisResult(
            bullish_fvgs=bullish_fvgs,
            bearish_fvgs=bearish_fvgs,
            all_fvgs=all_fvgs,
            bullish_breakers=bullish_breakers,
            bearish_breakers=bearish_breakers,
            all_breakers=all_breakers,
            current_price=current_price,
            nearest_bullish_fvg=nearest_bull,
            nearest_bearish_fvg=nearest_bear,
            nearest_breaker=near_breaker,
            total_fvgs=len(all_fvgs),
            fresh_fvgs=sum(1 for f in all_fvgs if f.status == "FRESH"),
            inverted_fvgs=sum(1 for f in all_fvgs if f.is_inverted),
            total_breakers=len(all_breakers),
            fvg_signal=fvg_signal,
            breaker_signal=breaker_signal,
            entry_bias=entry_bias,
            confluence_score=min(5, abs_score),
            signals=signals,
            setup_quality=setup_quality,
        )

    # ─────────────────── core detectors ──────────────────────

    def _detect_fvgs(
        self, highs, lows, opens, closes, vols, atr
    ) -> Tuple[List[FVG], List[FVG]]:
        """
        3-candle FVG pattern:
        Bullish FVG: candle[i-1].high < candle[i+1].low
          → gap between them is the bullish imbalance
        Bearish FVG: candle[i-1].low > candle[i+1].high
          → gap between them is the bearish imbalance
        """
        bull_fvgs = []
        bear_fvgs = []
        n = len(closes)
        fvg_id = 0

        for i in range(1, n - 1):
            # Bullish FVG
            gap_low  = float(highs[i - 1])
            gap_high = float(lows[i + 1])
            if gap_high > gap_low:
                size = gap_high - gap_low
                if size >= atr * self.min_gap_atr_mult:
                    atr_mult = size / atr if atr > 0 else 0
                    ce = (gap_high + gap_low) / 2
                    is_inst = atr_mult >= 1.5
                    strength = self._fvg_strength(size, atr, vols[i], np.mean(vols), is_inst, closes[i] > opens[i])
                    bull_fvgs.append(FVG(
                        id=fvg_id, type="BULLISH",
                        gap_high=round(gap_high, 6), gap_low=round(gap_low, 6),
                        ce_level=round(ce, 6), size=round(size, 6),
                        size_atr_mult=round(atr_mult, 3), bar_idx=i,
                        status="FRESH", is_inverted=False, fill_pct=0.0,
                        displacement_vol=float(vols[i]),
                        is_institutional=is_inst, strength=strength,
                    ))
                    fvg_id += 1

            # Bearish FVG
            gap_high2 = float(lows[i - 1])
            gap_low2  = float(highs[i + 1])
            if gap_high2 > gap_low2:
                size = gap_high2 - gap_low2
                if size >= atr * self.min_gap_atr_mult:
                    atr_mult = size / atr if atr > 0 else 0
                    ce = (gap_high2 + gap_low2) / 2
                    is_inst = atr_mult >= 1.5
                    strength = self._fvg_strength(size, atr, vols[i], np.mean(vols), is_inst, closes[i] < opens[i])
                    bear_fvgs.append(FVG(
                        id=fvg_id, type="BEARISH",
                        gap_high=round(gap_high2, 6), gap_low=round(gap_low2, 6),
                        ce_level=round(ce, 6), size=round(size, 6),
                        size_atr_mult=round(atr_mult, 3), bar_idx=i,
                        status="FRESH", is_inverted=False, fill_pct=0.0,
                        displacement_vol=float(vols[i]),
                        is_institutional=is_inst, strength=strength,
                    ))
                    fvg_id += 1

        return bull_fvgs, bear_fvgs

    def _fvg_strength(
        self, size, atr, candle_vol, avg_vol, is_inst, is_impulse_direction
    ) -> int:
        """Score FVG 0-100."""
        score = 40  # base

        # Size bonus
        atr_ratio = size / atr if atr > 0 else 0
        score += min(30, int(atr_ratio * 20))

        # Volume bonus
        vol_ratio = candle_vol / avg_vol if avg_vol > 0 else 1
        score += min(15, int((vol_ratio - 1) * 10))

        # Institutional bonus
        if is_inst:
            score += 15

        # Direction alignment
        if is_impulse_direction:
            score += 10
        else:
            score -= 10

        return max(0, min(100, score))

    def _update_fvg_status(
        self, fvgs: List[FVG], highs, lows, closes
    ) -> List[FVG]:
        """Check which FVGs have been (partially) filled or inverted."""
        for fvg in fvgs:
            start_idx = fvg.bar_idx + 2  # After formation
            if start_idx >= len(closes):
                continue

            subsequent_highs = highs[start_idx:]
            subsequent_lows  = lows[start_idx:]

            if fvg.type == "BULLISH":
                # FVG filled when price trades down into the gap
                min_low = float(subsequent_lows.min()) if len(subsequent_lows) > 0 else fvg.gap_high
                if min_low <= fvg.gap_low:
                    # Full fill
                    fvg.status = "FILLED"
                    fvg.fill_pct = 1.0
                elif min_low < fvg.gap_high:
                    # Partial fill
                    fvg.fill_pct = (fvg.gap_high - min_low) / fvg.size
                    fvg.status = "PARTIAL"
                    # IFVG: price traded through the entire gap from above
                    if min_low < fvg.gap_low:
                        fvg.is_inverted = True
                        fvg.status = "INVERTED"

            elif fvg.type == "BEARISH":
                # Filled when price trades up into the gap
                max_high = float(subsequent_highs.max()) if len(subsequent_highs) > 0 else fvg.gap_low
                if max_high >= fvg.gap_high:
                    fvg.status = "FILLED"
                    fvg.fill_pct = 1.0
                elif max_high > fvg.gap_low:
                    fvg.fill_pct = (max_high - fvg.gap_low) / fvg.size
                    fvg.status = "PARTIAL"
                    if max_high > fvg.gap_high:
                        fvg.is_inverted = True
                        fvg.status = "INVERTED"

        return fvgs

    def _detect_breakers(
        self, highs, lows, closes, atr
    ) -> Tuple[List[BreakerBlock], List[BreakerBlock]]:
        """
        Breaker Block Detection:
        1. Find swing highs and lows (OB proxy using swing structure)
        2. When price sweeps through a swing high/low with momentum → Breaker
        3. On pullback to the broken level → entry signal
        """
        bull_breakers = []
        bear_breakers = []
        n = len(closes)
        bb_id = 0

        # Find swing points (simplified: 5-bar fractal)
        swing_highs = []
        swing_lows  = []
        for i in range(2, n - 2):
            if highs[i] == max(highs[i-2:i+3]):
                swing_highs.append((i, float(highs[i])))
            if lows[i] == min(lows[i-2:i+3]):
                swing_lows.append((i, float(lows[i])))

        # For each swing high, check if price later broke above with strength
        # → That swing area becomes a BEARISH BREAKER (broken supply)
        for sh_idx, sh_price in swing_highs[:-3]:
            # Check for break above: any subsequent close above swing high
            subsequent = closes[sh_idx + 1:]
            break_bars = np.where(subsequent > sh_price)[0]
            if len(break_bars) == 0:
                continue

            break_idx = sh_idx + 1 + int(break_bars[0])
            if break_idx >= n:
                continue

            # Confirm break: close above with decent move
            break_size = closes[break_idx] - sh_price
            if break_size < atr * 0.3:
                continue

            # Check if price has returned to test the breaker
            post_break = lows[break_idx + 1:]
            has_returned = len(post_break) > 0 and float(post_break.min()) <= sh_price * 1.002

            strength = min(100, 50 + int((break_size / atr) * 20))

            # The swing high zone is the bearish breaker (broken resistance = support)
            ob_high = sh_price + atr * 0.1
            ob_low  = sh_price - atr * 0.3

            bull_breakers.append(BreakerBlock(
                id=bb_id,
                type="BULLISH_BREAKER",  # Broken above → becomes support
                ob_high=round(ob_high, 6),
                ob_low=round(ob_low, 6),
                break_candle_idx=break_idx,
                break_price=float(closes[break_idx]),
                break_direction="UPWARD",
                status="TESTED" if has_returned else "ACTIVE",
                has_returned=has_returned,
                midpoint=round(sh_price, 6),
                strength=strength,
            ))
            bb_id += 1

        # For each swing low, check if price broke below
        for sl_idx, sl_price in swing_lows[:-3]:
            subsequent = closes[sl_idx + 1:]
            break_bars = np.where(subsequent < sl_price)[0]
            if len(break_bars) == 0:
                continue

            break_idx = sl_idx + 1 + int(break_bars[0])
            if break_idx >= n:
                continue

            break_size = sl_price - closes[break_idx]
            if break_size < atr * 0.3:
                continue

            post_break = highs[break_idx + 1:]
            has_returned = len(post_break) > 0 and float(post_break.max()) >= sl_price * 0.998

            strength = min(100, 50 + int((break_size / atr) * 20))

            ob_high = sl_price + atr * 0.3
            ob_low  = sl_price - atr * 0.1

            bear_breakers.append(BreakerBlock(
                id=bb_id,
                type="BEARISH_BREAKER",  # Broken below → becomes resistance
                ob_high=round(ob_high, 6),
                ob_low=round(ob_low, 6),
                break_candle_idx=break_idx,
                break_price=float(closes[break_idx]),
                break_direction="DOWNWARD",
                status="TESTED" if has_returned else "ACTIVE",
                has_returned=has_returned,
                midpoint=round(sl_price, 6),
                strength=strength,
            ))
            bb_id += 1

        # Return strongest 5 of each
        bull_breakers = sorted(bull_breakers, key=lambda b: b.strength, reverse=True)[:5]
        bear_breakers = sorted(bear_breakers, key=lambda b: b.strength, reverse=True)[:5]

        return bull_breakers, bear_breakers

    def _nearest_breaker(
        self, breakers: List[BreakerBlock], price: float
    ) -> Optional[BreakerBlock]:
        if not breakers:
            return None
        return min(breakers, key=lambda b: abs(b.midpoint - price))

    def _atr(self, highs, lows, closes, period=14) -> float:
        if len(closes) < 2:
            return 1.0
        trs = [
            max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            for i in range(1, len(closes))
        ]
        return float(np.mean(trs[-period:])) if trs else 1.0

    def _empty(self) -> FVGAnalysisResult:
        return FVGAnalysisResult(
            bullish_fvgs=[], bearish_fvgs=[], all_fvgs=[],
            bullish_breakers=[], bearish_breakers=[], all_breakers=[],
            current_price=0,
            nearest_bullish_fvg=None, nearest_bearish_fvg=None, nearest_breaker=None,
            total_fvgs=0, fresh_fvgs=0, inverted_fvgs=0, total_breakers=0,
            fvg_signal="NEUTRAL", breaker_signal="NEUTRAL",
            entry_bias="NEUTRAL", confluence_score=0, setup_quality="NONE",
        )

    # ─────────────────── serialization ───────────────────────

    def fvg_to_dict(self, f: FVG) -> dict:
        return {
            "id":             f.id,
            "type":           f.type,
            "gap_high":       f.gap_high,
            "gap_low":        f.gap_low,
            "ce_level":       f.ce_level,
            "size":           f.size,
            "size_atr_mult":  f.size_atr_mult,
            "bar_idx":        f.bar_idx,
            "status":         f.status,
            "is_inverted":    f.is_inverted,
            "fill_pct":       round(f.fill_pct * 100, 1),
            "is_institutional": f.is_institutional,
            "strength":       f.strength,
        }

    def breaker_to_dict(self, b: BreakerBlock) -> dict:
        return {
            "id":              b.id,
            "type":            b.type,
            "ob_high":         b.ob_high,
            "ob_low":          b.ob_low,
            "break_price":     b.break_price,
            "break_direction": b.break_direction,
            "status":          b.status,
            "has_returned":    b.has_returned,
            "midpoint":        b.midpoint,
            "strength":        b.strength,
        }

    def to_dict(self, r: FVGAnalysisResult) -> dict:
        return {
            "current_price": r.current_price,
            "summary": {
                "total_fvgs":    r.total_fvgs,
                "fresh_fvgs":    r.fresh_fvgs,
                "inverted_fvgs": r.inverted_fvgs,
                "total_breakers": r.total_breakers,
            },
            "bullish_fvgs": [self.fvg_to_dict(f) for f in r.bullish_fvgs],
            "bearish_fvgs": [self.fvg_to_dict(f) for f in r.bearish_fvgs],
            "top_fvgs":     [self.fvg_to_dict(f) for f in r.all_fvgs[:8]],
            "bullish_breakers": [self.breaker_to_dict(b) for b in r.bullish_breakers],
            "bearish_breakers": [self.breaker_to_dict(b) for b in r.bearish_breakers],
            "nearest": {
                "bullish_fvg": self.fvg_to_dict(r.nearest_bullish_fvg) if r.nearest_bullish_fvg else None,
                "bearish_fvg": self.fvg_to_dict(r.nearest_bearish_fvg) if r.nearest_bearish_fvg else None,
                "breaker":     self.breaker_to_dict(r.nearest_breaker) if r.nearest_breaker else None,
            },
            "signals": {
                "fvg_signal":      r.fvg_signal,
                "breaker_signal":  r.breaker_signal,
                "entry_bias":      r.entry_bias,
                "setup_quality":   r.setup_quality,
                "confluence_score": r.confluence_score,
                "messages":        r.signals,
            },
        }
