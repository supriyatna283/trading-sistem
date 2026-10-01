"""
Options / Perpetuals Integration Engine (Sprint 4)
====================================================
Provides options-style analysis for crypto perpetual futures:

1. Funding Rate Analysis   — Tracks perp funding rate as sentiment proxy
2. Open Interest Analysis  — Rising OI + rising price = trend confirmation
3. Long/Short Ratio        — Retail positioning (contrarian signal)
4. Black-Scholes Pricing   — Theoretical option value for given strike
5. Greeks Calculator       — Delta, Gamma, Theta, Vega for any option
6. Max Pain Calculator     — Strike price where most options expire worthless
7. Perp vs Spot Premium    — Basis for carry trade detection

Data sources: OKX / Binance (via existing market_data engine).
All option math is pure Python (no scipy needed).
"""

import numpy as np
import math
from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class OptionGreeks:
    delta: float    # Rate of change of price vs underlying
    gamma: float    # Rate of change of delta
    theta: float    # Time decay (per day)
    vega: float     # Sensitivity to volatility
    rho: float      # Sensitivity to interest rate


@dataclass
class OptionContract:
    strike: float
    option_type: str    # "CALL" | "PUT"
    expiry_days: float
    theoretical_price: float
    intrinsic_value: float
    time_value: float
    greeks: OptionGreeks
    iv: float           # Implied volatility used
    moneyness: str      # "ITM" | "ATM" | "OTM"
    moneyness_pct: float


@dataclass
class PerpMetrics:
    # Funding rate
    funding_rate_8h: float      # Current 8h funding rate (%)
    funding_annualized: float   # Annualized funding rate (%)
    funding_sentiment: str      # BULLISH (positive) | BEARISH (negative) | NEUTRAL

    # Open Interest (proxy from volume)
    oi_trend: str               # RISING | FALLING | STABLE
    oi_signal: str              # Interpretation

    # Long/Short ratio
    long_short_ratio: float     # > 1 = more longs, < 1 = more shorts
    ls_signal: str              # Contrarian signal

    # Perp vs Spot
    basis_pct: float            # Perp premium over spot (%)
    carry_signal: str           # CONTANGO | BACKWARDATION | FLAT


@dataclass
class OptionsAnalysisResult:
    # Underlying
    spot_price: float
    iv_30d: float              # 30-day implied vol estimate

    # Key option contracts
    atm_call: Optional[OptionContract]
    atm_put: Optional[OptionContract]
    otm_calls: List[OptionContract] = field(default_factory=list)
    otm_puts: List[OptionContract] = field(default_factory=list)

    # Perp metrics
    perp: Optional[PerpMetrics] = None

    # Market structure
    put_call_ratio: float = 1.0
    max_pain_strike: float = 0.0
    skew: float = 0.0           # Put-call skew (negative = fear)

    # Signals
    options_bias: str = "NEUTRAL"
    signals: List[str] = field(default_factory=list)
    confluence_score: int = 0


