"""
GARCH Volatility Forecasting Engine (Sprint 4)
================================================
Implements GARCH(1,1) from scratch (no arch/statsmodels dependency):

GARCH(1,1) model:
  σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1}

Where:
  ω = long-run variance weight
  α = ARCH coefficient (shock weight)
  β = GARCH coefficient (persistence weight)
  ε = return residual

Outputs:
  - Current volatility estimate
  - 1/5/10-day volatility forecast
  - Volatility regime: LOW | MEDIUM | HIGH | EXTREME
  - Volatility percentile vs historical
  - ATR-based entry/stop sizing
  - Options-implied move estimation
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class GARCHForecast:
    # Current state
    current_vol_daily: float      # Current daily vol (%)
    current_vol_annual: float     # Annualized (%)
    long_run_vol: float           # Long-run / unconditional vol

    # Forecasts
    forecast_1d: float            # Tomorrow's vol
    forecast_5d: float            # 5-day ahead
    forecast_10d: float           # 10-day ahead

    # Regime
    vol_regime: str               # LOW | MEDIUM | HIGH | EXTREME
    vol_regime_color: str
    vol_percentile: float         # 0-100 vs historical

    # Model params
    omega: float                  # GARCH omega
    alpha: float                  # ARCH coefficient
    beta: float                   # GARCH coefficient
    persistence: float            # alpha + beta (< 1 = stationary)

    # Trading implications
    expected_daily_move_pct: float   # 1-sigma daily move
    expected_weekly_move_pct: float
    atr_equivalent: float            # Daily vol in price terms (given price)

    # Options pricing
    implied_move_1w_pct: float    # Estimated 1-week options move
    implied_move_1m_pct: float    # Estimated 1-month options move

    # Signal
    signal: str                   # VOLATILITY_EXPANDING | CONTRACTING | STABLE
    trade_advice: str
    confluence_score: int


class GARCHVolatilityEngine:
    """
    Pure-Python GARCH(1,1) volatility forecaster.
    No external dependencies beyond numpy.
    """

    VOL_REGIMES = {
        "LOW":     {"threshold": 0.25, "color": "#10b981"},
        "MEDIUM":  {"threshold": 0.50, "color": "#3b82f6"},
        "HIGH":    {"threshold": 0.75, "color": "#f59e0b"},
        "EXTREME": {"threshold": 1.00, "color": "#ef4444"},
    }

    def analyze(self, df: pd.DataFrame, current_price: float = None) -> GARCHForecast:
        if df is None or len(df) < 30:
            return self._empty()

        closes = df["close"].astype(float).values
        if current_price is None:
            current_price = closes[-1]

        # Log returns
        returns = np.diff(np.log(closes))
        if len(returns) < 20:
            return self._empty()

        # Fit GARCH(1,1)
        omega, alpha, beta = self._fit_garch(returns)
        persistence = alpha + beta

        # Current conditional variance
        sigma2_series = self._garch_filter(returns, omega, alpha, beta)
        current_sigma2 = sigma2_series[-1]
        current_vol_daily = float(np.sqrt(current_sigma2)) * 100

        # Long-run variance
        if 1 - persistence > 0:
            long_run_var = omega / (1 - persistence)
        else:
            long_run_var = np.var(returns)
        long_run_vol = float(np.sqrt(long_run_var)) * 100

        # Forecasts (mean-reverting GARCH variance)
        forecast_1d  = self._forecast(current_sigma2, omega, alpha, beta, 1)
        forecast_5d  = self._forecast(current_sigma2, omega, alpha, beta, 5)
        forecast_10d = self._forecast(current_sigma2, omega, alpha, beta, 10)

        # Annualize
        annual_vol = current_vol_daily * np.sqrt(252)

        # Historical volatility percentile
        historical_vols = [float(np.sqrt(v)) * 100 for v in sigma2_series]
        vol_pct = float(np.mean(np.array(historical_vols) <= current_vol_daily)) * 100

        # Regime
        regime = self._classify_regime(vol_pct)

        # Trading implications
        daily_move = current_vol_daily
        weekly_move = current_vol_daily * np.sqrt(5)
        atr_equiv = (current_vol_daily / 100) * current_price

        # Options: simplified Black-Scholes move estimate
        implied_1w = (current_vol_daily / 100) * np.sqrt(5) * current_price / current_price * 100
        implied_1m = (current_vol_daily / 100) * np.sqrt(21) * current_price / current_price * 100

        # Signal
        if forecast_1d > current_vol_daily * 1.1:
            signal = "VOLATILITY_EXPANDING"
            advice = "⚠️ Vol expanding — widen stops, reduce position size"
        elif forecast_1d < current_vol_daily * 0.9:
            signal = "VOLATILITY_CONTRACTING"
            advice = "📉 Vol contracting — tighten stops, breakout imminent"
        else:
            signal = "STABLE"
            advice = "✅ Vol stable — normal position sizing applies"

        score = (3 if signal == "VOLATILITY_CONTRACTING" else
                 2 if signal == "STABLE" else 1)

        return GARCHForecast(
            current_vol_daily=round(current_vol_daily, 4),
            current_vol_annual=round(annual_vol, 2),
            long_run_vol=round(long_run_vol, 4),
            forecast_1d=round(forecast_1d * 100, 4),
            forecast_5d=round(forecast_5d * 100, 4),
            forecast_10d=round(forecast_10d * 100, 4),
            vol_regime=regime,
            vol_regime_color=self._regime_color(regime),
            vol_percentile=round(vol_pct, 1),
            omega=round(float(omega), 8),
            alpha=round(float(alpha), 4),
            beta=round(float(beta), 4),
            persistence=round(float(persistence), 4),
            expected_daily_move_pct=round(daily_move, 3),
            expected_weekly_move_pct=round(weekly_move, 3),
            atr_equivalent=round(atr_equiv, 4),
            implied_move_1w_pct=round(implied_1w, 2),
            implied_move_1m_pct=round(implied_1m, 2),
            signal=signal,
            trade_advice=advice,
            confluence_score=score,
        )

    def _fit_garch(self, returns: np.ndarray) -> Tuple[float, float, float]:
        """
        Fit GARCH(1,1) via simple method-of-moments / moment matching.
        For production, replace with MLE but this gives reasonable estimates.
        """
        r2 = returns ** 2
        var_total = float(np.var(returns))

        # Start with simple estimates
        # Unconditional variance = omega / (1 - alpha - beta)
        # Use autocorrelation of squared returns to estimate alpha + beta
        if len(r2) > 1:
            acf1 = float(np.corrcoef(r2[:-1], r2[1:])[0, 1])
            acf1 = max(0.01, min(0.97, acf1))  # Clamp
        else:
            acf1 = 0.8

        persistence = acf1
        alpha = max(0.05, min(0.3, persistence * 0.3))
        beta  = max(0.5,  min(0.94 - alpha, persistence - alpha))
        omega = var_total * (1 - alpha - beta)
        omega = max(1e-7, omega)

        return omega, alpha, beta

    def _garch_filter(self, returns: np.ndarray, omega: float, alpha: float, beta: float) -> np.ndarray:
        """Run GARCH filter to get conditional variance series."""
        n = len(returns)
        sigma2 = np.zeros(n)
        sigma2[0] = np.var(returns)

        for t in range(1, n):
            sigma2[t] = omega + alpha * returns[t-1]**2 + beta * sigma2[t-1]

        return sigma2

    def _forecast(self, current_var: float, omega: float, alpha: float, beta: float, h: int) -> float:
        """h-step ahead GARCH forecast (mean-reverting)."""
        persistence = alpha + beta
        if 1 - persistence <= 0:
            return float(np.sqrt(current_var))

        long_run = omega / (1 - persistence)
        forecast_var = long_run + (persistence ** h) * (current_var - long_run)
        return float(np.sqrt(max(0, forecast_var)))

    def _classify_regime(self, vol_percentile: float) -> str:
        if vol_percentile >= 75:
            return "EXTREME"
        elif vol_percentile >= 50:
            return "HIGH"
        elif vol_percentile >= 25:
            return "MEDIUM"
        return "LOW"

    def _regime_color(self, regime: str) -> str:
        return self.VOL_REGIMES.get(regime, {}).get("color", "#64748b")

    def _empty(self) -> GARCHForecast:
        return GARCHForecast(
            current_vol_daily=0, current_vol_annual=0, long_run_vol=0,
            forecast_1d=0, forecast_5d=0, forecast_10d=0,
            vol_regime="UNKNOWN", vol_regime_color="#64748b", vol_percentile=50,
            omega=0, alpha=0, beta=0, persistence=0,
            expected_daily_move_pct=0, expected_weekly_move_pct=0, atr_equivalent=0,
            implied_move_1w_pct=0, implied_move_1m_pct=0,
            signal="STABLE", trade_advice="Insufficient data",
            confluence_score=0,
        )

    def to_dict(self, r: GARCHForecast) -> dict:
        return {
            "current": {
                "daily_vol_pct":   r.current_vol_daily,
                "annual_vol_pct":  r.current_vol_annual,
                "long_run_vol_pct": r.long_run_vol,
            },
            "forecasts": {
                "1d_vol_pct":  r.forecast_1d,
                "5d_vol_pct":  r.forecast_5d,
                "10d_vol_pct": r.forecast_10d,
            },
            "regime": {
                "label":      r.vol_regime,
                "color":      r.vol_regime_color,
                "percentile": r.vol_percentile,
            },
            "model_params": {
                "omega":       r.omega,
                "alpha":       r.alpha,
                "beta":        r.beta,
                "persistence": r.persistence,
            },
            "trading": {
                "daily_move_pct":  r.expected_daily_move_pct,
                "weekly_move_pct": r.expected_weekly_move_pct,
                "atr_equivalent":  r.atr_equivalent,
            },
            "options_estimates": {
                "1w_move_pct": r.implied_move_1w_pct,
                "1m_move_pct": r.implied_move_1m_pct,
            },
            "signal":       r.signal,
            "trade_advice": r.trade_advice,
            "confluence_score": r.confluence_score,
        }
