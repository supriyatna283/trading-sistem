"""
Scoring Engine
===============
Orchestrates all signal detectors and computes a final 0-100 score
with full explainability for each signal contribution.

Architecture:
  - Each signal is computed independently and asynchronously.
  - The engine aggregates them using configurable weights.
  - The result includes per-signal breakdown for UI display.
  - All flag detection (stale signal, concentration risk, scam warning) is done here.

Usage:
    engine = ScoringEngine(provider=MockWhaleProvider(), config=load_scoring_config())
    result = await engine.score(symbol="HYPE", chain_id="hyperliquid", db=db)
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from ..providers.base import BaseWhaleProvider
from ..signals.accumulation import AccumulationSignal, AccumulationResult
from ..signals.exchange_netflow import ExchangeNetflowSignal, NetflowResult
from ..signals.smart_wallet import SmartWalletSignal, SmartWalletResult
from ..signals.holder_concentration import HolderConcentrationSignal, ConcentrationResult
from ..signals.new_project import NewProjectSignal, NewProjectResult
from .config import ScoringConfig, load_scoring_config

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "⚠️ Skor bersifat probabilistik berdasarkan data on-chain. "
    "Bukan jaminan pergerakan harga. Selalu kombinasikan dengan analisis "
    "struktur harga (SMC/ICT) dan manajemen risiko."
)


@dataclass
class SignalBreakdown:
    """Contribution of a single signal to the final score."""
    signal_name: str
    raw_score: float         # 0-100 (or negative for risk signals)
    weight: float            # configured weight
    contribution: float      # raw_score * weight (actual points added/removed)
    detail: str
    flags: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)  # signal-specific data for UI


@dataclass
class ScoreResult:
    """Full scoring result for a single (symbol, chain_id) pair."""
    symbol: str
    chain_id: str
    token_address: str

    # Final score
    score: float             # 0-100
    grade: str               # A/B/C/D/F
    grade_label: str         # human-readable label

    # Breakdown
    breakdown: list[SignalBreakdown]

    # Flags
    flags: list[str] = field(default_factory=list)  # aggregated across all signals
    is_stale: bool = False    # True if price already moved significantly

    # Metadata
    provider: str = "unknown"
    scored_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    disclaimer: str = DISCLAIMER

    # Raw signal results (for deep inspection)
    accumulation: Optional[AccumulationResult] = None
    netflow: Optional[NetflowResult] = None
    smart_wallet: Optional[SmartWalletResult] = None
    concentration: Optional[ConcentrationResult] = None
    new_project: Optional[NewProjectResult] = None

    def to_dict(self) -> dict:
        """Serialise to JSON-friendly dict for API response."""
        return {
            "symbol": self.symbol,
            "chain_id": self.chain_id,
            "token_address": self.token_address,
            "score": round(self.score, 1),
            "grade": self.grade,
            "grade_label": self.grade_label,
            "is_stale": self.is_stale,
            "flags": self.flags,
            "disclaimer": self.disclaimer,
            "provider": self.provider,
            "scored_at": self.scored_at.isoformat(),
            "breakdown": [
                {
                    "signal": b.signal_name,
                    "raw_score": round(b.raw_score, 1),
                    "weight": b.weight,
                    "contribution": round(b.contribution, 1),
                    "detail": b.detail,
                    "flags": b.flags,
                    **b.extra,
                }
                for b in self.breakdown
            ],
        }


class ScoringEngine:
    """
    Orchestrates signal computation and aggregation.
    Thread-safe (stateless, uses async).
    """

    def __init__(
        self,
        provider: BaseWhaleProvider,
        config: ScoringConfig | None = None,
    ):
        self.provider = provider
        self.config = config or load_scoring_config()

        # Instantiate signal detectors (stateless, can be reused)
        self._accumulation = AccumulationSignal(lookback_days=self.config.accumulation_days)
        self._netflow = ExchangeNetflowSignal(lookback_days=self.config.netflow_days)
        self._smart_wallet = SmartWalletSignal(lookback_hours=self.config.smart_wallet_lookback_hours)
        self._concentration = HolderConcentrationSignal()
        self._new_project = NewProjectSignal()

    async def score(
        self,
        symbol: str,
        chain_id: str,
        token_address: str = "",
        db: "Session | None" = None,
        price_change_7d_pct: float | None = None,
        current_price: float | None = None,
    ) -> ScoreResult:
        """
        Compute full score for a (symbol, chain_id) pair.
        All signals are fetched concurrently for speed.

        Args:
            symbol: Token symbol (e.g., "BTC", "HYPE")
            chain_id: Chain identifier (e.g., "bitcoin", "hyperliquid")
            token_address: Contract address (empty for native assets)
            db: SQLAlchemy session (used for DB-fallback in some signals)
            price_change_7d_pct: 7-day price change % (for sideways detection)
            current_price: Current price in USD (for stale detection)
        """
        cfg = self.config  # reload each time for hot-reload support
        try:
            cfg = load_scoring_config()  # always fresh weights
        except Exception:
            pass

        # Run all signals concurrently
        accum_task = self._accumulation.compute(
            self.provider, symbol, chain_id, db, price_change_7d_pct
        )
        netflow_task = self._netflow.compute(self.provider, symbol, chain_id, db)
        smart_task = self._smart_wallet.compute(self.provider, symbol, chain_id, db)
        conc_task = self._concentration.compute(self.provider, symbol, chain_id, db)
        new_proj_task = self._new_project.compute(
            self.provider, symbol, chain_id, token_address
        )

        accum_res, netflow_res, smart_res, conc_res, new_proj_res = await asyncio.gather(
            accum_task, netflow_task, smart_task, conc_task, new_proj_task,
            return_exceptions=True,
        )

        # Handle exceptions gracefully
        def safe(res, fallback_cls):
            if isinstance(res, Exception):
                logger.error(f"Signal error: {res}")
                return None
            return res

        accum_res = safe(accum_res, AccumulationResult)
        netflow_res = safe(netflow_res, NetflowResult)
        smart_res = safe(smart_res, SmartWalletResult)
        conc_res = safe(conc_res, ConcentrationResult)
        new_proj_res = safe(new_proj_res, NewProjectResult)

        # Build breakdown
        breakdown: list[SignalBreakdown] = []
        total_score = 0.0
        all_flags: list[str] = []

        # 1. Accumulation
        if accum_res:
            contrib = accum_res.raw_score * cfg.weight_accumulation
            total_score += contrib
            all_flags.extend([])  # accumulation doesn't flag warnings
            breakdown.append(SignalBreakdown(
                signal_name="accumulation",
                raw_score=accum_res.raw_score,
                weight=cfg.weight_accumulation,
                contribution=round(contrib, 2),
                detail=accum_res.detail,
                extra={
                    "consecutive_days": accum_res.consecutive_days,
                    "total_net_change_usd": accum_res.total_net_change_usd,
                    "sideways_bonus": accum_res.sideways_bonus,
                    "series": accum_res.series[-7:],  # last 7 days for chart
                },
            ))

        # 2. Exchange Netflow
        if netflow_res:
            contrib = netflow_res.raw_score * cfg.weight_netflow
            total_score += contrib
            breakdown.append(SignalBreakdown(
                signal_name="exchange_netflow",
                raw_score=netflow_res.raw_score,
                weight=cfg.weight_netflow,
                contribution=round(contrib, 2),
                detail=netflow_res.detail,
                extra={
                    "bias": netflow_res.bias,
                    "net_flow_usd": netflow_res.net_flow_usd,
                    "inflow_usd": netflow_res.inflow_usd,
                    "outflow_usd": netflow_res.outflow_usd,
                    "daily_snapshots": netflow_res.daily_snapshots[-7:],
                },
            ))

        # 3. Smart Wallet
        if smart_res:
            contrib = smart_res.raw_score * cfg.weight_smart_wallet
            total_score += contrib
            breakdown.append(SignalBreakdown(
                signal_name="smart_wallet",
                raw_score=smart_res.raw_score,
                weight=cfg.weight_smart_wallet,
                contribution=round(contrib, 2),
                detail=smart_res.detail,
                extra={
                    "active_wallets": smart_res.active_wallets,
                    "open_longs": smart_res.open_longs,
                    "open_shorts": smart_res.open_shorts,
                    "avg_win_rate": smart_res.avg_win_rate,
                    "positions": smart_res.positions[:5],
                },
            ))

        # 4. Holder Concentration (RISK — uses abs weight as deduction)
        if conc_res:
            # concentration raw_score is already negative; weight is negative in config
            # contribution = raw_score * abs(weight) — result is a deduction
            contrib = conc_res.raw_score * abs(cfg.weight_concentration)
            total_score += contrib  # negative
            all_flags.extend(conc_res.flags)
            breakdown.append(SignalBreakdown(
                signal_name="holder_concentration",
                raw_score=conc_res.raw_score,
                weight=cfg.weight_concentration,
                contribution=round(contrib, 2),
                detail=conc_res.detail,
                flags=conc_res.flags,
                extra={
                    "top10_pct": conc_res.top10_pct,
                    "top20_pct": conc_res.top20_pct,
                    "top50_pct": conc_res.top50_pct,
                    "risk_level": conc_res.risk_level,
                    "excluded_count": conc_res.excluded_count,
                },
            ))

        # 5. New Project (only applies to non-mature assets)
        if new_proj_res and new_proj_res.applies:
            contrib = new_proj_res.raw_score * cfg.weight_new_project
            total_score += contrib
            all_flags.extend(new_proj_res.risk_flags)
            breakdown.append(SignalBreakdown(
                signal_name="new_project",
                raw_score=new_proj_res.raw_score,
                weight=cfg.weight_new_project,
                contribution=round(contrib, 2),
                detail=new_proj_res.detail,
                flags=new_proj_res.risk_flags,
                extra={
                    "deploy_age_days": new_proj_res.deploy_age_days,
                    "liquidity_locked": new_proj_res.liquidity_locked,
                    "early_entry_wallets": new_proj_res.early_entry_wallets,
                },
            ))
        elif new_proj_res and not new_proj_res.applies:
            breakdown.append(SignalBreakdown(
                signal_name="new_project",
                raw_score=0.0,
                weight=cfg.weight_new_project,
                contribution=0.0,
                detail=new_proj_res.detail,
            ))

        # Normalise final score to 0-100
        final_score = max(0.0, min(100.0, total_score))

        # Grade assignment
        grade, grade_label = self._assign_grade(final_score, cfg)

        # Stale signal detection
        is_stale = False
        if price_change_7d_pct is not None and abs(price_change_7d_pct) > cfg.stale_price_move_pct:
            is_stale = True
            all_flags.append("signal_may_be_stale")

        # Deduplicate flags
        all_flags = list(dict.fromkeys(all_flags))

        return ScoreResult(
            symbol=symbol,
            chain_id=chain_id,
            token_address=token_address,
            score=round(final_score, 1),
            grade=grade,
            grade_label=grade_label,
            breakdown=breakdown,
            flags=all_flags,
            is_stale=is_stale,
            provider=self.provider.name,
            accumulation=accum_res,
            netflow=netflow_res,
            smart_wallet=smart_res,
            concentration=conc_res,
            new_project=new_proj_res if (new_proj_res and new_proj_res.applies) else None,
        )

    def _assign_grade(self, score: float, cfg: ScoringConfig) -> tuple[str, str]:
        grade_labels = cfg.grade_labels or {}
        if score >= cfg.grade_a_min:
            return "A", grade_labels.get("A", "Sangat Bullish")
        elif score >= cfg.grade_b_min:
            return "B", grade_labels.get("B", "Bullish")
        elif score >= cfg.grade_c_min:
            return "C", grade_labels.get("C", "Netral")
        elif score >= cfg.grade_d_min:
            return "D", grade_labels.get("D", "Waspada")
        else:
            return "F", grade_labels.get("F", "Bearish / Risiko Tinggi")
