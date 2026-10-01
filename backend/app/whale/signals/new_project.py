"""
New Project Signal Detector
==============================
Assesses early-entry potential and risk for new/emerging projects.
Only applies to non-mature assets (not BTC, ETH, SOL, etc.).

Positive signals:
  - Smart wallets entered before hype (early_entry_wallets > 0)
  - Liquidity is locked
  - Vesting schedule exists
  - Token deployed > 14 days ago (less rug risk)

Risk flags (reduce or cap score):
  - Liquidity NOT locked → flag + deduction
  - Top holder wallets are new (< 7 days old) → suspicious
  - Very high concentration → flag
  - Token deployed < 3 days → very high risk

Score range: 0-100 (but capped at 50 if any critical risk flag is present)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..providers.base import BaseWhaleProvider, NewProjectInfo

logger = logging.getLogger(__name__)

# Mature assets skip new-project scoring entirely
MATURE_ASSETS = frozenset(["BTC", "ETH", "SOL", "BNB", "HYPE", "USDT", "USDC", "DAI"])


@dataclass
class NewProjectResult:
    raw_score: float            # 0-100
    applies: bool               # False for mature assets
    deploy_age_days: float | None
    liquidity_locked: bool | None
    risk_flags: list[str] = field(default_factory=list)
    early_entry_wallets: int = 0
    detail: str = ""


class NewProjectSignal:
    """Computes new project early-entry + risk score."""

    async def compute(
        self,
        provider: BaseWhaleProvider,
        symbol: str,
        chain_id: str,
        token_address: str = "",
    ) -> NewProjectResult:
        if symbol.upper() in MATURE_ASSETS:
            return NewProjectResult(
                raw_score=0.0,
                applies=False,
                deploy_age_days=None,
                liquidity_locked=None,
                detail="Aset matang — sinyal new project tidak berlaku.",
            )

        if not token_address:
            return NewProjectResult(
                raw_score=0.0,
                applies=True,
                deploy_age_days=None,
                liquidity_locked=None,
                risk_flags=[],
                detail="Token address tidak tersedia, tidak dapat menilai proyek baru.",
            )

        try:
            info: NewProjectInfo | None = await provider.get_new_project_info(
                symbol=symbol, chain_id=chain_id, token_address=token_address
            )
        except Exception as e:
            logger.warning(f"[NewProjectSignal] Provider error for {symbol}: {e}")
            info = None

        if info is None:
            return NewProjectResult(
                raw_score=0.0,
                applies=True,
                deploy_age_days=None,
                liquidity_locked=None,
                detail="Tidak ada data proyek baru dari provider.",
            )

        # Age calculation
        deploy_age = None
        if info.deploy_timestamp:
            deploy_age = (datetime.now(timezone.utc) - info.deploy_timestamp).days

        flags = list(info.risk_flags)
        raw = 50.0  # neutral start
        critical_risk = False

        # Deploy age assessment
        if deploy_age is not None:
            if deploy_age < 3:
                raw = 10.0
                flags.append("very_new_token_high_risk")
                critical_risk = True
            elif deploy_age < 14:
                raw = 30.0
                flags.append("new_token_moderate_risk")
            elif deploy_age < 90:
                raw = 50.0
            else:
                raw = 60.0

        # Liquidity lock bonus/penalty
        if info.liquidity_locked is True:
            raw = min(100, raw + 20)
        elif info.liquidity_locked is False:
            raw = max(0, raw - 20)
            flags.append("liquidity_not_locked")
            critical_risk = True

        # Vesting
        if info.vesting_exists is True:
            raw = min(100, raw + 10)

        # Early entry
        if info.early_entry_wallets > 0:
            bonus = min(15, info.early_entry_wallets * 3)
            raw = min(100, raw + bonus)

        # Suspicious new whale wallets
        if info.top_holder_wallet_age_days is not None and info.top_holder_wallet_age_days < 7:
            raw = max(0, raw - 20)
            flags.append("new_whale_wallets_suspicious")
            critical_risk = True

        # Cap score if critical risk flags
        if critical_risk:
            raw = min(raw, 45.0)

        detail_parts: list[str] = []
        if deploy_age is not None:
            detail_parts.append(f"Deploy {deploy_age} hari lalu")
        if info.liquidity_locked is not None:
            detail_parts.append("Liquidity terkunci ✓" if info.liquidity_locked else "Liquidity TIDAK terkunci ⚠️")
        if info.early_entry_wallets:
            detail_parts.append(f"{info.early_entry_wallets} smart wallet early entry")
        if flags:
            detail_parts.append(f"Flag risiko: {', '.join(flags)}")

        return NewProjectResult(
            raw_score=round(raw, 1),
            applies=True,
            deploy_age_days=float(deploy_age) if deploy_age is not None else None,
            liquidity_locked=info.liquidity_locked,
            risk_flags=flags,
            early_entry_wallets=info.early_entry_wallets,
            detail=" — ".join(detail_parts),
        )
