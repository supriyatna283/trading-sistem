"""
Smart Money Concepts Detection (V3 - Institutional Precision)
=============================================================
Detects institutional trading footprints with realistic ICT/SMC rules:
- Order Blocks: rolling body + ATR displacement filter, structure-break / FVG
  validation, and full lifecycle tracking (FRESH -> TESTED -> MITIGATED / INVALIDATED).
- Fair Value Gaps: tracks 50% Consequent Encroachment (CE), partial fills, and
  only marks a gap FILLED when price fully traverses the gap or closes past CE.
- Liquidity levels: swing-pivot Equal Highs/Lows with ATR-adaptive tolerance
  and genuine wick-through + close-back sweep detection.
- Premium / Discount equilibrium.
"""

import pandas as pd
import numpy as np
from typing import List, Optional, Tuple
from app.schemas.market_data import (
    OrderBlock, FairValueGap, LiquidityLevel, SmartMoneyAnalysis,
)


class SmartMoneyConceptsEngine:
    """Detects Smart Money Concepts on OHLCV data with institutional quality filters."""

    def __init__(
        self,
        ob_lookback: int = 15,
        eq_tolerance: float = 0.001,
        ob_impulse_multiplier: float = 1.3,
        ob_min_body_ratio: float = 0.4,
        ob_max_age: int = 80,
        fvg_min_atr_ratio: float = 0.2,
    ):
        self.ob_lookback = ob_lookback
        self.eq_tolerance = eq_tolerance
        self.ob_impulse_multiplier = ob_impulse_multiplier
        self.ob_min_body_ratio = ob_min_body_ratio
        self.ob_max_age = ob_max_age
        self.fvg_min_atr_ratio = fvg_min_atr_ratio

    def analyze(
        self, df: pd.DataFrame, symbol: str = "", timeframe: str = ""
    ) -> SmartMoneyAnalysis:
        """Run full SMC analysis with V3 institutional filters."""
        if df.empty or len(df) < 10:
            return SmartMoneyAnalysis(symbol=symbol, timeframe=timeframe)

        atr = self._estimate_atr(df)
        obs = self._detect_order_blocks(df, atr)
        fvgs = self._detect_fvgs(df, atr)
        liq = self._detect_liquidity_levels(df, atr)
        pd_mid = self._premium_discount_midpoint(df)

        return SmartMoneyAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            order_blocks=obs,
            fvgs=fvgs,
            liquidity_levels=liq,
            premium_discount_mid=pd_mid,
        )

    # ------------------------------------------------------------------
    # ATR estimation (shared utility)
    # ------------------------------------------------------------------
    def _estimate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Estimate ATR from OHLCV data."""
        if df.empty or len(df) < 2:
            return 0.0
        highs = df["high"].astype(float).values
        lows = df["low"].astype(float).values
        closes = df["close"].astype(float).values
        trs = []
        for i in range(1, len(df)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)
        if not trs:
            return 0.0
        return float(sum(trs[-period:]) / min(period, len(trs)))

    # ------------------------------------------------------------------
    # Order Blocks (V3 — rolling baseline + displacement validation + lifecycle)
    # ------------------------------------------------------------------
    def _detect_order_blocks(self, df: pd.DataFrame, atr: float) -> List[OrderBlock]:
        """
        V3 Order Block detection:
        - Uses 20-bar rolling average body + ATR threshold (no long-history drift)
        - Inspects up to the latest completed bar (no longer skips last 2 candles)
        - Requires institutional displacement: impulse breaks recent local structure,
          creates an FVG, or exceeds 1.8x rolling body
        - Tracks full lifecycle: FRESH, TESTED (wick tap), MITIGATED (close inside),
          and INVALIDATED (close through the opposite side -> discarded)
        """
        active_obs: List[OrderBlock] = []
        mitigated_obs: List[OrderBlock] = []
        highs = df["high"].astype(float).values
        lows = df["low"].astype(float).values
        opens = df["open"].astype(float).values
        closes = df["close"].astype(float).values
        n = len(df)

        bodies = np.abs(closes - opens)

        for i in range(1, n):
            ob_idx = i - 1
            candles_from_end = n - 1 - ob_idx
            if candles_from_end > self.ob_max_age:
                continue

            body_prev = closes[ob_idx] - opens[ob_idx]
            body_curr = closes[i] - opens[i]

            candle_range_prev = highs[ob_idx] - lows[ob_idx]
            body_ratio = abs(body_prev) / candle_range_prev if candle_range_prev > 0 else 0.0
            if body_ratio < self.ob_min_body_ratio:
                continue

            # 20-bar rolling body baseline prior to the impulse candle
            win_start = max(0, ob_idx - 20)
            avg_body = float(np.mean(bodies[win_start:i])) if i > win_start else float(bodies[ob_idx] or 1.0)
            impulse_threshold = max(avg_body * self.ob_impulse_multiplier, atr * 0.45 if atr > 0 else 0.0)

            # Look at 1-2 candle displacement leg starting at i
            leg_end = min(n - 1, i + 1)
            time_val = df.iloc[ob_idx]["open_time"] if "open_time" in df.columns else None

            # ── Bullish OB: bearish candle followed by bullish displacement ──
            if body_prev < 0 and body_curr > 0 and abs(body_curr) > impulse_threshold:
                ref_start = max(0, ob_idx - 6)
                prior_swing_high = float(np.max(highs[ref_start:ob_idx])) if ob_idx > ref_start else float(highs[ob_idx])
                leg_max_close = float(np.max(closes[i : leg_end + 1]))
                bos_ok = leg_max_close > prior_swing_high
                has_fvg = (i + 1 < n) and (lows[i + 1] > highs[ob_idx])
                strong_disp = abs(body_curr) >= avg_body * 1.75

                if not (bos_ok or has_fvg or strong_disp):
                    continue

                ob = OrderBlock(
                    type="BULLISH",
                    high=float(highs[ob_idx]),
                    low=float(lows[ob_idx]),
                    index=ob_idx,
                    time=time_val,
                    bos_confirmed=bos_ok,
                )
                self._evaluate_ob_state(ob, highs, lows, closes, i, n)
                if ob.status == "INVALIDATED":
                    continue
                if ob.mitigated:
                    mitigated_obs.append(ob)
                else:
                    active_obs.append(ob)

            # ── Bearish OB: bullish candle followed by bearish displacement ──
            elif body_prev > 0 and body_curr < 0 and abs(body_curr) > impulse_threshold:
                ref_start = max(0, ob_idx - 6)
                prior_swing_low = float(np.min(lows[ref_start:ob_idx])) if ob_idx > ref_start else float(lows[ob_idx])
                leg_min_close = float(np.min(closes[i : leg_end + 1]))
                bos_ok = leg_min_close < prior_swing_low
                has_fvg = (i + 1 < n) and (highs[i + 1] < lows[ob_idx])
                strong_disp = abs(body_curr) >= avg_body * 1.75

                if not (bos_ok or has_fvg or strong_disp):
                    continue

                ob = OrderBlock(
                    type="BEARISH",
                    high=float(highs[ob_idx]),
                    low=float(lows[ob_idx]),
                    index=ob_idx,
                    time=time_val,
                    bos_confirmed=bos_ok,
                )
                self._evaluate_ob_state(ob, highs, lows, closes, i, n)
                if ob.status == "INVALIDATED":
                    continue
                if ob.mitigated:
                    mitigated_obs.append(ob)
                else:
                    active_obs.append(ob)

        # Return recent active OBs + up to 3 recently mitigated OBs (marked mitigated=True
        # so downstream trade engines skip them while the chart can render ghost zones).
        combined = active_obs[-self.ob_lookback :] + mitigated_obs[-3:]
        combined.sort(key=lambda o: o.index)
        return combined

    def _evaluate_ob_state(
        self, ob: OrderBlock, highs, lows, closes, impulse_idx: int, n: int
    ) -> None:
        """
        Evaluate OB lifecycle after the impulse candle:
        - INVALIDATED: candle closes completely past the distal edge of the OB
          (close < ob.low for BULLISH, close > ob.high for BEARISH).
        - MITIGATED: candle closes inside [ob.low, ob.high] after price has left the zone.
        - TESTED: wick taps into [ob.low, ob.high] and closes back outside in trend direction.
        - FRESH: untouched since formation.
        """
        left_zone = False
        for j in range(impulse_idx, n):
            if ob.type == "BULLISH":
                if lows[j] > ob.high:
                    left_zone = True
                if not left_zone and j == impulse_idx:
                    if closes[j] > ob.high:
                        left_zone = True
                    continue
                # Close below distal edge -> zone failed
                if closes[j] < ob.low:
                    ob.mitigated = True
                    ob.status = "INVALIDATED"
                    return
                # Close inside zone -> consumed / mitigated (keep scanning in case later bar invalidates)
                if ob.low <= closes[j] <= ob.high:
                    ob.mitigated = True
                    ob.tested = True
                    ob.status = "MITIGATED"
                    continue
                # Wick tap into zone but close held above -> respected re-test
                if lows[j] <= ob.high and closes[j] > ob.high and not ob.mitigated:
                    ob.tested = True
                    ob.status = "TESTED"
            else:
                if highs[j] < ob.low:
                    left_zone = True
                if not left_zone and j == impulse_idx:
                    if closes[j] < ob.low:
                        left_zone = True
                    continue
                # Close above distal edge -> zone failed
                if closes[j] > ob.high:
                    ob.mitigated = True
                    ob.status = "INVALIDATED"
                    return
                # Close inside zone -> consumed / mitigated (keep scanning in case later bar invalidates)
                if ob.low <= closes[j] <= ob.high:
                    ob.mitigated = True
                    ob.tested = True
                    ob.status = "MITIGATED"
                    continue
                # Wick tap into zone but close held below -> respected re-test
                if highs[j] >= ob.low and closes[j] < ob.low and not ob.mitigated:
                    ob.tested = True
                    ob.status = "TESTED"

    # ------------------------------------------------------------------
    # Fair Value Gaps (V3 — partial fill, 50% CE touch, full fill)
    # ------------------------------------------------------------------
    def _detect_fvgs(self, df: pd.DataFrame, atr: float) -> List[FairValueGap]:
        """
        V3 FVG detection:
        - FVG must be >= fvg_min_atr_ratio * ATR
        - Tracks partial fills and 50% Consequent Encroachment (CE) touches
        - Only marks an FVG as FILLED (and excludes it from active list) when price
          traverses the entire gap OR closes beyond the 50% CE level.
        """
        fvgs: List[FairValueGap] = []
        highs = df["high"].astype(float).values
        lows = df["low"].astype(float).values
        closes = df["close"].astype(float).values
        n = len(df)
        min_gap_size = atr * self.fvg_min_atr_ratio if atr > 0 else 0.0

        for i in range(2, n):
            time_val = df.iloc[i - 1]["open_time"] if "open_time" in df.columns else None

            # Bullish FVG: low[i] > high[i - 2]
            if lows[i] > highs[i - 2]:
                gap_low = float(highs[i - 2])
                gap_high = float(lows[i])
                gap_size = gap_high - gap_low
                if gap_size < min_gap_size:
                    continue

                filled, fill_pct, ce_touched, status = self._evaluate_fvg_state(
                    gap_low, gap_high, highs, lows, closes, i + 1, n, "BULLISH"
                )
                if filled:
                    continue

                fvgs.append(FairValueGap(
                    type="BULLISH",
                    high=gap_high,
                    low=gap_low,
                    index=i - 1,
                    time=time_val,
                    filled=False,
                    midpoint=round((gap_low + gap_high) / 2.0, 8),
                    fill_pct=fill_pct,
                    ce_touched=ce_touched,
                    status=status,
                ))

            # Bearish FVG: high[i] < low[i - 2]
            if highs[i] < lows[i - 2]:
                gap_low = float(highs[i])
                gap_high = float(lows[i - 2])
                gap_size = gap_high - gap_low
                if gap_size < min_gap_size:
                    continue

                filled, fill_pct, ce_touched, status = self._evaluate_fvg_state(
                    gap_low, gap_high, highs, lows, closes, i + 1, n, "BEARISH"
                )
                if filled:
                    continue

                fvgs.append(FairValueGap(
                    type="BEARISH",
                    high=gap_high,
                    low=gap_low,
                    index=i - 1,
                    time=time_val,
                    filled=False,
                    midpoint=round((gap_low + gap_high) / 2.0, 8),
                    fill_pct=fill_pct,
                    ce_touched=ce_touched,
                    status=status,
                ))

        return fvgs[-20:]

    def _evaluate_fvg_state(
        self,
        gap_low: float,
        gap_high: float,
        highs,
        lows,
        closes,
        start_idx: int,
        n: int,
        fvg_type: str,
    ) -> Tuple[bool, float, bool, str]:
        """
        Return (filled, fill_pct, ce_touched, status) for an FVG.
        - Bullish FVG is filled when price reaches gap_low or closes below 50% CE.
        - Bearish FVG is filled when price reaches gap_high or closes above 50% CE.
        """
        gap_size = gap_high - gap_low
        if gap_size <= 0 or start_idx >= n:
            return False, 0.0, False, "FRESH"

        ce = (gap_low + gap_high) / 2.0
        max_penetration = 0.0
        ce_touched = False

        for j in range(start_idx, n):
            if fvg_type == "BULLISH":
                if lows[j] <= gap_low or closes[j] < ce:
                    return True, 100.0, True, "FILLED"
                if lows[j] < gap_high:
                    pen = (gap_high - float(lows[j])) / gap_size * 100.0
                    if pen > max_penetration:
                        max_penetration = pen
                    if lows[j] <= ce:
                        ce_touched = True
            else:
                if highs[j] >= gap_high or closes[j] > ce:
                    return True, 100.0, True, "FILLED"
                if highs[j] > gap_low:
                    pen = (float(highs[j]) - gap_low) / gap_size * 100.0
                    if pen > max_penetration:
                        max_penetration = pen
                    if highs[j] >= ce:
                        ce_touched = True

        fill_pct = round(min(99.9, max_penetration), 1)
        if ce_touched:
            status = "CE_TOUCHED"
        elif fill_pct > 0:
            status = "PARTIAL"
        else:
            status = "FRESH"
        return False, fill_pct, ce_touched, status

    # ------------------------------------------------------------------
    # Liquidity Levels (V3 — swing pivots + ATR tolerance + genuine sweep)
    # ------------------------------------------------------------------
    def _detect_liquidity_levels(
        self, df: pd.DataFrame, atr: float = 0.0
    ) -> List[LiquidityLevel]:
        """
        Detect Equal Highs / Equal Lows from genuine swing pivots (not adjacent bars),
        cluster within an ATR-adaptive tolerance, and flag sweeps only when price
        wicks beyond the pool and closes back inside.
        """
        levels: List[LiquidityLevel] = []
        highs = df["high"].astype(float).values
        lows = df["low"].astype(float).values
        closes = df["close"].astype(float).values
        n = len(df)
        if n < 10:
            return levels

        last_close = float(closes[-1])
        # ATR-adaptive relative tolerance (bounded between 0.05% and 0.35%)
        atr_rel = (atr * 0.18 / last_close) if (atr > 0 and last_close > 0) else self.eq_tolerance
        tolerance = max(0.0005, min(0.0035, max(self.eq_tolerance, atr_rel)))

        lb = 2
        swing_highs: List[Tuple[int, float]] = []
        swing_lows: List[Tuple[int, float]] = []
        for idx in range(lb, n - lb):
            if highs[idx] == max(highs[idx - lb : idx + lb + 1]):
                if not swing_highs or idx - swing_highs[-1][0] >= lb:
                    swing_highs.append((idx, float(highs[idx])))
            if lows[idx] == min(lows[idx - lb : idx + lb + 1]):
                if not swing_lows or idx - swing_lows[-1][0] >= lb:
                    swing_lows.append((idx, float(lows[idx])))

        # Cluster swing highs -> EQUAL_HIGH
        sorted_sh = sorted(swing_highs, key=lambda x: x[1])
        i = 0
        while i < len(sorted_sh):
            base_p = sorted_sh[i][1]
            j = i + 1
            while j < len(sorted_sh) and abs(sorted_sh[j][1] - base_p) / base_p <= tolerance:
                j += 1
            cluster = sorted_sh[i:j]
            # Require at least 2 distinct swings separated by >= 3 bars
            if len(cluster) >= 2 and (max(c[0] for c in cluster) - min(c[0] for c in cluster)) >= 3:
                by_time = sorted(cluster, key=lambda c: c[0])
                base_level = (by_time[0][1] + by_time[1][1]) / 2.0
                core_swings = by_time[:2] + [
                    c for c in by_time[2:]
                    if not (c[1] > base_level and closes[c[0]] < base_level)
                ]
                avg_price = sum(c[1] for c in core_swings) / len(core_swings)
                formed_idx = by_time[1][0]
                swept, broken = self._check_pool_state(
                    avg_price, highs, lows, closes, formed_idx + 1, n, "EQUAL_HIGH"
                )
                if not broken:
                    levels.append(LiquidityLevel(
                        price=round(avg_price, 8),
                        type="EQUAL_HIGH",
                        strength=len(core_swings),
                        swept=swept,
                    ))
            i = j

        # Cluster swing lows -> EQUAL_LOW
        sorted_sl = sorted(swing_lows, key=lambda x: x[1])
        i = 0
        while i < len(sorted_sl):
            base_p = sorted_sl[i][1]
            j = i + 1
            while j < len(sorted_sl) and abs(sorted_sl[j][1] - base_p) / base_p <= tolerance:
                j += 1
            cluster = sorted_sl[i:j]
            if len(cluster) >= 2 and (max(c[0] for c in cluster) - min(c[0] for c in cluster)) >= 3:
                by_time = sorted(cluster, key=lambda c: c[0])
                base_level = (by_time[0][1] + by_time[1][1]) / 2.0
                core_swings = by_time[:2] + [
                    c for c in by_time[2:]
                    if not (c[1] < base_level and closes[c[0]] > base_level)
                ]
                avg_price = sum(c[1] for c in core_swings) / len(core_swings)
                formed_idx = by_time[1][0]
                swept, broken = self._check_pool_state(
                    avg_price, highs, lows, closes, formed_idx + 1, n, "EQUAL_LOW"
                )
                if not broken:
                    levels.append(LiquidityLevel(
                        price=round(avg_price, 8),
                        type="EQUAL_LOW",
                        strength=len(core_swings),
                        swept=swept,
                    ))
            i = j

        levels = self._deduplicate_levels(levels, tolerance)
        return levels[:20]

    def _check_pool_state(
        self,
        level_price: float,
        highs,
        lows,
        closes,
        start_idx: int,
        n: int,
        pool_type: str,
    ) -> Tuple[bool, bool]:
        """
        Return (swept, broken) for a liquidity pool after its formation:
        - swept=True: a recent candle (last 8 bars) wicked beyond level_price and
          closed back inside, and current close is still inside.
        - broken=True: price closed decisively beyond level_price and stayed beyond it
          (the liquidity pool was run through in a trend continuation, no longer pending).
        """
        if start_idx >= n:
            return False, False

        recent_start = max(start_idx, n - 8)
        if pool_type == "EQUAL_HIGH":
            # If latest close is well above the equal highs, the pool was broken through
            if closes[-1] > level_price * (1 + self.eq_tolerance):
                return False, True
            swept = any(
                highs[k] > level_price and closes[k] < level_price
                for k in range(recent_start, n)
            )
            return swept, False
        else:
            if closes[-1] < level_price * (1 - self.eq_tolerance):
                return False, True
            swept = any(
                lows[k] < level_price and closes[k] > level_price
                for k in range(recent_start, n)
            )
            return swept, False

    def _deduplicate_levels(
        self, levels: List[LiquidityLevel], tolerance: Optional[float] = None
    ) -> List[LiquidityLevel]:
        """Merge levels that are very close to each other."""
        if not levels:
            return levels
        tol = tolerance or self.eq_tolerance
        sorted_levels = sorted(levels, key=lambda l: l.price)
        merged: List[LiquidityLevel] = [sorted_levels[0]]
        for lv in sorted_levels[1:]:
            if lv.type == merged[-1].type and abs(lv.price - merged[-1].price) / merged[-1].price < tol:
                merged[-1].strength = max(merged[-1].strength, lv.strength) + 1
                merged[-1].swept = merged[-1].swept or lv.swept
            else:
                merged.append(lv)
        return merged

    # ------------------------------------------------------------------
    # Premium / Discount
    # ------------------------------------------------------------------
    def _premium_discount_midpoint(self, df: pd.DataFrame) -> Optional[float]:
        """Calculate the 50% equilibrium of the current range."""
        if df.empty:
            return None
        recent = df.tail(50)
        range_high = float(recent["high"].max())
        range_low = float(recent["low"].min())
        return round((range_high + range_low) / 2, 8)

    # ------------------------------------------------------------------
    # Liquidity Sweep Detection
    # ------------------------------------------------------------------
    def check_liquidity_sweep(
        self, df: pd.DataFrame, levels: List[LiquidityLevel],
        lookback: int = 3,
    ) -> List[LiquidityLevel]:
        """
        Check if recent candles swept any liquidity level (wick through + close back).
        """
        if df.empty or not levels:
            return []

        window = df.iloc[-lookback:]
        recent_high = float(window["high"].astype(float).max())
        recent_low = float(window["low"].astype(float).min())
        last_close = float(df.iloc[-1]["close"])

        swept = []
        for lv in levels:
            if lv.type == "EQUAL_HIGH":
                if recent_high > lv.price and last_close < lv.price:
                    lv.swept = True
                    swept.append(lv)
            elif lv.type == "EQUAL_LOW":
                if recent_low < lv.price and last_close > lv.price:
                    lv.swept = True
                    swept.append(lv)
        return swept