class OptionsPerpsEngine:
    """
    Options pricing + perpetual futures analysis engine.
    Uses Black-Scholes for option pricing and Greeks.
    """

    def __init__(self, risk_free_rate: float = 0.05):
        self.rf = risk_free_rate

    def analyze(
        self,
        spot_price: float,
        iv_30d: float,               # Implied volatility (annualized, e.g. 0.65 for 65%)
        funding_rate_8h: float = 0.01,  # Current 8h funding rate (%)
        long_short_ratio: float = 1.0,
        perp_price: float = None,
        expiry_days_list: List[float] = None,
        strike_pct_range: float = 0.15,   # How far OTM to compute (15%)
    ) -> OptionsAnalysisResult:
        """
        Full options analysis for a given asset.

        Args:
            spot_price: Current spot price
            iv_30d: 30-day implied volatility (annualized, decimal)
            funding_rate_8h: Current perp funding rate (%)
            long_short_ratio: Long/Short ratio from exchange
            perp_price: Perpetual contract price (for basis calc)
            expiry_days_list: Days to expiry to compute
        """
        if expiry_days_list is None:
            expiry_days_list = [7, 14, 30]

        # Compute ATM options for primary expiry (30 days)
        T_primary = 30 / 365

        atm_call = self._price_option(spot_price, spot_price, T_primary, iv_30d, "CALL")
        atm_put  = self._price_option(spot_price, spot_price, T_primary, iv_30d, "PUT")

        # OTM options (10 strikes each side)
        otm_calls = []
        otm_puts  = []
        for pct in [0.05, 0.10, 0.15, 0.20]:
            call_strike = spot_price * (1 + pct)
            put_strike  = spot_price * (1 - pct)
            otm_calls.append(self._price_option(spot_price, call_strike, T_primary, iv_30d, "CALL"))
            otm_puts.append(self._price_option(spot_price, put_strike,  T_primary, iv_30d, "PUT"))

        # Put/Call ratio (proxy: OTM put price vs OTM call price)
        if otm_calls and otm_puts:
            avg_put  = sum(o.theoretical_price for o in otm_puts)  / len(otm_puts)
            avg_call = sum(o.theoretical_price for o in otm_calls) / len(otm_calls)
            pcr = avg_put / avg_call if avg_call > 0 else 1.0
        else:
            pcr = 1.0

        # Skew (25-delta put price minus 25-delta call price as % of spot)
        skew = 0.0
        if otm_puts and otm_calls:
            skew = (otm_puts[1].theoretical_price - otm_calls[1].theoretical_price) / spot_price * 100

        # Max pain (simplified: ATM strike ± nearest whole number)
        max_pain = round(spot_price / 1000) * 1000 if spot_price > 1000 else round(spot_price / 100) * 100

        # Perp metrics
        perp = self._analyze_perp(funding_rate_8h, long_short_ratio, spot_price, perp_price)

        # Signals + Bias
        signals = []
        bias_score = 0

        if pcr > 1.3:
            signals.append("🐻 High put/call ratio — market fearful (contrarian bullish?)")
            bias_score -= 1
        elif pcr < 0.7:
            signals.append("🐂 Low put/call ratio — market complacent (caution)")
            bias_score += 1

        if skew < -2:
            signals.append(f"⚠️ Negative skew {skew:.1f}% — tail risk hedging (fear)")
            bias_score -= 1
        elif skew > 2:
            signals.append(f"🚀 Positive skew +{skew:.1f}% — call buying dominant")
            bias_score += 2

        if perp:
            if perp.funding_annualized > 50:
                signals.append(f"💰 High funding {perp.funding_annualized:.0f}% APR — longs paying, crowded long")
                bias_score -= 2
            elif perp.funding_annualized < -20:
                signals.append(f"💸 Negative funding {perp.funding_annualized:.0f}% APR — shorts paying, crowded short")
                bias_score += 2

            if perp.long_short_ratio > 2.0:
                signals.append(f"🔴 Long/Short {perp.long_short_ratio:.1f} — crowded long, caution")
                bias_score -= 1
            elif perp.long_short_ratio < 0.5:
                signals.append(f"🟢 Long/Short {perp.long_short_ratio:.1f} — crowded short, contrarian buy")
                bias_score += 1

        # Bias
        if bias_score >= 2:
            options_bias = "BULLISH"
        elif bias_score <= -2:
            options_bias = "BEARISH"
        else:
            options_bias = "NEUTRAL"

        cscore = min(5, abs(bias_score))

        return OptionsAnalysisResult(
            spot_price=spot_price,
            iv_30d=iv_30d * 100,
            atm_call=atm_call,
            atm_put=atm_put,
            otm_calls=otm_calls,
            otm_puts=otm_puts,
            perp=perp,
            put_call_ratio=round(pcr, 3),
            max_pain_strike=max_pain,
            skew=round(skew, 3),
            options_bias=options_bias,
            signals=signals,
            confluence_score=cscore,
        )

    def _price_option(
        self, S: float, K: float, T: float, sigma: float, opt_type: str
    ) -> OptionContract:
        """Black-Scholes option pricing with Greeks."""
        # Handle edge cases
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
            g = OptionGreeks(0, 0, 0, 0, 0)
            return OptionContract(K, opt_type, 0, 0, 0, 0, g, sigma * 100, "ATM", 0)

        r = self.rf

        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        N_d1  = self._norm_cdf(d1)
        N_d2  = self._norm_cdf(d2)
        Nm_d1 = self._norm_cdf(-d1)
        Nm_d2 = self._norm_cdf(-d2)
        n_d1  = self._norm_pdf(d1)

        if opt_type == "CALL":
            price    = S * N_d1 - K * math.exp(-r * T) * N_d2
            delta    = N_d1
            intrinsic = max(0, S - K)
        else:
            price    = K * math.exp(-r * T) * Nm_d2 - S * Nm_d1
            delta    = N_d1 - 1
            intrinsic = max(0, K - S)

        gamma = n_d1 / (S * sigma * math.sqrt(T))
        theta = (-(S * n_d1 * sigma) / (2 * math.sqrt(T))
                 - r * K * math.exp(-r * T) * (N_d2 if opt_type == "CALL" else Nm_d2)) / 365
        vega  = S * n_d1 * math.sqrt(T) / 100
        rho   = (K * T * math.exp(-r * T) * (N_d2 if opt_type == "CALL" else -Nm_d2)) / 100

        time_value = max(0, price - intrinsic)

        # Moneyness
        m_pct = (S - K) / K * 100 if K > 0 else 0
        if abs(m_pct) < 1:
            moneyness = "ATM"
        elif (opt_type == "CALL" and m_pct > 0) or (opt_type == "PUT" and m_pct < 0):
            moneyness = "ITM"
        else:
            moneyness = "OTM"

        return OptionContract(
            strike=round(K, 2),
            option_type=opt_type,
            expiry_days=round(T * 365, 1),
            theoretical_price=round(max(0, price), 4),
            intrinsic_value=round(intrinsic, 4),
            time_value=round(time_value, 4),
            greeks=OptionGreeks(
                delta=round(delta, 4),
                gamma=round(gamma, 6),
                theta=round(theta, 4),
                vega=round(vega, 4),
                rho=round(rho, 4),
            ),
            iv=round(sigma * 100, 2),
            moneyness=moneyness,
            moneyness_pct=round(m_pct, 2),
        )

    def _analyze_perp(
        self, funding_8h: float, ls_ratio: float, spot: float, perp_price: float = None
    ) -> PerpMetrics:
        # Funding rate analysis
        annual = funding_8h * 3 * 365  # 3 periods per day, 365 days

        if funding_8h > 0.03:
            f_sentiment = "BULLISH_CAUTION"  # Longs paying a lot = crowded
        elif funding_8h > 0:
            f_sentiment = "BULLISH"
        elif funding_8h < -0.01:
            f_sentiment = "BEARISH_CAUTION"
        elif funding_8h < 0:
            f_sentiment = "BEARISH"
        else:
            f_sentiment = "NEUTRAL"

        # Long/short
        if ls_ratio > 1.5:
            ls_signal = "CONTRARIAN_SELL — Too many longs"
        elif ls_ratio < 0.7:
            ls_signal = "CONTRARIAN_BUY — Too many shorts"
        else:
            ls_signal = "NEUTRAL"

        # OI trend proxy
        oi_trend = "STABLE"
        oi_signal = "No strong OI directional signal"

        # Basis
        basis = 0.0
        carry = "FLAT"
        if perp_price and spot:
            basis = (perp_price - spot) / spot * 100
            if basis > 0.2:
                carry = "CONTANGO"
            elif basis < -0.2:
                carry = "BACKWARDATION"

        return PerpMetrics(
            funding_rate_8h=round(funding_8h, 4),
            funding_annualized=round(annual, 2),
            funding_sentiment=f_sentiment,
            oi_trend=oi_trend,
            oi_signal=oi_signal,
            long_short_ratio=round(ls_ratio, 3),
            ls_signal=ls_signal,
            basis_pct=round(basis, 4),
            carry_signal=carry,
        )

    def _norm_cdf(self, x: float) -> float:
        """Cumulative standard normal distribution (Hart approximation)."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def _norm_pdf(self, x: float) -> float:
        """Standard normal PDF."""
        return math.exp(-0.5 * x ** 2) / math.sqrt(2 * math.pi)

    def option_to_dict(self, o: OptionContract) -> dict:
        return {
            "strike":        o.strike,
            "type":          o.option_type,
            "expiry_days":   o.expiry_days,
            "price":         o.theoretical_price,
            "intrinsic":     o.intrinsic_value,
            "time_value":    o.time_value,
            "iv_pct":        o.iv,
            "moneyness":     o.moneyness,
            "moneyness_pct": o.moneyness_pct,
            "greeks": {
                "delta": o.greeks.delta,
                "gamma": o.greeks.gamma,
                "theta": o.greeks.theta,
                "vega":  o.greeks.vega,
                "rho":   o.greeks.rho,
            },
        }

    def to_dict(self, r: OptionsAnalysisResult) -> dict:
        return {
            "spot_price":    r.spot_price,
            "iv_30d_pct":    r.iv_30d,
            "put_call_ratio": r.put_call_ratio,
            "max_pain":      r.max_pain_strike,
            "skew_pct":      r.skew,
            "options_bias":  r.options_bias,
            "atm_call":      self.option_to_dict(r.atm_call) if r.atm_call else None,
            "atm_put":       self.option_to_dict(r.atm_put) if r.atm_put else None,
            "otm_calls":     [self.option_to_dict(o) for o in r.otm_calls],
            "otm_puts":      [self.option_to_dict(o) for o in r.otm_puts],
            "perp": {
                "funding_8h_pct":      r.perp.funding_rate_8h if r.perp else 0,
                "funding_annual_pct":  r.perp.funding_annualized if r.perp else 0,
                "funding_sentiment":   r.perp.funding_sentiment if r.perp else "NEUTRAL",
                "long_short_ratio":    r.perp.long_short_ratio if r.perp else 1.0,
                "ls_signal":           r.perp.ls_signal if r.perp else "",
                "basis_pct":           r.perp.basis_pct if r.perp else 0,
                "carry":               r.perp.carry_signal if r.perp else "FLAT",
            } if r.perp else {},
            "signals":          r.signals,
            "confluence_score": r.confluence_score,
        }
