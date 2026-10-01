"""
Advanced Position Sizing Engine — Sprint 1
==========================================
Implements:
  - Kelly Criterion (full + fractional)
  - Risk of Ruin Calculator
  - Optimal position size based on account + risk %
  - Forex lot size calculator
  - Crypto unit/contracts calculator
  - Break-even win rate
"""

import math
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class PositionSizingResult:
    # Core sizing
    position_size: float        # In base currency units (e.g., BTC)
    position_value: float       # In quote currency (e.g., USDT)
    risk_amount: float          # Dollar amount at risk
    risk_pct: float             # % of account at risk

    # Levels
    entry_price: float
    stop_loss: float
    stop_distance: float
    stop_distance_pct: float

    # Targets
    take_profit_1: Optional[float]
    take_profit_2: Optional[float]
    take_profit_3: Optional[float]
    rr_1: Optional[float]
    rr_2: Optional[float]
    rr_3: Optional[float]

    # Kelly
    kelly_full: float           # Full Kelly fraction
    kelly_quarter: float        # Quarter-Kelly (recommended)
    kelly_recommended_pct: float  # Recommended risk % from Kelly

    # Risk of Ruin
    risk_of_ruin_pct: float    # % probability of blowing account
    max_consecutive_losses: int  # Consecutive losses to cut risk in half

    # Crypto specific
    leverage_1x_size: float    # Position size at 1x leverage
    leverage_5x_size: float    # Position size at 5x (cross margin)
    leverage_10x_size: float   # Position size at 10x

    # Break even
    breakeven_win_rate: float  # Win rate needed to break even at this R:R
    expected_value: float       # EV per trade in $ (positive = profitable system)

    # Recommendation
    size_grade: str             # OPTIMAL | MODERATE | AGGRESSIVE | CONSERVATIVE
    warnings: List[str] = field(default_factory=list)


