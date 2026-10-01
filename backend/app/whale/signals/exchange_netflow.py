"""
Exchange Netflow Signal Detector
===================================
Detects net flow of assets to/from centralised exchanges.

Interpretation:
  - Positive net_flow (more outflow from CEX): whale withdrawal = accumulation signal (bullish)
  - Negative net_flow (more inflow to CEX): deposit for selling = distribution signal (bearish)

Score mapping (0-100):
  - net_flow > +30% of volume → 90-100 (strong bullish)
  - net_flow +10% to +30%    → 65-89
  - net_flow ±10%            → 40-64  (neutral)
  - net_flow -10% to -30%    → 15-39  (bearish)
  - net_flow < -30%          → 0-14   (strong bearish, reduces score significantly)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from ..providers.base import BaseWhaleProvider, NetflowData

logger = logging.getLogger(__name__)


@dataclass
class NetflowResult:
    raw_score: float           # 0-100
    net_flow_usd: float        # positive = bullish
    inflow_usd: float
    outflow_usd: float
    bias: str                  # "STRONGLY_BULLISH" | "BULLISH" | "NEUTRAL" | "BEARISH" | "STRONGLY_BEARISH"
    detail: str
    daily_snapshots: list[dict] = field(default_factory=list)
    source: str = "unknown"


class ExchangeNetflowSignal:
    """Computes exchange netflow score for a (symbol, chain_id) pair."""

    def __init__(self, lookback_days: int = 7):
        self.lookback_days = lookback_days

    async def compute(
        self,
        provider: BaseWhaleProvider,
        symbol: str,
        chain_id: str,
        db: "Session | None" = None,
    ) -> NetflowResult:
        try:
            data: NetflowData | None = await provider.get_exchange_netflow(
                symbol=symbol,
                chain_id=chain_id,
                days=self.lookback_days,
            )
        except Exception as e:
            logger.warning(f"[NetflowSignal] Provider error for {symbol}: {e}")
            data = None

        if data is None and db is not None:
            data = self._query_db_netflow(db, symbol, chain_id, self.lookback_days)

        if data is None:
            return NetflowResult(
                raw_score=50.0,  # neutral when no data
                net_flow_usd=0.0,
                inflow_usd=0.0,
                outflow_usd=0.0,
                bias="NEUTRAL",
                detail="Data netflow tidak tersedia (skor netral).",
            )

        total = data.inflow_usd + data.outflow_usd
        if total == 0:
            ratio = 0.0
        else:
            # ratio = net / total  (-1 to +1)
            ratio = data.net_flow_usd / total

        # Map ratio to 0-100 score
        if ratio >= 0.30:
            raw_score = 90 + min(10, (ratio - 0.30) * 100)
            bias = "STRONGLY_BULLISH"
        elif ratio >= 0.10:
            raw_score = 65 + (ratio - 0.10) * 125  # 65 to 90
            bias = "BULLISH"
        elif ratio >= -0.10:
            raw_score = 40 + (ratio + 0.10) * 125  # 40 to 65
            bias = "NEUTRAL"
        elif ratio >= -0.30:
            raw_score = 15 + (ratio + 0.30) * 125  # 15 to 40
            bias = "BEARISH"
        else:
            raw_score = max(0, 15 + (ratio + 0.30) * 50)
            bias = "STRONGLY_BEARISH"

        raw_score = round(min(100, max(0, raw_score)), 1)

        sign = "+" if data.net_flow_usd >= 0 else ""
        detail = (
            f"Net CEX flow: {sign}${data.net_flow_usd / 1_000_000:.1f}M "
            f"(Outflow ${data.outflow_usd / 1_000_000:.1f}M vs "
            f"Inflow ${data.inflow_usd / 1_000_000:.1f}M, {self.lookback_days}d)"
        )

        return NetflowResult(
            raw_score=raw_score,
            net_flow_usd=data.net_flow_usd,
            inflow_usd=data.inflow_usd,
            outflow_usd=data.outflow_usd,
            bias=bias,
            detail=detail,
            daily_snapshots=data.daily_snapshots,
            source=data.source,
        )

    def _query_db_netflow(self, db: "Session", symbol: str, chain_id: str, days: int) -> NetflowData | None:
        """
        Fallback: Calculate netflow from local DB transactions.
        INFLOW: from non-exchange to exchange
        OUTFLOW: from exchange to non-exchange
        """
        try:
            from datetime import datetime, timedelta
            from sqlalchemy import func
            from app.models.whale import WhaleTransaction, WhaleDirection

            since = datetime.utcnow() - timedelta(days=days)
            
            inflow_sum = db.query(func.sum(WhaleTransaction.usd_value)).filter(
                WhaleTransaction.chain_id == chain_id,
                WhaleTransaction.token_symbol == symbol,
                WhaleTransaction.block_time >= since,
                WhaleTransaction.direction == WhaleDirection.INFLOW
            ).scalar() or 0.0

            outflow_sum = db.query(func.sum(WhaleTransaction.usd_value)).filter(
                WhaleTransaction.chain_id == chain_id,
                WhaleTransaction.token_symbol == symbol,
                WhaleTransaction.block_time >= since,
                WhaleTransaction.direction == WhaleDirection.OUTFLOW
            ).scalar() or 0.0

            if inflow_sum == 0 and outflow_sum == 0:
                return None

            net_flow = outflow_sum - inflow_sum # positive = more outflows (bullish)

            return NetflowData(
                symbol=symbol,
                chain_id=chain_id,
                period_days=days,
                net_flow_usd=float(net_flow),
                inflow_usd=float(inflow_sum),
                outflow_usd=float(outflow_sum),
                source="database",
                daily_snapshots=[]
            )
        except Exception as e:
            logger.warning(f"[NetflowSignal] DB query failed: {e}")
            return None
