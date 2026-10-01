"""
Order Block Strength Meter
===========================
Not all Order Blocks are equal. This engine scores each OB based on 6 factors:

  1. Displacement Strength  (30 pts) — stronger move away = higher quality OB
  2. Formation Volume       (20 pts) — high volume at OB = institutional activity
  3. Touch Count Penalty   (-15/touch) — more touches = weaker OB (exhausted)
  4. Internal FVG          (+25 pts) — FVG inside OB = IFVG (super strong)
  5. HTF Confluence        (+15 pts) — OB aligns with HTF OB = institutional
  6. Freshness             (+10 pts) — recent OB > stale OB

Grade:
  A+ : score >= 80 (institutional, untouched, with FVG)
  A  : score >= 65
  B  : score >= 45
  C  : score >= 30
  D  : below 30 (skip)
"""

import pandas as pd
import numpy as np
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from app.schemas.market_data import OrderBlock


@dataclass
class ScoredOrderBlock:
    """OrderBlock enriched with strength score."""
    ob: OrderBlock
    score: int
    grade: str                   # A+ | A | B | C | D
    grade_color: str

    # Breakdown
    displacement_score: int = 0
    volume_score: int = 0
    touch_penalty: int = 0
    fvg_bonus: int = 0
    htf_bonus: int = 0
    freshness_score: int = 0

    # Context
    is_fresh: bool = True        # Not yet touched
    touch_count: int = 0
    has_internal_fvg: bool = False
    displacement_atr: float = 0.0

    # Recommendation
    is_tradeable: bool = True
    reason: str = ""


