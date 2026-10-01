"""
Smart Wallet Signal Detector
===============================
Tracks wallets with proven profitable track records.
These wallets are maintained in the `smart_wallets` DB table.

Score factors:
  - Number of smart wallets with open long positions
  - Number of smart wallets recently accumulating (last 48h)
  - Average win rate of active wallets
  - Aggregate position size vs historical average

Score mapping:
  - 0 smart wallets active         → 0
  - 1-2 wallets accumulating       → 30-45
  - 3-4 wallets accumulating       → 55-70
  - 5+ wallets accumulating        → 75-90
  - High win rate (>75%) bonus     → +10
  - Large position size bonus      → +5
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from ..providers.base import BaseWhaleProvider, WalletActivity, SmartWalletPosition

logger = logging.getLogger(__name__)


@dataclass
class SmartWalletResult:
    raw_score: float
    active_wallets: int          # wallets that took action in lookback window
    open_longs: int
    open_shorts: int
    avg_win_rate: float          # average win rate of active wallets
    total_position_usd: float    # total open position size in USD
    activities: list[dict] = field(default_factory=list)
    positions: list[dict] = field(default_factory=list)
    detail: str = ""


class SmartWalletSignal:
    """Computes smart wallet activity score."""

    def __init__(self, lookback_hours: int = 48):
        self.lookback_hours = lookback_hours

    def _get_smart_wallet_addresses(self, db: "Session") -> list[str]:
        """Load active smart wallet addresses from DB."""
        try:
            from app.models.whale import Wallet
            # Query wallets marked as smart_money with high win rates
            rows = (
                db.query(Wallet.address)
                .filter(
                    Wallet.entity_type == "smart_money",
                    Wallet.win_rate >= 60.0,
                )
                .limit(50)
                .all()
            )
            return [r.address for r in rows]
        except Exception as e:
            logger.warning(f"[SmartWalletSignal] DB query failed: {e}")
            return []

    async def compute(
        self,
        provider: BaseWhaleProvider,
        symbol: str,
        chain_id: str,
        db: "Session | None" = None,
        smart_wallet_addresses: list[str] | None = None,
    ) -> SmartWalletResult:
        # Get addresses from DB if not provided directly
        if smart_wallet_addresses is None:
            smart_wallet_addresses = self._get_smart_wallet_addresses(db) if db else []

        if not smart_wallet_addresses:
            return SmartWalletResult(
                raw_score=0.0,
                active_wallets=0,
                open_longs=0,
                open_shorts=0,
                avg_win_rate=0.0,
                total_position_usd=0.0,
                detail="Tidak ada smart wallet terdaftar untuk aset ini.",
            )

        # Fetch activity and positions from provider
        try:
            activities = await provider.get_smart_wallet_activity(
                wallet_addresses=smart_wallet_addresses,
                symbol=symbol,
                chain_id=chain_id,
                lookback_hours=self.lookback_hours,
            )
            positions = await provider.get_smart_wallet_positions(
                wallet_addresses=smart_wallet_addresses,
                symbol=symbol,
                chain_id=chain_id,
            )
        except Exception as e:
            logger.warning(f"[SmartWalletSignal] Provider error for {symbol}: {e}")
            activities, positions = [], []

        # Aggregate
        bullish_actions = {"accumulate", "open_long"}
        active_addresses = set()
        bull_count = 0
        win_rates = []

        for act in activities:
            active_addresses.add(act.wallet_address)
            if act.action in bullish_actions:
                bull_count += 1
            if act.win_rate is not None:
                win_rates.append(act.win_rate)

        open_longs = sum(1 for p in positions if p.side == "long")
        open_shorts = sum(1 for p in positions if p.side == "short")
        total_position_usd = sum(p.size_usd for p in positions)

        active_count = len(active_addresses)
        avg_win_rate = sum(win_rates) / len(win_rates) if win_rates else 0.0

        # Base score from active wallet count
        count_scores = {0: 0, 1: 30, 2: 42, 3: 55, 4: 67, 5: 75}
        raw = float(count_scores.get(min(active_count, 5), 80 if active_count > 5 else 0))

        # Win rate bonus
        if avg_win_rate >= 75:
            raw = min(100, raw + 10)
        elif avg_win_rate >= 65:
            raw = min(100, raw + 5)

        # Long dominance bonus
        if open_longs > open_shorts and open_longs > 0:
            raw = min(100, raw + 5)
        elif open_shorts > open_longs and open_shorts > 0:
            raw = max(0, raw - 10)

        parts = []
        if active_count > 0:
            parts.append(f"{active_count} smart wallet aktif dalam {self.lookback_hours}h")
        if open_longs:
            parts.append(f"{open_longs} posisi long terbuka")
        if open_shorts:
            parts.append(f"{open_shorts} posisi short terbuka")
        if avg_win_rate > 0:
            parts.append(f"Win rate rata-rata {avg_win_rate:.0f}%")

        return SmartWalletResult(
            raw_score=round(raw, 1),
            active_wallets=active_count,
            open_longs=open_longs,
            open_shorts=open_shorts,
            avg_win_rate=round(avg_win_rate, 1),
            total_position_usd=round(total_position_usd, 2),
            activities=[
                {
                    "address": a.wallet_address,
                    "action": a.action,
                    "amount_usd": a.amount_usd,
                    "timestamp": a.timestamp.isoformat(),
                    "label": a.label,
                }
                for a in activities
            ],
            positions=[
                {
                    "address": p.wallet_address,
                    "side": p.side,
                    "size_usd": p.size_usd,
                    "entry_price": p.entry_price,
                    "unrealised_pnl": p.unrealised_pnl,
                    "label": p.label,
                }
                for p in positions
            ],
            detail=" — ".join(parts) if parts else "Tidak ada aktivitas smart wallet.",
        )
