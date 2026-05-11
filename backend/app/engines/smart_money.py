"""
Smart Money Concepts Detection (V2 - High Quality)
=====================================================
Detects institutional trading footprints with stricter quality filters:
- Order Blocks with mitigation tracking & freshness check
- Fair Value Gaps with minimum gap size & fill detection
- Liquidity levels (equal highs/lows, stop clusters)
- Liquidity sweeps
- Premium / Discount zones
"""

import pandas as pd
import numpy as np
from typing import List, Optional
from app.schemas.market_data import (
    OrderBlock, FairValueGap, LiquidityLevel, SmartMoneyAnalysis,
)


class SmartMoneyConceptsEngine:
    """Detects Smart Money Concepts on OHLCV data with strict quality filters."""

    def __init__(
        self,
        ob_lookback: int = 10,
        eq_tolerance: float = 0.001,
        ob_impulse_multiplier: float = 1.7,
        ob_min_body_ratio: float = 0.5,
        ob_max_age: int = 40,
        fvg_min_atr_ratio: float = 0.3,
    ):
        self.ob_lookback = ob_lookback
        self.eq_tolerance = eq_tolerance  # 0.1 % tolerance for equal highs/lows
        self.ob_impulse_multiplier = ob_impulse_multiplier  # Minimum impulse strength
        self.ob_min_body_ratio = ob_min_body_ratio  # OB candle must have dominant body
        self.ob_max_age = ob_max_age  # OB older than this many candles is stale
        self.fvg_min_atr_ratio = fvg_min_atr_ratio  # FVG must be >= this * ATR

    def analyze(
        self, df: pd.DataFrame, symbol: str = "", timeframe: str = ""
    ) -> SmartMoneyAnalysis:
        """Run full SMC analysis with enhanced quality filters."""
        if df.empty or len(df) < 10:
            return SmartMoneyAnalysis(symbol=symbol, timeframe=timeframe)

        atr = self._estimate_atr(df)
        obs = self._detect_order_blocks(df, atr)
        fvgs = self._detect_fvgs(df, atr)
        liq = self._detect_liquidity_levels(df)
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
        return sum(trs[-period:]) / min(period, len(trs))

    # ------------------------------------------------------------------
    # Order Blocks (V2 — stricter detection + mitigation tracking)
    # ------------------------------------------------------------------
    def _detect_order_blocks(self, df: pd.DataFrame, atr: float) -> List[OrderBlock]:
        """
        V2 Order Block detection with quality filters:
        - Impulse must be >= 2.0x average body (stronger institutional footprint)
        - OB candle must have body ratio >= 0.5 (no doji OBs)
        - OBs older than ob_max_age candles are discarded
        - Mitigated OBs (price revisited) are marked
        """
        obs: List[OrderBlock] = []
        highs = df["high"].astype(float).values
        lows = df["low"].astype(float).values
        opens = df["open"].astype(float).values
        closes = df["close"].astype(float).values
        n = len(df)

        # Pre-compute running average body size
        bodies = np.abs(closes - opens)
        cum_bodies = np.cumsum(bodies)

        for i in range(1, n - 2):
            body_prev = closes[i - 1] - opens[i - 1]
            body_curr = closes[i] - opens[i]

            # Running average body up to index i
            avg_body = cum_bodies[i - 1] / i if i > 0 else 1

            # --- Quality Filter 1: Body ratio of OB candle ---
            candle_range_prev = highs[i - 1] - lows[i - 1]
            body_ratio = abs(body_prev) / candle_range_prev if candle_range_prev > 0 else 0
            if body_ratio < self.ob_min_body_ratio:
                continue  # Skip doji/indecision candles

            # --- Quality Filter 2: Freshness (age check) ---
            candles_from_end = n - 1 - (i - 1)
            if candles_from_end > self.ob_max_age:
                continue  # Too old, skip

            # --- Quality Filter 3: Stronger impulse threshold ---
            impulse_threshold = avg_body * self.ob_impulse_multiplier

            # Bullish OB: bearish candle followed by strong bullish move
            if body_prev < 0 and body_curr > 0 and abs(body_curr) > impulse_threshold:
                time_val = df.iloc[i - 1]["open_time"] if "open_time" in df.columns else None
                ob = OrderBlock(
                    type="BULLISH",
                    high=float(highs[i - 1]),
                    low=float(lows[i - 1]),
                    index=i - 1,
                    time=time_val,
                )
                # Check mitigation: has price revisited this OB after it formed?
                ob.mitigated = self._check_ob_mitigated(
                    ob, highs, lows, i, n, "BULLISH"
                )
                if not ob.mitigated:
                    obs.append(ob)

            # Bearish OB: bullish candle followed by strong bearish move
            if body_prev > 0 and body_curr < 0 and abs(body_curr) > impulse_threshold:
                time_val = df.iloc[i - 1]["open_time"] if "open_time" in df.columns else None
                ob = OrderBlock(
                    type="BEARISH",
                    high=float(highs[i - 1]),
                    low=float(lows[i - 1]),
                    index=i - 1,
                    time=time_val,
                )
                ob.mitigated = self._check_ob_mitigated(
                    ob, highs, lows, i, n, "BEARISH"
                )
                if not ob.mitigated:
                    obs.append(ob)

        # Keep last N order blocks (most relevant)
        return obs[-self.ob_lookback:]

    def _check_ob_mitigated(
        self, ob: OrderBlock, highs, lows, start_idx: int, n: int, ob_type: str
    ) -> bool:
        """
        Check if an OB has been mitigated (price returned into the OB zone
        after it was created, meaning institutions already filled there).
        """
        for j in range(start_idx + 1, n):
            if ob_type == "BULLISH":
                # Bullish OB mitigated if price dipped back into the OB zone
                if lows[j] <= ob.high and lows[j] >= ob.low:
                    return True
            else:
                # Bearish OB mitigated if price wicked back into the OB zone
                if highs[j] >= ob.low and highs[j] <= ob.high:
                    return True
        return False

    # ------------------------------------------------------------------
    # Fair Value Gaps (V2 — minimum size + fill detection)
    # ------------------------------------------------------------------
    def _detect_fvgs(self, df: pd.DataFrame, atr: float) -> List[FairValueGap]:
        """
        V2 FVG detection with quality filters:
        - FVG must be >= fvg_min_atr_ratio * ATR (filter micro-gaps)
        - Filled FVGs are excluded
        """
        fvgs: List[FairValueGap] = []
        highs = df["high"].astype(float).values
        lows = df["low"].astype(float).values
        n = len(df)
        min_gap_size = atr * self.fvg_min_atr_ratio if atr > 0 else 0

        for i in range(2, n):
            # Bullish FVG: low of current candle > high of two candles ago
            if lows[i] > highs[i - 2]:
                gap_size = lows[i] - highs[i - 2]
                if gap_size < min_gap_size:
                    continue  # Too small, not significant

                # Check if FVG has been filled by subsequent candles
                filled = self._check_fvg_filled(
                    highs[i - 2], lows[i], lows, i + 1, n, "BULLISH"
                )
                if filled:
                    continue  # Already filled, skip

                time_val = df.iloc[i - 1]["open_time"] if "open_time" in df.columns else None
                fvgs.append(FairValueGap(
                    type="BULLISH",
                    high=float(lows[i]),
                    low=float(highs[i - 2]),
                    index=i - 1,
                    time=time_val,
                ))

            # Bearish FVG: high of current candle < low of two candles ago
            if highs[i] < lows[i - 2]:
                gap_size = lows[i - 2] - highs[i]
                if gap_size < min_gap_size:
                    continue  # Too small

                filled = self._check_fvg_filled(
                    highs[i], lows[i - 2], highs, i + 1, n, "BEARISH"
                )
                if filled:
                    continue

                time_val = df.iloc[i - 1]["open_time"] if "open_time" in df.columns else None
                fvgs.append(FairValueGap(
                    type="BEARISH",
                    high=float(lows[i - 2]),
                    low=float(highs[i]),
                    index=i - 1,
                    time=time_val,
                ))

        return fvgs[-20:]  # Keep last 20

    def _check_fvg_filled(
        self, gap_low: float, gap_high: float,
        price_array, start_idx: int, n: int, fvg_type: str
    ) -> bool:
        """
        Check if an FVG has been filled by subsequent price action.
        Bullish FVG filled = price dipped back down into the gap
        Bearish FVG filled = price pushed back up into the gap
        """
        for j in range(start_idx, n):
            if fvg_type == "BULLISH":
                # Bullish FVG filled if a subsequent candle's low enters the gap
                if price_array[j] <= gap_high:
                    return True
            else:
                # Bearish FVG filled if a subsequent candle's high enters the gap
                if price_array[j] >= gap_low:
                    return True
        return False

    # ------------------------------------------------------------------
    # Liquidity Levels
    # ------------------------------------------------------------------
    def _detect_liquidity_levels(self, df: pd.DataFrame) -> List[LiquidityLevel]:
        """Detect equal highs/lows using O(n log n) sort-and-group."""
        levels: List[LiquidityLevel] = []
        highs = df["high"].astype(float).values
        lows = df["low"].astype(float).values
        n = len(df)
        tolerance = self.eq_tolerance
        last_high = float(highs[-1]) if n > 0 else 0
        last_low = float(lows[-1]) if n > 0 else 0

        # Equal Highs — sort then group neighbors (O(n log n))
        sorted_highs = sorted(enumerate(highs), key=lambda x: x[1])
        i = 0
        while i < len(sorted_highs):
            group_price = sorted_highs[i][1]
            count = 1
            j = i + 1
            while j < len(sorted_highs) and abs(sorted_highs[j][1] - group_price) / group_price < tolerance:
                count += 1
                j += 1
            if count >= 2:
                avg_price = sum(sorted_highs[k][1] for k in range(i, j)) / count
                levels.append(LiquidityLevel(
                    price=round(avg_price, 8),
                    type="EQUAL_HIGH",
                    strength=count,
                    swept=last_high > avg_price,
                ))
            i = j

        # Equal Lows
        sorted_lows = sorted(enumerate(lows), key=lambda x: x[1])
        i = 0
        while i < len(sorted_lows):
            group_price = sorted_lows[i][1]
            count = 1
            j = i + 1
            while j < len(sorted_lows) and abs(sorted_lows[j][1] - group_price) / group_price < tolerance:
                count += 1
                j += 1
            if count >= 2:
                avg_price = sum(sorted_lows[k][1] for k in range(i, j)) / count
                levels.append(LiquidityLevel(
                    price=round(avg_price, 8),
                    type="EQUAL_LOW",
                    strength=count,
                    swept=last_low < avg_price,
                ))
            i = j

        # Deduplicate close levels
        levels = self._deduplicate_levels(levels)
        return levels[:20]

    def _deduplicate_levels(self, levels: List[LiquidityLevel]) -> List[LiquidityLevel]:
        """Merge levels that are very close to each other."""
        if not levels:
            return levels
        sorted_levels = sorted(levels, key=lambda l: l.price)
        merged: List[LiquidityLevel] = [sorted_levels[0]]
        for lv in sorted_levels[1:]:
            if abs(lv.price - merged[-1].price) / merged[-1].price < self.eq_tolerance:
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
        Check if recent candles swept any liquidity level.
        V2: checks a window of `lookback` candles (default 3) instead of
        only the last candle, to catch sweeps that happen across 2-3 bars.
        """
        if df.empty or not levels:
            return []

        window = df.iloc[-lookback:]
        recent_high = float(window["high"].astype(float).max())
        recent_low = float(window["low"].astype(float).min())

        swept = []
        for lv in levels:
            if lv.type == "EQUAL_HIGH" and recent_high > lv.price:
                lv.swept = True
                swept.append(lv)
            elif lv.type == "EQUAL_LOW" and recent_low < lv.price:
                lv.swept = True
                swept.append(lv)
        return swept
