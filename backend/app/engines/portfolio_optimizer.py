"""
Portfolio Optimizer Engine
===========================
Professional-grade portfolio optimization using:

1. Mean-Variance Optimization (Markowitz)
2. Maximum Sharpe Ratio Portfolio
3. Minimum Volatility Portfolio
4. Equal Risk Contribution (Risk Parity)
5. Kelly-weighted multi-asset sizing
6. Correlation analysis + diversification score
7. Monte Carlo drawdown simulation
8. Rebalancing recommendations

Works with any list of symbols + expected returns.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


@dataclass
class AssetMetrics:
    symbol: str
    weight: float               # Optimal weight (0-1)
    weight_pct: float           # Weight as percentage
    expected_return: float      # Annualized expected return
    volatility: float           # Annualized volatility
    sharpe: float               # Individual Sharpe ratio
    kelly_fraction: float       # Kelly bet size
    risk_contribution: float    # % of total portfolio risk


@dataclass
class PortfolioMetrics:
    expected_return: float      # Annualized portfolio return
    volatility: float           # Annualized portfolio vol
    sharpe: float               # Portfolio Sharpe ratio
    max_drawdown_est: float     # Estimated max drawdown
    diversification_score: float  # 0-100 (100 = perfectly diversified)
    risk_parity_score: float    # How equal risk is distributed


@dataclass
class PortfolioOptResult:
    # Optimal allocation
    allocations: List[AssetMetrics]

    # Portfolio stats
    max_sharpe: PortfolioMetrics
    min_vol: PortfolioMetrics
    equal_weight: PortfolioMetrics
    risk_parity: PortfolioMetrics

    # Recommended portfolio
    recommended_type: str       # MAX_SHARPE | MIN_VOL | RISK_PARITY
    recommended: PortfolioMetrics

    # Correlation
    correlation_matrix: Dict    # {sym: {sym: corr}}
    avg_correlation: float

    # Monte Carlo
    monte_carlo_var_95: float   # 95% VaR (% loss)
    monte_carlo_cvar_95: float  # Conditional VaR

    # Rebalancing
    rebalancing_needed: bool
    rebalancing_threshold_pct: float

    signals: List[str] = field(default_factory=list)


class PortfolioOptimizerEngine:
    """
    Markowitz-based portfolio optimizer with risk parity and Monte Carlo.
    Requires at least 2 assets. Works purely from returns arrays.
    """

    def __init__(self, risk_free_rate: float = 0.05):
        self.rf = risk_free_rate
        self.n_mc_simulations = 2000

    def optimize(
        self,
        symbols: List[str],
        returns_matrix: np.ndarray,   # shape (n_days, n_assets)
        current_weights: Optional[List[float]] = None,
    ) -> PortfolioOptResult:
        """
        Optimize portfolio allocation.

        Args:
            symbols: List of asset names
            returns_matrix: Daily returns (n_days x n_assets)
            current_weights: Current holdings weights (optional)
        """
        n_assets = len(symbols)
        if returns_matrix.shape[1] != n_assets:
            raise ValueError("returns_matrix columns must match symbols count")

        # Annualize
        mean_returns = np.mean(returns_matrix, axis=0) * 252
        cov_matrix   = np.cov(returns_matrix.T) * 252

        # ── Portfolios ─────────────────────────────────────────────────────
        max_sharpe_w  = self._max_sharpe(mean_returns, cov_matrix)
        min_vol_w     = self._min_volatility(mean_returns, cov_matrix)
        equal_w       = np.ones(n_assets) / n_assets
        risk_parity_w = self._risk_parity(cov_matrix)

        # ── Metrics ────────────────────────────────────────────────────────
        ms_metrics  = self._portfolio_metrics(max_sharpe_w,  mean_returns, cov_matrix)
        mv_metrics  = self._portfolio_metrics(min_vol_w,     mean_returns, cov_matrix)
        ew_metrics  = self._portfolio_metrics(equal_w,       mean_returns, cov_matrix)
        rp_metrics  = self._portfolio_metrics(risk_parity_w, mean_returns, cov_matrix)

        # ── Recommended ────────────────────────────────────────────────────
        # Risk-based recommendation
        if ms_metrics.sharpe > 1.5 and ms_metrics.volatility < 0.4:
            rec_type = "MAX_SHARPE"
            rec = ms_metrics
        elif mv_metrics.volatility < ms_metrics.volatility * 0.7:
            rec_type = "MIN_VOL"
            rec = mv_metrics
        else:
            rec_type = "RISK_PARITY"
            rec = rp_metrics

        # ── Per-asset metrics ──────────────────────────────────────────────
        # Use recommended weights for allocation display
        w_rec = max_sharpe_w if rec_type == "MAX_SHARPE" else (
                min_vol_w if rec_type == "MIN_VOL" else risk_parity_w)

        asset_vols   = np.sqrt(np.diag(cov_matrix))
        risk_contrib = self._risk_contributions(w_rec, cov_matrix)

        allocations = []
        for i, sym in enumerate(symbols):
            individual_sharpe = (mean_returns[i] - self.rf) / asset_vols[i] if asset_vols[i] > 0 else 0
            kelly = max(0, (individual_sharpe / asset_vols[i]) * 0.25)  # Quarter Kelly

            allocations.append(AssetMetrics(
                symbol=sym,
                weight=round(float(w_rec[i]), 4),
                weight_pct=round(float(w_rec[i]) * 100, 2),
                expected_return=round(float(mean_returns[i]) * 100, 2),
                volatility=round(float(asset_vols[i]) * 100, 2),
                sharpe=round(individual_sharpe, 3),
                kelly_fraction=round(float(kelly) * 100, 2),
                risk_contribution=round(float(risk_contrib[i]) * 100, 2),
            ))

        # ── Correlation ────────────────────────────────────────────────────
        corr_matrix = np.corrcoef(returns_matrix.T)
        corr_dict   = {}
        for i, s1 in enumerate(symbols):
            corr_dict[s1] = {}
            for j, s2 in enumerate(symbols):
                corr_dict[s1][s2] = round(float(corr_matrix[i, j]), 3)

        # Avg off-diagonal correlation
        mask = ~np.eye(n_assets, dtype=bool)
        avg_corr = float(np.mean(np.abs(corr_matrix[mask]))) if mask.sum() > 0 else 0

        # ── Monte Carlo ────────────────────────────────────────────────────
        var95, cvar95 = self._monte_carlo_risk(w_rec, mean_returns, cov_matrix)

        # ── Rebalancing ────────────────────────────────────────────────────
        rebal_needed = False
        if current_weights and len(current_weights) == n_assets:
            drift = float(np.max(np.abs(np.array(current_weights) - w_rec)))
            rebal_needed = drift > 0.05  # 5% drift threshold

        # ── Signals ────────────────────────────────────────────────────────
        signals = []
        if avg_corr > 0.7:
            signals.append("⚠️ High average correlation — portfolio not well diversified")
        if rec.sharpe < 1.0:
            signals.append("⚠️ Sharpe ratio < 1.0 — consider reducing position sizes")
        if rec.volatility > 0.5:
            signals.append("🚨 Portfolio volatility > 50% — very high risk")
        if rebal_needed:
            signals.append("🔄 Portfolio drift detected — rebalancing recommended")
        if ms_metrics.sharpe > 2.0:
            signals.append("✅ Excellent Sharpe > 2.0 on max-Sharpe portfolio")

        return PortfolioOptResult(
            allocations=sorted(allocations, key=lambda x: x.weight, reverse=True),
            max_sharpe=ms_metrics,
            min_vol=mv_metrics,
            equal_weight=ew_metrics,
            risk_parity=rp_metrics,
            recommended_type=rec_type,
            recommended=rec,
            correlation_matrix=corr_dict,
            avg_correlation=round(avg_corr, 3),
            monte_carlo_var_95=round(var95 * 100, 2),
            monte_carlo_cvar_95=round(cvar95 * 100, 2),
            rebalancing_needed=rebal_needed,
            rebalancing_threshold_pct=5.0,
            signals=signals,
        )

    # ─────────────────── optimizers ────────────────────────────

    def _max_sharpe(self, returns, cov) -> np.ndarray:
        """Maximize Sharpe ratio using gradient descent."""
        n = len(returns)
        w = np.ones(n) / n
        lr = 0.01
        for _ in range(500):
            sr, grad = self._sharpe_grad(w, returns, cov)
            w = w + lr * grad
            w = np.clip(w, 0.01, 1.0)
            w = w / w.sum()
        return w

    def _min_volatility(self, returns, cov) -> np.ndarray:
        """Minimize portfolio volatility."""
        n = len(returns)
        w = np.ones(n) / n
        lr = 0.01
        for _ in range(500):
            port_vol = float(np.sqrt(w @ cov @ w))
            if port_vol == 0:
                break
            grad = (cov @ w) / port_vol
            w = w - lr * grad
            w = np.clip(w, 0.01, 1.0)
            w = w / w.sum()
        return w

    def _risk_parity(self, cov) -> np.ndarray:
        """Equal risk contribution (risk parity)."""
        n = cov.shape[0]
        w = np.ones(n) / n
        for _ in range(1000):
            rc = self._risk_contributions(w, cov)
            target = 1.0 / n
            w = w * (target / (rc + 1e-8))
            w = np.clip(w, 0.001, 1.0)
            w = w / w.sum()
        return w

    def _sharpe_grad(self, w, returns, cov) -> Tuple[float, np.ndarray]:
        """Compute Sharpe and its gradient."""
        port_ret = float(w @ returns) - self.rf
        port_vol = float(np.sqrt(w @ cov @ w))
        if port_vol == 0:
            return 0.0, np.zeros_like(w)
        sr = port_ret / port_vol
        grad_ret = returns
        grad_vol = (cov @ w) / port_vol
        grad = (grad_ret * port_vol - port_ret * grad_vol) / (port_vol ** 2)
        return sr, grad

    def _risk_contributions(self, w, cov) -> np.ndarray:
        """Calculate each asset's risk contribution as fraction of total risk."""
        port_vol = float(np.sqrt(w @ cov @ w))
        if port_vol == 0:
            return np.ones_like(w) / len(w)
        marginal = cov @ w
        rc = w * marginal / port_vol
        return rc / rc.sum()

    def _portfolio_metrics(self, w, returns, cov) -> PortfolioMetrics:
        port_ret = float(w @ returns)
        port_vol = float(np.sqrt(w @ cov @ w))
        sharpe   = (port_ret - self.rf) / port_vol if port_vol > 0 else 0

        # Simplified max drawdown estimate from volatility
        max_dd = port_vol * np.sqrt(1) * 2.0  # ~2 sigma annual move

        # Diversification score (low avg corr = high score)
        rc = self._risk_contributions(w, cov)
        # Even risk = good diversification
        ideal_rc = 1.0 / len(w)
        div_score = 100 * (1 - float(np.mean(np.abs(rc - ideal_rc))) * len(w))
        div_score = max(0, min(100, div_score))

        # Risk parity score = how even are risk contributions
        rp_score = 100 * (1 - float(np.std(rc)) * 10)
        rp_score = max(0, min(100, rp_score))

        return PortfolioMetrics(
            expected_return=round(port_ret * 100, 2),
            volatility=round(port_vol * 100, 2),
            sharpe=round(sharpe, 3),
            max_drawdown_est=round(max_dd * 100, 2),
            diversification_score=round(div_score, 1),
            risk_parity_score=round(rp_score, 1),
        )

    def _monte_carlo_risk(self, w, returns, cov) -> Tuple[float, float]:
        """Simulate 1-year portfolio returns using Monte Carlo."""
        port_ret = float(w @ returns) / 252
        port_vol = float(np.sqrt(w @ cov @ w)) / np.sqrt(252)

        sim_returns = np.random.normal(port_ret, port_vol, self.n_mc_simulations)
        sorted_r = np.sort(sim_returns)

        var95  = -np.percentile(sorted_r, 5)
        cvar95 = -np.mean(sorted_r[sorted_r <= np.percentile(sorted_r, 5)])

        return max(0, var95), max(0, cvar95)

    def to_dict(self, r: PortfolioOptResult) -> dict:
        def pm(m: PortfolioMetrics): return {
            "expected_return_pct": m.expected_return,
            "volatility_pct":      m.volatility,
            "sharpe":              m.sharpe,
            "max_drawdown_est_pct":m.max_drawdown_est,
            "diversification_score": m.diversification_score,
        }
        return {
            "recommended_type":    r.recommended_type,
            "recommended":         pm(r.recommended),
            "portfolios": {
                "max_sharpe":   pm(r.max_sharpe),
                "min_vol":      pm(r.min_vol),
                "equal_weight": pm(r.equal_weight),
                "risk_parity":  pm(r.risk_parity),
            },
            "allocations": [
                {
                    "symbol":            a.symbol,
                    "weight_pct":        a.weight_pct,
                    "expected_return_pct": a.expected_return,
                    "volatility_pct":    a.volatility,
                    "sharpe":            a.sharpe,
                    "kelly_pct":         a.kelly_fraction,
                    "risk_contribution_pct": a.risk_contribution,
                }
                for a in r.allocations
            ],
            "correlation": {
                "matrix":          r.correlation_matrix,
                "avg_correlation": r.avg_correlation,
            },
            "risk": {
                "var_95_pct":      r.monte_carlo_var_95,
                "cvar_95_pct":     r.monte_carlo_cvar_95,
            },
            "rebalancing_needed": r.rebalancing_needed,
            "signals":            r.signals,
        }
