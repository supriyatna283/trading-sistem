"""
Premium / Discount Zone Engine
================================
Smart Money Concepts: Institutions BUY in Discount (< 50% of range) 
and SELL in Premium (> 50% of range).

Key Concepts:
  - Premium Zone   : > 62% of HTF range (institutional SELL zone)
  - Equilibrium    : ~50% (CIPD - Consequent Encroachment of Price Delivery)
  - Discount Zone  : < 38% of HTF range (institutional BUY zone)
  - OTE            : Optimal Trade Entry (0.62–0.79 Fib retracement)
  - SIBI / BISI    : Sell-Side Imbalance Buy-Side / Buy-Side Imbalance Sell-Side

Usage:
    from app.engines.pd_zones import PDZoneEngine
    engine = PDZoneEngine()
    result = engine.analyze(df_1d, df_4h, df_1h, current_price)
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class PDZoneResult:
    """Full P/D zone analysis result."""
    # Current position
    zone: str                   # PREMIUM | DISCOUNT | EQUILIBRIUM
    zone_pct: float             # 0-100 position within range
    zone_color: str             # UI color hint

    # Range anchor
    range_high: float
    range_low: float
    range_mid: float            # 50% = equilibrium
    range_size: float

    # Key levels
    premium_threshold: float    # 62% = top of discount → premium
    discount_threshold: float   # 38% = bottom of premium → discount
    ote_low: float              # 62% Fib retracement (OTE entry zone)
    ote_high: float             # 79% Fib retracement (OTE entry zone)

    # Bias
    htf_bias: str               # BULLISH | BEARISH | SIDEWAYS
    trade_allowed: bool         # True = BUY in discount / SELL in premium
    signal: str                 # STRONG_BUY | BUY | NEUTRAL | SELL | STRONG_SELL

    # Context
    distance_to_ote_pct: float  # Distance to nearest OTE level in %
    is_in_ote: bool             # Price inside OTE zone (best entry)
    equilibrium: float          # 50% midpoint

    # Breakdown per timeframe
    htf_range: Dict[str, float] = field(default_factory=dict)  # {"high": x, "low": y, "tf": "1d"}


class PDZoneEngine:
    """
    Premium/Discount Zone Engine.
    Analyzes where current price sits in HTF range and whether it's a valid
    institutional entry zone.
    """

    # Fib-based zone boundaries
    PREMIUM_LEVEL  = 0.618   # Above this → Premium (sell territory)
    DISCOUNT_LEVEL = 0.382   # Below this → Discount (buy territory)
    OTE_LOW        = 0.62    # OTE zone start (Optimal Trade Entry)
    OTE_HIGH       = 0.79    # OTE zone end

    def analyze(
        self,
        df_htf: pd.DataFrame,      # Higher timeframe (1D or 4H) candles
        current_price: float,
        lookback: int = 20,        # Bars to determine swing high/low range
        htf_label: str = "1D",
    ) -> PDZoneResult:
        """
        Analyze Premium/Discount zones based on HTF swing range.

        Args:
            df_htf: Higher timeframe OHLCV DataFrame
            current_price: Current market price
            lookback: Number of bars to find swing high/low
            htf_label: Label for HTF timeframe

        Returns:
            PDZoneResult with full zone breakdown
        """
        if df_htf.empty or len(df_htf) < 5:
            return self._empty_result(current_price)

        # Find the swing range (recent high/low)
        recent = df_htf.tail(lookback)
        range_high = float(recent["high"].max())
        range_low  = float(recent["low"].min())
        range_size = range_high - range_low

        if range_size <= 0:
            return self._empty_result(current_price)

        # HTF bias (last close vs midpoint)
        last_close = float(df_htf["close"].iloc[-1])
        range_mid  = range_low + range_size * 0.5
        htf_bias   = "BULLISH" if last_close > range_mid else (
                     "BEARISH" if last_close < range_mid else "SIDEWAYS")

        # Key Fib levels
        premium_threshold  = range_low + range_size * self.PREMIUM_LEVEL
        discount_threshold = range_low + range_size * self.DISCOUNT_LEVEL

        # OTE levels depend on HTF bias (Fib from swing)
        # For BULLISH: OTE is a pullback from high (discount retracement)
        # For BEARISH: OTE is a rally from low (premium retracement)
        if htf_bias == "BULLISH":
            ote_low  = range_low + range_size * self.OTE_LOW
            ote_high = range_low + range_size * self.OTE_HIGH
        else:
            ote_low  = range_high - range_size * self.OTE_HIGH
            ote_high = range_high - range_size * self.OTE_LOW

        # Where is current price?
        zone_pct  = ((current_price - range_low) / range_size) * 100
        zone_pct  = max(0.0, min(100.0, zone_pct))

        raw_ratio = (current_price - range_low) / range_size

        if raw_ratio >= self.PREMIUM_LEVEL:
            zone = "PREMIUM"
            zone_color = "#ef4444"   # Red = sell zone
        elif raw_ratio <= self.DISCOUNT_LEVEL:
            zone = "DISCOUNT"
            zone_color = "#10b981"   # Green = buy zone
        else:
            zone = "EQUILIBRIUM"
            zone_color = "#f59e0b"   # Yellow = wait

        # Is price in OTE?
        is_in_ote = ote_low <= current_price <= ote_high

        # Distance to nearest OTE boundary
        dist_to_ote_low  = abs(current_price - ote_low)  / current_price * 100
        dist_to_ote_high = abs(current_price - ote_high) / current_price * 100
        dist_to_ote = min(dist_to_ote_low, dist_to_ote_high)

        # Trade signal
        trade_allowed, signal = self._generate_signal(
            zone, htf_bias, is_in_ote, zone_pct
        )

        return PDZoneResult(
            zone=zone,
            zone_pct=round(zone_pct, 1),
            zone_color=zone_color,
            range_high=round(range_high, 8),
            range_low=round(range_low, 8),
            range_mid=round(range_mid, 8),
            range_size=round(range_size, 8),
            premium_threshold=round(premium_threshold, 8),
            discount_threshold=round(discount_threshold, 8),
            ote_low=round(ote_low, 8),
            ote_high=round(ote_high, 8),
            htf_bias=htf_bias,
            trade_allowed=trade_allowed,
            signal=signal,
            distance_to_ote_pct=round(dist_to_ote, 3),
            is_in_ote=is_in_ote,
            equilibrium=round(range_mid, 8),
            htf_range={"high": range_high, "low": range_low, "tf": htf_label},
        )

    def score_for_confluence(self, result: PDZoneResult, direction: str) -> int:
        """
        Return confluence score contribution (0-4 pts) for use in ConfluenceEngine.

        Rules:
          - BUY in DISCOUNT + OTE : +4 pts
          - BUY in DISCOUNT       : +2 pts
          - SELL in PREMIUM + OTE : +4 pts
          - SELL in PREMIUM       : +2 pts
          - Direction in EQUILIBRIUM: +1 pt (neutral)
          - Opposing zone         : 0 pts (fade risk)
        """
        if direction == "BUY":
            if result.zone == "DISCOUNT":
                return 4 if result.is_in_ote else 2
            elif result.zone == "EQUILIBRIUM":
                return 1
            else:
                return 0  # Buying in premium = bad
        else:  # SELL
            if result.zone == "PREMIUM":
                return 4 if result.is_in_ote else 2
            elif result.zone == "EQUILIBRIUM":
                return 1
            else:
                return 0  # Selling in discount = bad

    # ─────────────────── private ───────────────────

    def _generate_signal(
        self,
        zone: str,
        bias: str,
        is_in_ote: bool,
        zone_pct: float
    ) -> tuple[bool, str]:
        """Determine if trade is allowed and the signal label."""
        if zone == "DISCOUNT" and bias == "BULLISH":
            return True, "STRONG_BUY" if is_in_ote else "BUY"
        elif zone == "PREMIUM" and bias == "BEARISH":
            return True, "STRONG_SELL" if is_in_ote else "SELL"
        elif zone == "EQUILIBRIUM":
            return False, "NEUTRAL"
        elif zone == "PREMIUM" and bias == "BULLISH":
            # Buying near HTF high — caution
            return False, "CAUTION_PREMIUM"
        elif zone == "DISCOUNT" and bias == "BEARISH":
            # Selling near HTF low — caution
            return False, "CAUTION_DISCOUNT"
        return False, "NEUTRAL"

    def _empty_result(self, price: float) -> PDZoneResult:
        return PDZoneResult(
            zone="UNKNOWN", zone_pct=50.0, zone_color="#64748b",
            range_high=price, range_low=price, range_mid=price, range_size=0,
            premium_threshold=price, discount_threshold=price,
            ote_low=price, ote_high=price,
            htf_bias="SIDEWAYS", trade_allowed=False, signal="NEUTRAL",
            distance_to_ote_pct=0.0, is_in_ote=False, equilibrium=price,
        )