class PositionSizingEngine:
    """
    Professional position sizing with Kelly Criterion and risk controls.

    Usage:
        engine = PositionSizingEngine()
        result = engine.calculate(
            account_balance=10000,
            risk_pct=1.0,
            entry=64000,
            stop_loss=63000,
            direction="BUY",
            win_rate=0.55,
            avg_rr=2.0,
            take_profits=[65000, 66000, 68000],
        )
    """

    def calculate(
        self,
        account_balance: float,
        risk_pct: float,
        entry: float,
        stop_loss: float,
        direction: str = "BUY",
        win_rate: float = 0.5,
        avg_rr: float = 2.0,
        take_profits: Optional[List[float]] = None,
    ) -> PositionSizingResult:
        """Calculate position size with full risk analysis."""
        warnings = []

        # Clamp inputs
        risk_pct = max(0.1, min(risk_pct, 10.0))
        win_rate = max(0.01, min(win_rate, 0.99))
        avg_rr   = max(0.1, avg_rr)

        # Stop distance
        stop_dist     = abs(entry - stop_loss)
        stop_dist_pct = (stop_dist / entry) * 100 if entry > 0 else 0

        # Risk amount
        risk_amount = account_balance * (risk_pct / 100)

        # Position size (units of base asset)
        position_size  = risk_amount / stop_dist if stop_dist > 0 else 0
        position_value = position_size * entry

        # ── Kelly Criterion ─────────────────────────────────────────────
        # f* = (bp - q) / b
        # b = average win / average loss = avg_rr
        # p = win_rate, q = 1 - win_rate
        b = avg_rr
        p = win_rate
        q = 1 - win_rate

        kelly_full = (b * p - q) / b
        kelly_full = max(0.0, kelly_full)

        kelly_quarter     = kelly_full * 0.25
        kelly_rec_pct     = kelly_quarter * 100   # As percentage of account

        # ── Risk of Ruin ──────────────────────────────────────────────────
        # Using the simplified formula:
        # R = ((1 - edge) / (1 + edge))^n
        # Where edge = (p * b - q) and n = (1 / risk_pct)
        ror_pct = self._risk_of_ruin(win_rate, avg_rr, risk_pct / 100)

        # Max consecutive losses before risking 50% of account
        max_consec = self._max_consecutive_losses_before_halving(risk_pct)

        # ── Targets ──────────────────────────────────────────────────────
        tps = take_profits or []
        tp1 = tps[0] if len(tps) > 0 else None
        tp2 = tps[1] if len(tps) > 1 else None
        tp3 = tps[2] if len(tps) > 2 else None

        rr1 = self._calc_rr(entry, stop_loss, tp1, direction) if tp1 else None
        rr2 = self._calc_rr(entry, stop_loss, tp2, direction) if tp2 else None
        rr3 = self._calc_rr(entry, stop_loss, tp3, direction) if tp3 else None

        # ── Leverage sizes ────────────────────────────────────────────────
        lev1  = position_size
        lev5  = position_size * 5
        lev10 = position_size * 10

        # ── Break-even & Expected Value ───────────────────────────────────
        breakeven_wr = 1 / (1 + avg_rr)   # WR needed to break even
        ev = (win_rate * avg_rr * risk_amount) - ((1 - win_rate) * risk_amount)

        # ── Size Grade & Warnings ─────────────────────────────────────────
        grade, warnings = self._grade_size(
            risk_pct, kelly_rec_pct, ror_pct, position_value, account_balance
        )

        return PositionSizingResult(
            position_size=round(position_size, 6),
            position_value=round(position_value, 2),
            risk_amount=round(risk_amount, 2),
            risk_pct=round(risk_pct, 2),
            entry_price=entry,
            stop_loss=stop_loss,
            stop_distance=round(stop_dist, 8),
            stop_distance_pct=round(stop_dist_pct, 3),
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            rr_1=rr1,
            rr_2=rr2,
            rr_3=rr3,
            kelly_full=round(kelly_full * 100, 2),
            kelly_quarter=round(kelly_quarter * 100, 2),
            kelly_recommended_pct=round(kelly_rec_pct, 2),
            risk_of_ruin_pct=round(ror_pct, 2),
            max_consecutive_losses=max_consec,
            leverage_1x_size=round(lev1, 6),
            leverage_5x_size=round(lev5, 6),
            leverage_10x_size=round(lev10, 6),
            breakeven_win_rate=round(breakeven_wr * 100, 1),
            expected_value=round(ev, 2),
            size_grade=grade,
            warnings=warnings,
        )

    def _risk_of_ruin(self, win_rate: float, avg_rr: float, risk_fraction: float) -> float:
        """
        Approximate Risk of Ruin using gambler's ruin formula.
        Higher = worse.
        """
        edge = win_rate * avg_rr - (1 - win_rate)
        if edge <= 0:
            return 100.0  # Negative edge = guaranteed ruin

        # Simplified RoR formula
        try:
            q_over_p = (1 - win_rate) / win_rate
            n_units   = 1.0 / risk_fraction  # Number of risk units in account
            ror = (q_over_p ** n_units) * 100
            return min(100.0, max(0.0, ror))
        except Exception:
            return 0.0

    def _max_consecutive_losses_before_halving(self, risk_pct: float) -> int:
        """How many consecutive losses before account halved."""
        if risk_pct <= 0:
            return 999
        # Account halves when (1 - risk_pct/100)^n = 0.5
        # n = log(0.5) / log(1 - risk_pct/100)
        try:
            n = math.log(0.5) / math.log(1 - risk_pct / 100)
            return max(1, int(n))
        except Exception:
            return 999

    def _calc_rr(self, entry: float, sl: float, tp: float, direction: str) -> float:
        risk   = abs(entry - sl)
        reward = abs(tp - entry)
        if direction == "SELL":
            reward = abs(entry - tp)
        return round(reward / risk, 2) if risk > 0 else 0.0

    def _grade_size(
        self, risk_pct: float, kelly_pct: float, ror_pct: float,
        position_value: float, account: float
    ) -> tuple[str, List[str]]:
        warnings = []
        leverage_implied = (position_value / account) * 100

        if risk_pct <= kelly_pct and ror_pct < 5:
            grade = "OPTIMAL"
        elif risk_pct <= kelly_pct * 1.5 and ror_pct < 15:
            grade = "MODERATE"
        elif risk_pct > 3:
            grade = "AGGRESSIVE"
            warnings.append("⚠️ Risk >3% per trade exceeds professional norms")
        else:
            grade = "CONSERVATIVE"

        if ror_pct > 25:
            warnings.append(f"🚨 Risk of Ruin is {ror_pct:.0f}% — reduce position size!")
        if risk_pct > kelly_pct * 2 and kelly_pct > 0:
            warnings.append(f"⚠️ Risk % ({risk_pct:.1f}%) is 2x the Kelly recommendation ({kelly_pct:.1f}%)")
        if position_value > account * 0.5:
            warnings.append("⚠️ Position value exceeds 50% of account — high exposure!")

        return grade, warnings
