"""
Liquidity Sweep Detector
=========================
Market Makers always "sweep" liquidity pools (clusters of retail stop losses)
BEFORE reversing to the true direction. This engine detects those sweeps.

Key Concepts:
  1. Equal Highs / Equal Lows  → Liquidity Pool (retail stops cluster here)
  2. Stop Hunt / Sweep          → Price briefly pierces the level (wick beyond)
  3. Displacement Candle        → Strong reversal candle immediately after sweep
  4. Confirmation               → Close back inside the range = REAL signal

Edge: 80%+ of ICT A+ setups begin with a liquidity sweep in a killzone.

Detection Flow:
    Equal Level Found → Sweep Wick Detected → Displacement Confirmed → SIGNAL
"""

import pandas as pd
import numpy as np
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LiquidityPool:
    """A cluster of equal highs or equal lows (retail stop cluster)."""
    price: float
    type: str           # "EQUAL_HIGH" | "EQUAL_LOW"
    strength: int       # Number of touches (higher = stronger magnet)
    bar_indices: List[int] = field(default_factory=list)
    first_seen: Optional[int] = None
    last_seen: Optional[int] = None
    swept: bool = False
    sweep_bar: Optional[int] = None


@dataclass
class SweepEvent:
    """A detected liquidity sweep event."""
    pool: LiquidityPool
    sweep_type: str         # "SELL_SIDE_SWEEP" | "BUY_SIDE_SWEEP"
    direction_after: str    # Expected direction after sweep: "BUY" | "SELL"
    sweep_bar_idx: int
    sweep_price: float      # Lowest wick (sell sweep) or highest wick (buy sweep)

    # Displacement
    has_displacement: bool = False
    displacement_strength: float = 0.0   # In ATR multiples
    displacement_bar_idx: Optional[int] = None

    # Trade quality
    is_confirmed: bool = False            # Displacement + close back inside
    quality_score: int = 0               # 0-100
    signal_grade: str = "WEAK"           # A+ | VALID | WEAK

    # Levels for trading
    entry_zone_low: float = 0.0
    entry_zone_high: float = 0.0
    invalidation: float = 0.0            # Price that invalidates the sweep thesis

    sweep_time: Optional[str] = None


