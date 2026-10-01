"""
Holder Concentration Signal Detector
=======================================
Measures supply concentration among top holders (RISK signal — reduces score).

Key rules:
  - Exchange addresses, burn addresses, and contracts are EXCLUDED from calculation.
  - High concentration = fewer wallets control more supply = higher manipulation risk.
  - This signal always contributes NEGATIVELY to the final score.

Risk thresholds (top 10 % of circulating supply, excl. exchanges):
  - top10 <= 25%  → low risk, small reduction  (-5 to -10)
  - top10 25-50%  → moderate risk              (-10 to -25)
  - top10 50-70%  → high risk                  (-25 to -45)
  - top10 > 70%   → very high risk             (-45 to -60)

The return value is a NEGATIVE raw_score: the scoring engine applies this
as a deduction. Max deduction is capped at the configured weight.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from ..providers.base import BaseWhaleProvider, HolderDistribution

logger = logging.getLogger(__name__)


@dataclass
class ConcentrationResult:
    raw_score: float           # NEGATIVE: 0 to -100 (used as risk deduction)
    top10_pct: float           # % held by top 10 non-exchange wallets
    top20_pct: float
    top50_pct: float
    risk_level: str            # "LOW" | "MODERATE" | "HIGH" | "VERY_HIGH"
    excluded_count: int        # exchange/burn/contract addresses excluded
    holder_count: int          # total top-N holders analysed
    flags: list[str] = field(default_factory=list)
    detail: str = ""


class HolderConcentrationSignal:
    """
    Computes concentration risk (negative contribution to score).
    The final score contribution = raw_score * |weight| (weight is negative in config).
    """

    async def compute(
        self,
        provider: BaseWhaleProvider,
        symbol: str,
        chain_id: str,
        db: "Session | None" = None,
    ) -> ConcentrationResult:
        try:
            dist: HolderDistribution | None = await provider.get_holder_distribution(
                symbol=symbol, chain_id=chain_id
            )
        except Exception as e:
            logger.warning(f"[ConcentrationSignal] Provider error for {symbol}: {e}")
            dist = None

        if dist is None or dist.top10_pct == 0.0:
            # No data → assume moderate risk, small deduction
            return ConcentrationResult(
                raw_score=-15.0,
                top10_pct=0.0,
                top20_pct=0.0,
                top50_pct=0.0,
                risk_level="UNKNOWN",
                excluded_count=0,
                holder_count=0,
                flags=["concentration_data_unavailable"],
                detail="Data konsentrasi holder tidak tersedia (asumsi risiko moderat).",
            )

        # Count excluded addresses
        excluded = [h for h in dist.holders if h.is_excluded]
        non_exchange = [h for h in dist.holders if not h.is_excluded]

        top10 = dist.top10_pct
        top20 = dist.top20_pct
        top50 = dist.top50_pct
        flags: list[str] = []

        # Risk level and raw deduction
        if top10 <= 25:
            risk_level = "LOW"
            deduction = 5 + top10 * 0.2
        elif top10 <= 50:
            risk_level = "MODERATE"
            deduction = 10 + (top10 - 25) * 0.6
            if top10 > 40:
                flags.append("moderate_concentration")
        elif top10 <= 70:
            risk_level = "HIGH"
            deduction = 25 + (top10 - 50) * 1.0
            flags.append("high_concentration")
        else:
            risk_level = "VERY_HIGH"
            deduction = 45 + min(15, (top10 - 70) * 0.75)
            flags.append("extreme_concentration")

        if dist.is_high_concentration:
            flags.append("provider_flagged_high_concentration")

        detail_parts = [f"Top 10 pegang {top10:.1f}% supply (excl. exchange/burn)"]
        if risk_level in ("HIGH", "VERY_HIGH"):
            detail_parts.append("RISIKO MANIPULASI TINGGI")
        if top50:
            detail_parts.append(f"Top 50: {top50:.1f}%")

        return ConcentrationResult(
            raw_score=round(-deduction, 1),
            top10_pct=top10,
            top20_pct=top20,
            top50_pct=top50,
            risk_level=risk_level,
            excluded_count=len(excluded),
            holder_count=len(dist.holders),
            flags=flags,
            detail=" — ".join(detail_parts),
        )
