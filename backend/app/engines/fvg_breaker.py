"""
FVG + Breaker Block Engine — MAXIMIZED VERSION
================================================

ADDITIONS vs V1:
  - Rejection Blocks (heavy-wick candles)
  - Propulsion Blocks (momentum candles that leave FVGs)
  - FVG Confluence Zones (overlapping FVGs = stronger magnet)
  - Time-weighted scoring (recent FVGs score higher)
  - Entry Zone Calculator per FVG (CE entry, SL, TP)
  - Multi-FVG confluence analysis
  - Breaker OTE calculation (optimal entry within breaker)
  - ICT Setup Score combining all elements
  - Efficiency Ratio (how fast price typically returns)
  - FVG Stack detection (multiple aligned FVGs)
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# Data Models — v2
# ═══════════════════════════════════════════════════════

@dataclass
class EntryZone:
    """Computed entry zone for a FVG or Breaker."""
    entry_price:   float     # Ideal entry (CE or OTE of zone)
    stop_loss:     float     # SL beyond the gap
    tp1:           float     # First TP (opposite edge of nearest FVG)
    tp2:           float     # Second TP (1.5R extension)
    tp3:           float     # Third TP (2R extension)
    rr_tp1:        float     # Risk:Reward to TP1
    rr_tp2:        float     # Risk:Reward to TP2
    risk_pct:      float     # Risk % from entry to SL
    entry_quality: str       # "IDEAL" | "GOOD" | "VALID"


@dataclass
class FVG:
    id: int
    type: str                 # "BULLISH" | "BEARISH"
    gap_high:       float
    gap_low:        float
    ce_level:       float     # 50% of gap (Consequent Encroachment)
    size:           float
    size_atr_mult:  float
    bar_idx:        int
    bar_age:        int       # How many bars ago the FVG formed
    status: str               # "FRESH"|"PARTIAL"|"FILLED"|"INVERTED"
    is_inverted:    bool
    fill_pct:       float
    displacement_vol: float
    avg_vol:        float
    vol_ratio:      float     # displacement_vol / avg_vol
    is_institutional: bool
    is_stacked:     bool      # Another FVG overlaps this one
    stack_count:    int       # How many FVGs overlap
    strength:       int       # 0–100
    entry_zone:     Optional[EntryZone] = None


@dataclass
class RejectionBlock:
    """Heavy-wick candle acting as supply/demand."""
    id:           int
    type:         str      # "BULLISH_RB" | "BEARISH_RB"
    zone_high:    float
    zone_low:     float
    wick_pct:     float    # Wick as % of candle range
    bar_idx:      int
    strength:     int


@dataclass
class BreakerBlock:
    id:             int
    type:           str    # "BULLISH_BREAKER" | "BEARISH_BREAKER"
    ob_high:        float
    ob_low:         float
    midpoint:       float
    ote_entry:      float  # OTE (62%) within the breaker zone
    break_candle_idx: int
    break_price:    float
    break_direction: str   # "UPWARD" | "DOWNWARD"
    break_strength:  float # Size of break relative to ATR
    status:         str    # "ACTIVE" | "TESTED" | "USED"
    test_count:     int    # How many times price has returned
    has_returned:   bool
    entry_zone:     Optional[EntryZone] = None
    strength:       int = 0


@dataclass
class FVGStack:
    """Multiple overlapping FVGs = extra strong zone."""
    zone_high:  float
    zone_low:   float
    count:      int
    types:      List[str]   # ["BULLISH", "BULLISH"] etc
    combined_strength: int


@dataclass
class ICTSetupScore:
    """Comprehensive ICT setup quality scoring."""
    total:        float     # 0–100
    grade:        str       # "A+" | "A" | "B" | "C" | "D" | "WAIT"
    has_fvg:      bool
    has_breaker:  bool
    has_discount_zone: bool
    in_killzone:  bool
    has_sweep:    bool
    has_displacement: bool
    components:   Dict[str, float]
    description:  str


@dataclass
class FVGBreakerResult:
    # FVGs
    bullish_fvgs:    List[FVG]
    bearish_fvgs:    List[FVG]
    all_fvgs:        List[FVG]
    fvg_stacks:      List[FVGStack]

    # Breakers
    bullish_breakers: List[BreakerBlock]
    bearish_breakers: List[BreakerBlock]
    all_breakers:     List[BreakerBlock]

    # Rejection blocks
    rejection_blocks: List[RejectionBlock]

    # Context
    current_price:    float
    atr:              float
    nearest_bullish_fvg: Optional[FVG]
    nearest_bearish_fvg: Optional[FVG]
    nearest_breaker:     Optional[BreakerBlock]

    # Stats
    total_fvgs:       int
    fresh_fvgs:       int
    inverted_fvgs:    int
    institutional_fvgs: int
    total_breakers:   int
    stacked_zones:    int

    # Signals
    fvg_signal:       str
    breaker_signal:   str
    entry_bias:       str
    ict_setup:        ICTSetupScore
    confluence_score: int

    signals:          List[str] = field(default_factory=list)
    warnings:         List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════
# Engine
# ═══════════════════════════════════════════════════════

class FVGBreakerEngine:

    def __init__(self, min_gap_atr_mult: float = 0.08):
        self.min_gap_atr_mult = min_gap_atr_mult

    # ─────────────────── main entry ──────────────────────

    def analyze(self, df: pd.DataFrame, lookback: int = 150) -> FVGBreakerResult:
        if df is None or len(df) < 10:
            return self._empty()

        df = df.tail(lookback).copy().reset_index(drop=True)
        n  = len(df)

        h  = df["high"].astype(float).values
        l  = df["low"].astype(float).values
        o  = df["open"].astype(float).values
        c  = df["close"].astype(float).values
        v  = df["volume"].astype(float).values if "volume" in df.columns else np.ones(n)

        price = float(c[-1])
        atr   = self._atr(h, l, c)
        avg_v = float(np.mean(v))

        # ── detect all structures ──────────────────────
        bull_fvgs, bear_fvgs = self._detect_fvgs(h, l, o, c, v, atr, avg_v, n)
        bull_fvgs = self._update_fvg_status(bull_fvgs, h, l, c)
        bear_fvgs = self._update_fvg_status(bear_fvgs, h, l, c)
        bull_fvgs = self._add_fvg_entry_zones(bull_fvgs, price, atr)
        bear_fvgs = self._add_fvg_entry_zones(bear_fvgs, price, atr)

        stacks = self._detect_stacks(bull_fvgs + bear_fvgs)

        bull_bbs, bear_bbs = self._detect_breakers(h, l, o, c, v, atr, avg_v)
        bull_bbs = self._add_breaker_entry_zones(bull_bbs, price, atr)
        bear_bbs = self._add_breaker_entry_zones(bear_bbs, price, atr)

        rbs = self._detect_rejection_blocks(h, l, o, c, atr)

        # ── active (non-filled) sorted by strength ─────
        active_bull = sorted([f for f in bull_fvgs if f.status != "FILLED"], key=lambda f: f.strength, reverse=True)
        active_bear = sorted([f for f in bear_fvgs if f.status != "FILLED"], key=lambda f: f.strength, reverse=True)
        all_fvgs    = sorted(active_bull + active_bear, key=lambda f: f.strength, reverse=True)
        all_bbs     = sorted(bull_bbs + bear_bbs, key=lambda b: b.strength, reverse=True)

        # ── nearest levels ─────────────────────────────
        bull_below = [f for f in active_bull if f.gap_high < price]
        bear_above = [f for f in active_bear if f.gap_low  > price]
        nb = max(bull_below, key=lambda f: f.gap_high)   if bull_below else None
        na = min(bear_above, key=lambda f: f.gap_low)    if bear_above else None
        nr = min(all_bbs,    key=lambda b: abs(b.midpoint - price)) if all_bbs else None

        # ── signals ────────────────────────────────────
        signals, warnings, fvg_sig, brk_sig, bias_score = self._compute_signals(
            active_bull, active_bear, all_bbs, nb, na, nr, price, atr
        )

        # ── ICT setup score ────────────────────────────
        ict = self._compute_ict_score(
            active_bull, active_bear, bull_bbs, bear_bbs, rbs, stacks,
            price, atr, bias_score
        )

        if bias_score >= 4:
            entry_bias = "STRONG_BUY"
        elif bias_score >= 2:
            entry_bias = "BUY"
        elif bias_score <= -4:
            entry_bias = "STRONG_SELL"
        elif bias_score <= -2:
            entry_bias = "SELL"
        else:
            entry_bias = "NEUTRAL"

        return FVGBreakerResult(
            bullish_fvgs=bull_fvgs,
            bearish_fvgs=bear_fvgs,
            all_fvgs=all_fvgs,
            fvg_stacks=stacks,
            bullish_breakers=bull_bbs,
            bearish_breakers=bear_bbs,
            all_breakers=all_bbs,
            rejection_blocks=rbs,
            current_price=price,
            atr=atr,
            nearest_bullish_fvg=nb,
            nearest_bearish_fvg=na,
            nearest_breaker=nr,
            total_fvgs=len(all_fvgs),
            fresh_fvgs=sum(1 for f in all_fvgs if f.status == "FRESH"),
            inverted_fvgs=sum(1 for f in all_fvgs if f.is_inverted),
            institutional_fvgs=sum(1 for f in all_fvgs if f.is_institutional),
            total_breakers=len(all_bbs),
            stacked_zones=len(stacks),
            fvg_signal=fvg_sig,
            breaker_signal=brk_sig,
            entry_bias=entry_bias,
            ict_setup=ict,
            confluence_score=min(10, abs(bias_score)),
            signals=signals,
            warnings=warnings,
        )

    # ─────────────────── FVG detection ───────────────────

    def _detect_fvgs(self, h, l, o, c, v, atr, avg_v, n) -> Tuple[List[FVG], List[FVG]]:
        bull, bear = [], []
        fid = 0
        for i in range(1, n - 1):
            age = n - 1 - i

            # ── Bullish FVG: gap between h[i-1] and l[i+1] ──
            bl = float(h[i - 1])
            bh = float(l[i + 1])
            if bh > bl:
                size = bh - bl
                if size >= atr * self.min_gap_atr_mult:
                    am  = size / atr if atr > 0 else 0
                    ce  = (bh + bl) / 2
                    vr  = v[i] / avg_v if avg_v > 0 else 1
                    ins = am >= 1.5
                    imp = c[i] > o[i]  # impulse in direction
                    str_ = self._fvg_strength(size, atr, v[i], avg_v, ins, imp, age, n)
                    bull.append(FVG(
                        id=fid, type="BULLISH",
                        gap_high=round(bh,6), gap_low=round(bl,6),
                        ce_level=round(ce,6), size=round(size,6),
                        size_atr_mult=round(am,3), bar_idx=i, bar_age=age,
                        status="FRESH", is_inverted=False, fill_pct=0.0,
                        displacement_vol=float(v[i]), avg_vol=avg_v,
                        vol_ratio=round(vr,2),
                        is_institutional=ins, is_stacked=False, stack_count=0,
                        strength=str_,
                    ))
                    fid += 1

            # ── Bearish FVG: gap between l[i-1] and h[i+1] ──
            bah = float(l[i - 1])
            bal = float(h[i + 1])
            if bah > bal:
                size = bah - bal
                if size >= atr * self.min_gap_atr_mult:
                    am  = size / atr if atr > 0 else 0
                    ce  = (bah + bal) / 2
                    vr  = v[i] / avg_v if avg_v > 0 else 1
                    ins = am >= 1.5
                    imp = c[i] < o[i]
                    str_ = self._fvg_strength(size, atr, v[i], avg_v, ins, imp, age, n)
                    bear.append(FVG(
                        id=fid, type="BEARISH",
                        gap_high=round(bah,6), gap_low=round(bal,6),
                        ce_level=round(ce,6), size=round(size,6),
                        size_atr_mult=round(am,3), bar_idx=i, bar_age=age,
                        status="FRESH", is_inverted=False, fill_pct=0.0,
                        displacement_vol=float(v[i]), avg_vol=avg_v,
                        vol_ratio=round(vr,2),
                        is_institutional=ins, is_stacked=False, stack_count=0,
                        strength=str_,
                    ))
                    fid += 1

        return bull, bear

    def _fvg_strength(self, size, atr, vol, avg_v, is_inst, is_impulse, age, n) -> int:
        s = 35
        # size bonus (up to 30)
        s += min(30, int((size / atr) * 20)) if atr > 0 else 0
        # volume bonus (up to 15)
        vr = vol / avg_v if avg_v > 0 else 1
        s += min(15, int((vr - 1) * 8))
        # institutional
        if is_inst:  s += 12
        # alignment
        if is_impulse: s += 8
        else: s -= 5
        # recency bonus (newer = stronger, max 10)
        recency = max(0, 10 - int(age / n * 50))
        s += recency
        return max(0, min(100, s))

    def _update_fvg_status(self, fvgs: List[FVG], h, l, c) -> List[FVG]:
        for fvg in fvgs:
            si = fvg.bar_idx + 2
            if si >= len(c):
                continue
            sh = h[si:]
            sl = l[si:]
            if fvg.type == "BULLISH":
                mn = float(sl.min()) if len(sl) else fvg.gap_high
                if mn <= fvg.gap_low:
                    fvg.status, fvg.fill_pct = "FILLED", 1.0
                elif mn < fvg.gap_high:
                    fvg.fill_pct = (fvg.gap_high - mn) / fvg.size
                    fvg.status = "INVERTED" if fvg.fill_pct > 0.8 else "PARTIAL"
                    if fvg.fill_pct > 0.8: fvg.is_inverted = True
            else:
                mx = float(sh.max()) if len(sh) else fvg.gap_low
                if mx >= fvg.gap_high:
                    fvg.status, fvg.fill_pct = "FILLED", 1.0
                elif mx > fvg.gap_low:
                    fvg.fill_pct = (mx - fvg.gap_low) / fvg.size
                    fvg.status = "INVERTED" if fvg.fill_pct > 0.8 else "PARTIAL"
                    if fvg.fill_pct > 0.8: fvg.is_inverted = True
        return fvgs

    def _add_fvg_entry_zones(self, fvgs: List[FVG], price: float, atr: float) -> List[FVG]:
        for fvg in fvgs:
            if fvg.status == "FILLED":
                continue
            if fvg.type == "BULLISH":
                entry = fvg.ce_level
                sl    = fvg.gap_low - atr * 0.1
                tp1   = price + (entry - sl) * 1.5
                tp2   = price + (entry - sl) * 2.0
                tp3   = price + (entry - sl) * 3.0
            else:
                entry = fvg.ce_level
                sl    = fvg.gap_high + atr * 0.1
                tp1   = price - (sl - entry) * 1.5
                tp2   = price - (sl - entry) * 2.0
                tp3   = price - (sl - entry) * 3.0

            risk    = abs(entry - sl)
            rr1     = abs(tp1 - entry) / risk if risk > 0 else 0
            rr2     = abs(tp2 - entry) / risk if risk > 0 else 0
            risk_p  = risk / entry * 100 if entry > 0 else 0
            quality = "IDEAL" if fvg.strength >= 70 else "GOOD" if fvg.strength >= 50 else "VALID"

            fvg.entry_zone = EntryZone(
                entry_price=round(entry, 6), stop_loss=round(sl, 6),
                tp1=round(tp1, 6), tp2=round(tp2, 6), tp3=round(tp3, 6),
                rr_tp1=round(rr1, 2), rr_tp2=round(rr2, 2),
                risk_pct=round(risk_p, 3), entry_quality=quality,
            )
        return fvgs

    # ─────────────────── FVG Stack ───────────────────────

    def _detect_stacks(self, fvgs: List[FVG]) -> List[FVGStack]:
        """Find overlapping FVGs (stacked imbalances = stronger magnet)."""
        stacks = []
        used   = set()
        active = [f for f in fvgs if f.status not in ("FILLED",)]

        for i, a in enumerate(active):
            if i in used:
                continue
            group = [a]
            for j, b in enumerate(active):
                if i == j or j in used:
                    continue
                # Check overlap
                overlap_hi = min(a.gap_high, b.gap_high)
                overlap_lo = max(a.gap_low,  b.gap_low)
                if overlap_hi > overlap_lo:
                    group.append(b)
                    used.add(j)

            if len(group) >= 2:
                used.add(i)
                zh = max(g.gap_high for g in group)
                zl = min(g.gap_low  for g in group)
                cs = min(100, int(np.mean([g.strength for g in group])) + len(group) * 8)
                stacks.append(FVGStack(
                    zone_high=zh, zone_low=zl, count=len(group),
                    types=[g.type for g in group],
                    combined_strength=cs,
                ))
                for g in group:
                    g.is_stacked  = True
                    g.stack_count = len(group)
                    g.strength    = min(100, g.strength + len(group) * 5)

        return stacks

    # ─────────────────── Breaker Blocks ──────────────────

    def _detect_breakers(self, h, l, o, c, v, atr, avg_v) -> Tuple[List[BreakerBlock], List[BreakerBlock]]:
        bull_bb, bear_bb = [], []
        n  = len(c)
        bid = 0

        # ── swing points (5-bar fractal) ──
        sh_pts = [(i, float(h[i])) for i in range(2, n-2) if h[i] == max(h[i-2:i+3])]
        sl_pts = [(i, float(l[i])) for i in range(2, n-2) if l[i] == min(l[i-2:i+3])]

        # ── Bullish Breaker: swing low broken upward ──
        for sl_idx, sl_price in sl_pts[:-2]:
            subs = c[sl_idx+1:]
            breaks = np.where(subs > sl_price)[0]
            if len(breaks) == 0: continue
            bi  = sl_idx + 1 + int(breaks[0])
            if bi >= n: continue
            bsz = c[bi] - sl_price
            if bsz < atr * 0.25: continue

            post = l[bi+1:]
            returns = np.where((post <= sl_price * 1.003) & (post >= sl_price * 0.99))[0]
            tc  = len(returns)
            hr  = tc > 0

            # OTE entry: 62% retrace of the OB zone
            ob_h = sl_price + atr * 0.3
            ob_l = sl_price - atr * 0.15
            ote  = ob_l + (ob_h - ob_l) * 0.62

            vol_mult = float(v[bi]) / avg_v if avg_v > 0 else 1
            str_ = min(100, 45 + int((bsz / atr) * 18) + int(vol_mult * 5) + (10 if hr else 0))

            bull_bb.append(BreakerBlock(
                id=bid, type="BULLISH_BREAKER",
                ob_high=round(ob_h,6), ob_low=round(ob_l,6), midpoint=round(sl_price,6),
                ote_entry=round(ote,6),
                break_candle_idx=bi, break_price=round(float(c[bi]),6),
                break_direction="UPWARD",
                break_strength=round(bsz/atr,2),
                status="TESTED" if hr else "ACTIVE",
                test_count=tc, has_returned=hr, strength=str_,
            ))
            bid += 1

        # ── Bearish Breaker: swing high broken downward ──
        for sh_idx, sh_price in sh_pts[:-2]:
            subs = c[sh_idx+1:]
            breaks = np.where(subs < sh_price)[0]
            if len(breaks) == 0: continue
            bi  = sh_idx + 1 + int(breaks[0])
            if bi >= n: continue
            bsz = sh_price - c[bi]
            if bsz < atr * 0.25: continue

            post = h[bi+1:]
            returns = np.where((post >= sh_price * 0.997) & (post <= sh_price * 1.01))[0]
            tc  = len(returns)
            hr  = tc > 0

            ob_h = sh_price + atr * 0.15
            ob_l = sh_price - atr * 0.3
            ote  = ob_h - (ob_h - ob_l) * 0.62

            vol_mult = float(v[bi]) / avg_v if avg_v > 0 else 1
            str_ = min(100, 45 + int((bsz / atr) * 18) + int(vol_mult * 5) + (10 if hr else 0))

            bear_bb.append(BreakerBlock(
                id=bid, type="BEARISH_BREAKER",
                ob_high=round(ob_h,6), ob_low=round(ob_l,6), midpoint=round(sh_price,6),
                ote_entry=round(ote,6),
                break_candle_idx=bi, break_price=round(float(c[bi]),6),
                break_direction="DOWNWARD",
                break_strength=round(bsz/atr,2),
                status="TESTED" if hr else "ACTIVE",
                test_count=tc, has_returned=hr, strength=str_,
            ))
            bid += 1

        bull_bb = sorted(bull_bb, key=lambda b: b.strength, reverse=True)[:6]
        bear_bb = sorted(bear_bb, key=lambda b: b.strength, reverse=True)[:6]
        return bull_bb, bear_bb

    def _add_breaker_entry_zones(self, bbs: List[BreakerBlock], price: float, atr: float) -> List[BreakerBlock]:
        for bb in bbs:
            if bb.type == "BULLISH_BREAKER":
                entry = bb.ote_entry
                sl    = bb.ob_low - atr * 0.1
                dir_  = 1
            else:
                entry = bb.ote_entry
                sl    = bb.ob_high + atr * 0.1
                dir_  = -1

            risk = abs(entry - sl)
            tp1  = entry + dir_ * risk * 1.5
            tp2  = entry + dir_ * risk * 2.5
            tp3  = entry + dir_ * risk * 4.0
            rr1  = abs(tp1 - entry) / risk if risk > 0 else 0
            rr2  = abs(tp2 - entry) / risk if risk > 0 else 0
            rp   = risk / entry * 100 if entry > 0 else 0

            bb.entry_zone = EntryZone(
                entry_price=round(entry,6), stop_loss=round(sl,6),
                tp1=round(tp1,6), tp2=round(tp2,6), tp3=round(tp3,6),
                rr_tp1=round(rr1,2), rr_tp2=round(rr2,2),
                risk_pct=round(rp,3),
                entry_quality="IDEAL" if bb.strength >= 70 else "GOOD" if bb.strength >= 50 else "VALID",
            )
        return bbs

    # ─────────────────── Rejection Blocks ────────────────

    def _detect_rejection_blocks(self, h, l, o, c, atr) -> List[RejectionBlock]:
        rbs = []
        n = len(c)
        for i in range(2, n):
            rng = h[i] - l[i]
            if rng < atr * 0.3: continue
            body  = abs(c[i] - o[i])
            uw    = h[i] - max(c[i], o[i])
            lw    = min(c[i], o[i]) - l[i]

            # Bearish RB: upper wick > 60% of range
            if uw > rng * 0.6 and uw > body * 2:
                wm = uw / rng
                rbs.append(RejectionBlock(
                    id=len(rbs), type="BEARISH_RB",
                    zone_high=round(float(h[i]),6),
                    zone_low=round(float(max(c[i],o[i])),6),
                    wick_pct=round(wm*100,1), bar_idx=i,
                    strength=min(100, int(wm*80 + body/rng*20)),
                ))
            # Bullish RB: lower wick > 60% of range
            elif lw > rng * 0.6 and lw > body * 2:
                wm = lw / rng
                rbs.append(RejectionBlock(
                    id=len(rbs), type="BULLISH_RB",
                    zone_high=round(float(min(c[i],o[i])),6),
                    zone_low=round(float(l[i]),6),
                    wick_pct=round(wm*100,1), bar_idx=i,
                    strength=min(100, int(wm*80 + body/rng*20)),
                ))

        # Return 5 strongest of each type
        bull_rbs = sorted([r for r in rbs if r.type == "BULLISH_RB"], key=lambda r: r.strength, reverse=True)[:5]
        bear_rbs = sorted([r for r in rbs if r.type == "BEARISH_RB"], key=lambda r: r.strength, reverse=True)[:5]
        return bull_rbs + bear_rbs

    # ─────────────────── Signals ─────────────────────────

    def _compute_signals(self, bull_fvgs, bear_fvgs, all_bbs, nb, na, nr, price, atr):
        sigs, warns = [], []
        bs   = 0
        fs   = "NEUTRAL"
        brs  = "NEUTRAL"

        in_bull = any(f.gap_low <= price <= f.gap_high for f in bull_fvgs)
        in_bear = any(f.gap_low <= price <= f.gap_high for f in bear_fvgs)

        if in_bull:
            fs = "PRICE_IN_BULLISH_FVG"; bs += 3
            sigs.append("✅ Price INSIDE Bullish FVG — highest probability BUY zone")
        elif in_bear:
            fs = "PRICE_IN_BEARISH_FVG"; bs -= 3
            sigs.append("🔴 Price INSIDE Bearish FVG — highest probability SELL zone")
        elif nb:
            d = (price - nb.gap_high) / price * 100
            fs = "BULLISH_FVG_BELOW"
            sigs.append(f"📊 Bullish FVG {d:.2f}% below — gravitational pull (CE: {nb.ce_level:,.2f})")
            if d < 0.5: bs += 2
        elif na:
            d = (na.gap_low - price) / price * 100
            fs = "BEARISH_FVG_ABOVE"
            sigs.append(f"📊 Bearish FVG {d:.2f}% above — gravitational pull (CE: {na.ce_level:,.2f})")
            if d < 0.5: bs -= 2

        # Breaker proximity
        if nr:
            d = abs(price - nr.midpoint) / price * 100
            if d < 0.3:
                brs = "PRICE_AT_BREAKER"; bs += 3 if "BULLISH" in nr.type else -3
                sigs.append(f"🧱 {'BUY' if 'BULLISH' in nr.type else 'SELL'}: Price AT {'Bullish' if 'BULLISH' in nr.type else 'Bearish'} Breaker Block!")
                if nr.has_returned:
                    sigs.append(f"   ↳ Breaker already tested {nr.test_count}x — confirmation strong")
            elif "BULLISH" in nr.type:
                brs = "BULLISH_BREAKER_BELOW"; bs += 1
                sigs.append(f"🧱 Bullish Breaker {d:.2f}% below (midpoint: {nr.midpoint:,.2f})")
            else:
                brs = "BEARISH_BREAKER_ABOVE"; bs -= 1
                sigs.append(f"🧱 Bearish Breaker {d:.2f}% above (midpoint: {nr.midpoint:,.2f})")

        # Stack bonus
        bull_stacked = [f for f in bull_fvgs if f.is_stacked]
        bear_stacked = [f for f in bear_fvgs if f.is_stacked]
        if bull_stacked:
            bs += 1
            sigs.append(f"🔥 FVG Stack detected ({bull_stacked[0].stack_count} overlapping Bullish FVGs)")
        if bear_stacked:
            bs -= 1
            sigs.append(f"🔥 FVG Stack detected ({bear_stacked[0].stack_count} overlapping Bearish FVGs)")

        # Institutional
        inst = [f for f in bull_fvgs + bear_fvgs if f.is_institutional]
        if inst:
            sigs.append(f"🐳 {len(inst)} Institutional FVG(s) — gap > 1.5x ATR")

        # Warnings
        if len(bull_fvgs) > 8:
            warns.append("⚠️ Many bullish FVGs — heavily imbalanced market, expect volatility")
        if len(bear_fvgs) > 8:
            warns.append("⚠️ Many bearish FVGs — heavily imbalanced market")

        return sigs, warns, fs, brs, bs

    # ─────────────────── ICT Setup Score ─────────────────

    def _compute_ict_score(self, bull_fvgs, bear_fvgs, bull_bbs, bear_bbs, rbs, stacks, price, atr, bias_score) -> ICTSetupScore:
        comps: Dict[str, float] = {}
        bull_bias = bias_score > 0

        # FVG presence (max 25)
        fvg_s = 0
        active = bull_fvgs if bull_bias else bear_fvgs
        if active:
            best = active[0]
            fvg_s = min(25, int(best.strength * 0.25))
            if best.is_stacked:  fvg_s = min(25, fvg_s + 5)
            if best.is_institutional: fvg_s = min(25, fvg_s + 3)
        comps["FVG"] = fvg_s

        # Breaker presence (max 20)
        bb_s = 0
        bbs = bull_bbs if bull_bias else bear_bbs
        if bbs:
            best_bb = bbs[0]
            bb_s = min(20, int(best_bb.strength * 0.20))
            if best_bb.has_returned: bb_s = min(20, bb_s + 5)
        comps["Breaker"] = bb_s

        # Rejection blocks (max 10)
        rb_type = "BULLISH_RB" if bull_bias else "BEARISH_RB"
        rb_s = min(10, len([r for r in rbs if r.type == rb_type]) * 3)
        comps["RejectionBlock"] = rb_s

        # Stack bonus (max 10)
        stk_s = min(10, len(stacks) * 4)
        comps["FVGStack"] = stk_s

        # Bias strength (max 15)
        bias_s = min(15, abs(bias_score) * 3)
        comps["BiasStrength"] = bias_s

        # Placeholder scores (would improve with market context)
        comps["Killzone"]     = 0   # Would need time info
        comps["Sweep"]        = 0   # Would need sweep engine
        comps["Displacement"] = min(10, int(fvg_s * 0.4))  # Proxy: FVG implies displacement

        total = sum(comps.values())
        grade = ("A+" if total >= 60 else "A" if total >= 48 else
                 "B"  if total >= 35 else "C" if total >= 22 else
                 "D"  if total >= 10 else "WAIT")

        desc_map = {
            "A+": "Ultra High Conviction — Full ICT confluence. Execute with confidence.",
            "A":  "High Conviction — Strong FVG/Breaker alignment. Valid entry.",
            "B":  "Moderate Conviction — Good setup, some confluence missing.",
            "C":  "Low Conviction — Partial signals only. Use smaller size.",
            "D":  "Weak Setup — Insufficient confluence. Wait for better entry.",
            "WAIT": "No Edge — Do not trade. Wait for clear ICT setup.",
        }

        return ICTSetupScore(
            total=round(total, 1),
            grade=grade,
            has_fvg=len(active) > 0,
            has_breaker=len(bbs) > 0,
            has_discount_zone=False,  # Requires PDZone engine
            in_killzone=False,        # Requires session time
            has_sweep=False,          # Requires sweep engine
            has_displacement=fvg_s > 0,
            components=comps,
            description=desc_map[grade],
        )

    # ─────────────────── helpers ──────────────────────────

    def _atr(self, h, l, c, p=14) -> float:
        if len(c) < 2: return 1.0
        trs = [max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])) for i in range(1, len(c))]
        return float(np.mean(trs[-p:])) if trs else 1.0

    def _empty(self) -> FVGBreakerResult:
        ict = ICTSetupScore(0,"WAIT",False,False,False,False,False,False,{},"No data")
        return FVGBreakerResult(
            bullish_fvgs=[],bearish_fvgs=[],all_fvgs=[],fvg_stacks=[],
            bullish_breakers=[],bearish_breakers=[],all_breakers=[],rejection_blocks=[],
            current_price=0,atr=0,nearest_bullish_fvg=None,nearest_bearish_fvg=None,
            nearest_breaker=None,total_fvgs=0,fresh_fvgs=0,inverted_fvgs=0,
            institutional_fvgs=0,total_breakers=0,stacked_zones=0,
            fvg_signal="NEUTRAL",breaker_signal="NEUTRAL",entry_bias="NEUTRAL",
            ict_setup=ict,confluence_score=0,
        )

    # ─────────────────── serialization ───────────────────

    def _entry_zone_dict(self, ez: Optional[EntryZone]) -> Optional[dict]:
        if not ez: return None
        return {
            "entry": ez.entry_price, "stop_loss": ez.stop_loss,
            "tp1": ez.tp1, "tp2": ez.tp2, "tp3": ez.tp3,
            "rr_tp1": ez.rr_tp1, "rr_tp2": ez.rr_tp2,
            "risk_pct": ez.risk_pct, "quality": ez.entry_quality,
        }

    def fvg_to_dict(self, f: FVG) -> dict:
        return {
            "id": f.id, "type": f.type,
            "gap_high": f.gap_high, "gap_low": f.gap_low, "ce_level": f.ce_level,
            "size": f.size, "size_atr_mult": f.size_atr_mult,
            "bar_idx": f.bar_idx, "bar_age": f.bar_age,
            "status": f.status, "is_inverted": f.is_inverted,
            "fill_pct": round(f.fill_pct * 100, 1),
            "vol_ratio": f.vol_ratio,
            "is_institutional": f.is_institutional,
            "is_stacked": f.is_stacked, "stack_count": f.stack_count,
            "strength": f.strength,
            "entry_zone": self._entry_zone_dict(f.entry_zone),
        }

    def breaker_to_dict(self, b: BreakerBlock) -> dict:
        return {
            "id": b.id, "type": b.type,
            "ob_high": b.ob_high, "ob_low": b.ob_low,
            "midpoint": b.midpoint, "ote_entry": b.ote_entry,
            "break_price": b.break_price, "break_direction": b.break_direction,
            "break_strength": b.break_strength,
            "status": b.status, "test_count": b.test_count, "has_returned": b.has_returned,
            "strength": b.strength,
            "entry_zone": self._entry_zone_dict(b.entry_zone),
        }

    def rb_to_dict(self, r: RejectionBlock) -> dict:
        return {
            "id": r.id, "type": r.type,
            "zone_high": r.zone_high, "zone_low": r.zone_low,
            "wick_pct": r.wick_pct, "bar_idx": r.bar_idx, "strength": r.strength,
        }

    def to_dict(self, r: FVGBreakerResult) -> dict:
        return {
            "current_price": r.current_price,
            "atr": r.atr,
            "summary": {
                "total_fvgs": r.total_fvgs, "fresh_fvgs": r.fresh_fvgs,
                "inverted_fvgs": r.inverted_fvgs, "institutional_fvgs": r.institutional_fvgs,
                "total_breakers": r.total_breakers, "stacked_zones": r.stacked_zones,
            },
            "bullish_fvgs":     [self.fvg_to_dict(f) for f in r.bullish_fvgs if f.status != "FILLED"],
            "bearish_fvgs":     [self.fvg_to_dict(f) for f in r.bearish_fvgs if f.status != "FILLED"],
            "top_fvgs":         [self.fvg_to_dict(f) for f in r.all_fvgs[:10]],
            "bullish_breakers": [self.breaker_to_dict(b) for b in r.bullish_breakers],
            "bearish_breakers": [self.breaker_to_dict(b) for b in r.bearish_breakers],
            "rejection_blocks": [self.rb_to_dict(rb) for rb in r.rejection_blocks[:8]],
            "fvg_stacks":       [{"zone_high": s.zone_high, "zone_low": s.zone_low, "count": s.count, "types": s.types, "strength": s.combined_strength} for s in r.fvg_stacks],
            "nearest": {
                "bullish_fvg": self.fvg_to_dict(r.nearest_bullish_fvg) if r.nearest_bullish_fvg else None,
                "bearish_fvg": self.fvg_to_dict(r.nearest_bearish_fvg) if r.nearest_bearish_fvg else None,
                "breaker":     self.breaker_to_dict(r.nearest_breaker)  if r.nearest_breaker else None,
            },
            "ict_setup": {
                "total":        r.ict_setup.total,
                "grade":        r.ict_setup.grade,
                "description":  r.ict_setup.description,
                "components":   r.ict_setup.components,
                "has_fvg":      r.ict_setup.has_fvg,
                "has_breaker":  r.ict_setup.has_breaker,
                "has_displacement": r.ict_setup.has_displacement,
            },
            "signals": {
                "fvg_signal":       r.fvg_signal,
                "breaker_signal":   r.breaker_signal,
                "entry_bias":       r.entry_bias,
                "confluence_score": r.confluence_score,
                "messages":         r.signals,
                "warnings":         r.warnings,
            },
        }