class LiquiditySweepEngine:
    """
    Detects liquidity sweeps and displacement patterns for ICT-style entries.
    """

    def __init__(
        self,
        eq_tolerance_pct: float = 0.0015,   # 0.15% tolerance for "equal" levels
        min_touches: int = 2,                # Minimum touches to form a pool
        sweep_wick_multiplier: float = 1.2,  # Wick must exceed level by this factor
        displacement_atr_multiplier: float = 1.0,  # Displacement >= 1x ATR
        lookback: int = 80,                  # Max bars to look back for pools
    ):
        self.eq_tolerance_pct = eq_tolerance_pct
        self.min_touches = min_touches
        self.sweep_wick_multiplier = sweep_wick_multiplier
        self.displacement_atr_min = displacement_atr_multiplier
        self.lookback = lookback

    def analyze(self, df: pd.DataFrame) -> dict:
        """
        Full liquidity sweep analysis.

        Returns:
            {
                "pools": [LiquidityPool, ...],
                "sweeps": [SweepEvent, ...],
                "latest_sweep": SweepEvent | None,
                "bias_from_sweep": "BUY" | "SELL" | None,
                "score": int,  # confluence score contribution 0-5
            }
        """
        if df.empty or len(df) < 10:
            return {"pools": [], "sweeps": [], "latest_sweep": None,
                    "bias_from_sweep": None, "score": 0}

        df = df.tail(self.lookback).reset_index(drop=True)
        atr = self._estimate_atr(df)

        pools  = self._detect_liquidity_pools(df)
        sweeps = self._detect_sweeps(df, pools, atr)

        # Find most recent confirmed sweep
        confirmed = [s for s in sweeps if s.is_confirmed]
        latest = confirmed[-1] if confirmed else (sweeps[-1] if sweeps else None)

        # Bias from latest sweep
        bias = latest.direction_after if latest else None

        # Score for confluence
        score = self._calc_score(latest)

        return {
            "pools":          [self._pool_to_dict(p) for p in pools],
            "sweeps":         [self._sweep_to_dict(s) for s in sweeps],
            "latest_sweep":   self._sweep_to_dict(latest) if latest else None,
            "bias_from_sweep": bias,
            "score":          score,
            "atr":            round(atr, 8),
            "confirmed_count": len(confirmed),
        }

    # ────────────────── Pool Detection ──────────────────

    def _detect_liquidity_pools(self, df: pd.DataFrame) -> List[LiquidityPool]:
        """
        Find equal highs and equal lows that form liquidity pools.
        Equal = within eq_tolerance_pct of each other.
        """
        highs  = df["high"].astype(float).values
        lows   = df["low"].astype(float).values
        n      = len(df)

        pools: List[LiquidityPool] = []

        # Equal Highs
        pools += self._cluster_equal_levels(highs, n, "EQUAL_HIGH")
        # Equal Lows
        pools += self._cluster_equal_levels(lows, n, "EQUAL_LOW")

        # Keep only pools with minimum touches
        pools = [p for p in pools if p.strength >= self.min_touches]

        return pools

    def _cluster_equal_levels(
        self, prices: np.ndarray, n: int, pool_type: str
    ) -> List[LiquidityPool]:
        """Group price levels into clusters of equal levels."""
        pools: List[LiquidityPool] = []
        used = [False] * n

        for i in range(n):
            if used[i]:
                continue
            base_price = prices[i]
            tolerance  = base_price * self.eq_tolerance_pct
            cluster_indices = [i]
            cluster_prices  = [base_price]

            for j in range(i + 1, n):
                if used[j]:
                    continue
                if abs(prices[j] - base_price) <= tolerance:
                    cluster_indices.append(j)
                    cluster_prices.append(prices[j])
                    used[j] = True

            if len(cluster_indices) >= self.min_touches:
                avg_price = float(np.mean(cluster_prices))
                pools.append(LiquidityPool(
                    price=round(avg_price, 8),
                    type=pool_type,
                    strength=len(cluster_indices),
                    bar_indices=cluster_indices,
                    first_seen=min(cluster_indices),
                    last_seen=max(cluster_indices),
                ))
                for idx in cluster_indices:
                    used[idx] = True

        return pools

    # ────────────────── Sweep Detection ──────────────────

    def _detect_sweeps(
        self,
        df: pd.DataFrame,
        pools: List[LiquidityPool],
        atr: float,
    ) -> List[SweepEvent]:
        """Detect sweep + displacement patterns after each pool."""
        sweeps: List[SweepEvent] = []
        highs  = df["high"].astype(float).values
        lows   = df["low"].astype(float).values
        opens  = df["open"].astype(float).values
        closes = df["close"].astype(float).values
        n      = len(df)

        for pool in pools:
            start_idx = (pool.last_seen or 0) + 1
            if start_idx >= n:
                continue

            for i in range(start_idx, n):
                sweep_event = None

                # ── BUY-SIDE SWEEP (Equal Highs swept then price rejects down)
                if pool.type == "EQUAL_HIGH":
                    wick_above = highs[i] > pool.price * self.sweep_wick_multiplier
                    # Actually for sweep: wick just needs to pierce the level
                    wick_pierces = highs[i] > pool.price and closes[i] < pool.price
                    if wick_pierces:
                        sweep_event = SweepEvent(
                            pool=pool,
                            sweep_type="BUY_SIDE_SWEEP",
                            direction_after="SELL",
                            sweep_bar_idx=i,
                            sweep_price=highs[i],
                            entry_zone_low=pool.price * 0.998,
                            entry_zone_high=pool.price * 1.002,
                            invalidation=highs[i] * 1.001,
                        )
                        pool.swept = True
                        pool.sweep_bar = i

                # ── SELL-SIDE SWEEP (Equal Lows swept then price rejects up)
                elif pool.type == "EQUAL_LOW":
                    wick_pierces = lows[i] < pool.price and closes[i] > pool.price
                    if wick_pierces:
                        sweep_event = SweepEvent(
                            pool=pool,
                            sweep_type="SELL_SIDE_SWEEP",
                            direction_after="BUY",
                            sweep_bar_idx=i,
                            sweep_price=lows[i],
                            entry_zone_low=pool.price * 0.998,
                            entry_zone_high=pool.price * 1.002,
                            invalidation=lows[i] * 0.999,
                        )
                        pool.swept = True
                        pool.sweep_bar = i

                if sweep_event:
                    # Check displacement on next 1-3 bars
                    self._check_displacement(sweep_event, df, i, n, atr)
                    self._score_sweep(sweep_event, pool, atr)

                    # Add time context
                    if "open_time" in df.columns:
                        try:
                            t = df.iloc[i]["open_time"]
                            sweep_event.sweep_time = str(t)
                        except Exception:
                            pass

                    sweeps.append(sweep_event)
                    break  # One sweep per pool (find first then stop)

        return sweeps

    def _check_displacement(
        self,
        event: SweepEvent,
        df: pd.DataFrame,
        sweep_idx: int,
        n: int,
        atr: float,
    ):
        """
        Check for displacement candle after sweep.
        Displacement = large candle in direction_after with body > 1x ATR.
        """
        highs  = df["high"].astype(float).values
        lows   = df["low"].astype(float).values
        opens  = df["open"].astype(float).values
        closes = df["close"].astype(float).values

        for j in range(sweep_idx + 1, min(sweep_idx + 4, n)):
            body = closes[j] - opens[j]
            body_abs = abs(body)

            is_bullish_disp = (
                event.direction_after == "BUY"
                and body > 0
                and body_abs >= atr * self.displacement_atr_min
            )
            is_bearish_disp = (
                event.direction_after == "SELL"
                and body < 0
                and body_abs >= atr * self.displacement_atr_min
            )

            if is_bullish_disp or is_bearish_disp:
                event.has_displacement = True
                event.displacement_strength = round(body_abs / atr, 2) if atr > 0 else 0
                event.displacement_bar_idx  = j
                event.is_confirmed = True
                break

    def _score_sweep(self, event: SweepEvent, pool: LiquidityPool, atr: float):
        """Score the sweep quality 0-100."""
        score = 0

        # Pool strength
        score += min(pool.strength * 10, 30)  # max 30 pts

        # Displacement confirmed
        if event.has_displacement:
            score += 30
            score += min(int(event.displacement_strength * 10), 20)  # max 20 pts for strength

        # Fresh sweep (recent)
        age = event.sweep_bar_idx
        recency_bonus = max(0, 20 - age)  # More recent = higher score
        score += min(recency_bonus, 20)

        event.quality_score = min(100, score)

        # Grade
        if event.quality_score >= 75 and event.is_confirmed:
            event.signal_grade = "A+"
        elif event.quality_score >= 50 or event.is_confirmed:
            event.signal_grade = "VALID"
        else:
            event.signal_grade = "WEAK"

    def _calc_score(self, event: Optional[SweepEvent]) -> int:
        """Convert to confluence score (0-5 pts)."""
        if event is None:
            return 0
        if event.signal_grade == "A+" and event.is_confirmed:
            return 5
        elif event.signal_grade == "VALID":
            return 3
        elif event.has_displacement:
            return 2
        else:
            return 1

    # ────────────────── ATR ──────────────────

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

    # ────────────────── Serialization ──────────────────

    def _pool_to_dict(self, p: LiquidityPool) -> dict:
        return {
            "price":       p.price,
            "type":        p.type,
            "strength":    p.strength,
            "swept":       p.swept,
            "first_seen":  p.first_seen,
            "last_seen":   p.last_seen,
        }

    def _sweep_to_dict(self, s: Optional[SweepEvent]) -> Optional[dict]:
        if s is None:
            return None
        return {
            "pool_price":            s.pool.price,
            "pool_type":             s.pool.type,
            "pool_strength":         s.pool.strength,
            "sweep_type":            s.sweep_type,
            "direction_after":       s.direction_after,
            "sweep_bar_idx":         s.sweep_bar_idx,
            "sweep_price":           round(s.sweep_price, 8),
            "has_displacement":      s.has_displacement,
            "displacement_strength": s.displacement_strength,
            "is_confirmed":          s.is_confirmed,
            "quality_score":         s.quality_score,
            "signal_grade":          s.signal_grade,
            "entry_zone_low":        round(s.entry_zone_low, 8),
            "entry_zone_high":       round(s.entry_zone_high, 8),
            "invalidation":          round(s.invalidation, 8),
            "sweep_time":            s.sweep_time,
        }
