"""
Wallet Cluster Detector
========================
Detects wallets that likely belong to the same entity
(splitting positions across multiple addresses).

Heuristic methods (no ML needed):
  1. Funding pattern: Wallet A funds wallets B, C, D in near-identical amounts
     within a short time window → likely same entity
  2. Transaction timing: Multiple wallets transact the same token within seconds
     of each other → coordinated behaviour
  3. Address proximity: Common funder/creator address

This is a best-effort filter; false positives are possible.
Results should be flagged as "probable cluster", not certainty.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class WalletCluster:
    """A group of wallets suspected to be controlled by the same entity."""
    cluster_id: str
    member_addresses: list[str]
    confidence: float          # 0-1 (higher = more likely same entity)
    evidence: list[str]        # human-readable evidence descriptions
    total_volume_usd: float
    detected_at: datetime = field(default_factory=datetime.utcnow)


class WalletClusterDetector:
    """
    Identifies wallets that are likely controlled by the same entity.
    Uses transaction patterns from the whale_transactions table.
    """

    def __init__(
        self,
        time_window_seconds: int = 300,   # 5 minutes — same-entity coordination window
        amount_similarity_pct: float = 5.0,  # amounts within 5% = suspicious
        min_cluster_size: int = 2,
    ):
        self.time_window_seconds = time_window_seconds
        self.amount_similarity_pct = amount_similarity_pct
        self.min_cluster_size = min_cluster_size

    def detect_clusters(
        self,
        db: "Session",
        chain_id: str,
        symbol: str,
        lookback_hours: int = 24,
    ) -> list[WalletCluster]:
        """
        Query whale_transactions and find wallets with suspicious coordination.
        Returns a list of detected clusters.
        """
        try:
            from app.models.whale import WhaleTransaction, Wallet
            since = datetime.utcnow() - timedelta(hours=lookback_hours)

            txs = (
                db.query(WhaleTransaction)
                .filter(
                    WhaleTransaction.chain_id == chain_id,
                    WhaleTransaction.token_symbol == symbol,
                    WhaleTransaction.block_time >= since,
                )
                .order_by(WhaleTransaction.block_time)
                .all()
            )
        except Exception as e:
            logger.warning(f"[ClusterDetector] DB query failed: {e}")
            return []

        if len(txs) < 2:
            return []

        clusters: list[WalletCluster] = []
        used_ids: set[int] = set()

        for i, tx_a in enumerate(txs):
            if tx_a.id in used_ids:
                continue

            cluster_members = [tx_a]
            evidence = []

            for j, tx_b in enumerate(txs[i + 1:], start=i + 1):
                if tx_b.id in used_ids:
                    continue

                # Timing check
                time_diff = abs(
                    (tx_b.block_time - tx_a.block_time).total_seconds()
                )
                if time_diff > self.time_window_seconds:
                    continue  # too far apart in time

                # Amount similarity check
                if tx_a.usd_value > 0:
                    amount_diff_pct = abs(tx_b.usd_value - tx_a.usd_value) / tx_a.usd_value * 100
                    if amount_diff_pct <= self.amount_similarity_pct:
                        cluster_members.append(tx_b)
                        evidence.append(
                            f"Jumlah serupa: ${tx_a.usd_value:,.0f} vs ${tx_b.usd_value:,.0f} "
                            f"({amount_diff_pct:.1f}% selisih, {time_diff:.0f}s selang waktu)"
                        )

            if len(cluster_members) >= self.min_cluster_size:
                member_addresses = list({
                    tx.from_wallet.address if tx.from_wallet else "Unknown"
                    for tx in cluster_members
                    if tx.from_wallet
                })
                if len(member_addresses) >= self.min_cluster_size:
                    confidence = min(0.95, 0.5 + len(cluster_members) * 0.1)
                    total_vol = sum(tx.usd_value for tx in cluster_members)
                    cluster_id = f"cluster_{chain_id}_{symbol}_{i}"

                    clusters.append(WalletCluster(
                        cluster_id=cluster_id,
                        member_addresses=member_addresses,
                        confidence=round(confidence, 2),
                        evidence=evidence[:5],  # limit evidence display
                        total_volume_usd=round(total_vol, 0),
                    ))
                    for tx in cluster_members:
                        used_ids.add(tx.id)

        return clusters

    def is_wash_transfer(
        self,
        from_address: str,
        to_address: str,
        from_label: str | None,
        to_label: str | None,
    ) -> bool:
        """
        Simple heuristic: if both wallets have the same label (entity),
        it's likely an internal transfer (wash trade / position move).
        """
        if from_label and to_label and from_label == to_label:
            return True
        # Self-transfer
        if from_address.lower() == to_address.lower():
            return True
        return False