class OBStrengthMeter:
    """
    Scores Order Blocks by institutional quality.
    Integrates with existing SmartMoneyConceptsEngine output.
    """

    # Grade thresholds
    GRADE_THRESHOLDS = {
        "A+": 80,
        "A":  65,
        "B":  45,
        "C":  30,
    }

    GRADE_COLORS = {
        "A+": "#f59e0b",   # Gold
        "A":  "#10b981",   # Green
        "B":  "#3b82f6",   # Blue
        "C":  "#94a3b8",   # Gray
        "D":  "#ef4444",   # Red = skip
    }

    def score_order_blocks(
        self,
        df: pd.DataFrame,
        order_blocks: List[OrderBlock],
        fvgs: List = None,
        htf_obs: List[OrderBlock] = None,
    ) -> List[ScoredOrderBlock]:
        """
        Score a list of order blocks.

        Args:
            df: OHLCV DataFrame (entry timeframe)
            order_blocks: List of OrderBlock from SmartMoneyConceptsEngine
            fvgs: List of FVG (optional, for internal FVG detection)
            htf_obs: Higher timeframe order blocks (optional, for confluence)

        Returns:
            List of ScoredOrderBlock sorted by score descending.
        """
        if not order_blocks:
            return []

        atr     = self._estimate_atr(df)
        volumes = df["volume"].astype(float).values if "volume" in df.columns else None
        avg_vol = float(np.mean(volumes)) if volumes is not None else 0.0

        scored: List[ScoredOrderBlock] = []

        for ob in order_blocks:
            scored.append(
                self._score_single_ob(ob, df, atr, avg_vol, fvgs, htf_obs)
            )

        # Sort: A+ first, then by score
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored

    def _score_single_ob(
        self,
        ob: OrderBlock,
        df: pd.DataFrame,
        atr: float,
        avg_vol: float,
        fvgs: List = None,
        htf_obs: List[OrderBlock] = None,
    ) -> ScoredOrderBlock:
        n      = len(df)
        highs  = df["high"].astype(float).values
        lows   = df["low"].astype(float).values
        opens  = df["open"].astype(float).values
        closes = df["close"].astype(float).values
        vols   = df["volume"].astype(float).values if "volume" in df.columns else np.ones(n)

        ob_idx = ob.index

        # ── 1. Displacement Strength (0-30 pts) ──────────────────
        disp_score, disp_atr = self._score_displacement(
            ob, ob_idx, closes, opens, atr, n
        )

        # ── 2. Formation Volume (0-20 pts) ───────────────────────
        vol_score = 0
        if ob_idx < len(vols) and avg_vol > 0:
            ob_vol = vols[ob_idx]
            vol_ratio = ob_vol / avg_vol
            vol_score = min(20, int(vol_ratio * 10))

        # ── 3. Touch Count Penalty ────────────────────────────────
        touch_count, touch_penalty = self._count_touches(ob, highs, lows, closes, ob_idx, n)

        # ── 4. Internal FVG Bonus (+25 pts) ──────────────────────
        has_ifvg = False
        fvg_bonus = 0
        if fvgs:
            for fvg in fvgs:
                # FVG is "inside" OB if its high/low overlap with OB range
                fvg_in_ob = (fvg.low >= ob.low * 0.995 and fvg.high <= ob.high * 1.005)
                if fvg_in_ob:
                    has_ifvg = True
                    fvg_bonus = 25
                    break

        # ── 5. HTF Confluence (+15 pts) ──────────────────────────
        htf_bonus = 0
        if htf_obs:
            for htf_ob in htf_obs:
                # Check if current OB overlaps with HTF OB
                if htf_ob.type == ob.type:
                    overlap = (
                        ob.low <= htf_ob.high and ob.high >= htf_ob.low
                    )
                    if overlap:
                        htf_bonus = 15
                        break

        # ── 6. Freshness (0-10 pts) ───────────────────────────────
        age_bars     = n - 1 - ob_idx
        freshness    = max(0, 10 - int(age_bars / 5))  # -1 pt per 5 bars
        is_fresh     = touch_count == 0

        # ── Total Score ───────────────────────────────────────────
        total = (
            disp_score
            + vol_score
            - touch_penalty
            + fvg_bonus
            + htf_bonus
            + freshness
        )
        total = max(0, min(100, total))

        grade       = self._get_grade(total)
        is_tradeable = total >= 30 and touch_count <= 2

        reason = ""
        if touch_count > 2:
            reason = f"OB touched {touch_count}x — likely exhausted"
        elif not is_fresh:
            reason = f"OB tested {touch_count}x — reduced strength"

        return ScoredOrderBlock(
            ob=ob,
            score=total,
            grade=grade,
            grade_color=self.GRADE_COLORS.get(grade, "#64748b"),
            displacement_score=disp_score,
            volume_score=vol_score,
            touch_penalty=touch_penalty,
            fvg_bonus=fvg_bonus,
            htf_bonus=htf_bonus,
            freshness_score=freshness,
            is_fresh=is_fresh,
            touch_count=touch_count,
            has_internal_fvg=has_ifvg,
            displacement_atr=disp_atr,
            is_tradeable=is_tradeable,
            reason=reason,
        )

    def _score_displacement(
        self, ob: OrderBlock, ob_idx: int,
        closes, opens, atr: float, n: int
    ) -> tuple[int, float]:
        """Score displacement move after OB formation."""
        if ob_idx + 1 >= n:
            return 0, 0.0

        # Look at displacement candle (candle right after OB)
        disp_idx = ob_idx + 1
        body = abs(closes[disp_idx] - opens[disp_idx])
        atr_mult = (body / atr) if atr > 0 else 0.0

        # Score: 0-30 based on how many ATRs the displacement is
        score = min(30, int(atr_mult * 15))
        return score, round(atr_mult, 2)

    def _count_touches(
        self, ob: OrderBlock, highs, lows, closes, ob_idx: int, n: int
    ) -> tuple[int, int]:
        """Count how many times price has re-entered the OB zone."""
        touch_count = 0
        for i in range(ob_idx + 2, n):
            if ob.type == "BULLISH":
                # Price wicking into OB from below
                if lows[i] <= ob.high and closes[i] > ob.low:
                    touch_count += 1
            else:
                # Price wicking into OB from above
                if highs[i] >= ob.low and closes[i] < ob.high:
                    touch_count += 1

        penalty = min(touch_count * 15, 45)  # Cap at -45 pts
        return touch_count, penalty

    def _get_grade(self, score: int) -> str:
        if score >= self.GRADE_THRESHOLDS["A+"]:
            return "A+"
        elif score >= self.GRADE_THRESHOLDS["A"]:
            return "A"
        elif score >= self.GRADE_THRESHOLDS["B"]:
            return "B"
        elif score >= self.GRADE_THRESHOLDS["C"]:
            return "C"
        return "D"

    def _estimate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        if len(df) < 2:
            return 0.0
        highs  = df["high"].astype(float).values
        lows   = df["low"].astype(float).values
        closes = df["close"].astype(float).values
        trs = [
            max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            for i in range(1, len(df))
        ]
        return float(np.mean(trs[-period:])) if trs else 0.0

    def to_dict(self, sob: ScoredOrderBlock) -> dict:
        """Serialize to dict for API response."""
        return {
            "type":               sob.ob.type,
            "high":               sob.ob.high,
            "low":                sob.ob.low,
            "index":              sob.ob.index,
            "score":              sob.score,
            "grade":              sob.grade,
            "grade_color":        sob.grade_color,
            "is_fresh":           sob.is_fresh,
            "touch_count":        sob.touch_count,
            "has_internal_fvg":   sob.has_internal_fvg,
            "displacement_atr":   sob.displacement_atr,
            "is_tradeable":       sob.is_tradeable,
            "reason":             sob.reason,
            "breakdown": {
                "displacement":  sob.displacement_score,
                "volume":        sob.volume_score,
                "touch_penalty": -sob.touch_penalty,
                "internal_fvg":  sob.fvg_bonus,
                "htf_confluence": sob.htf_bonus,
                "freshness":     sob.freshness_score,
            },
        }
