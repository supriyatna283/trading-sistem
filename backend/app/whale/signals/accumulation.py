"""
Accumulation Signal Detector
==============================
Detects consistent accumulation by large non-exchange wallets.

Algorithm:
  1. Pull `accumulation_series` from provider (daily net balance change for top N wallets).
  2. Also query `whale_transactions` DB for inflows to large non-exchange wallets (fallback/supplement).
  3. Count consecutive accumulation days (net_balance_change > 0).
  4. Apply bonus if price is sideways during accumulation (stealth accumulation).
  5. Return a raw score 0-100 and detail dict.

Score breakdown:
  - 0 consecutive days  → 0
  - 3 consecutive days  → 40
  - 5 consecutive days  → 65
  - 7+ consecutive days → 85-100
  - Sideways price bonus → +10
  - Volume drop bonus   → +5 (accumulation happening on low volume = institutional)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from ..providers.base import BaseWhaleProvider

logger = logging.getLogger(__name__)


@dataclass
class AccumulationResult:
    raw_score: float                   # 0-100 before weighting
    consecutive_days: int              # longest consecutive accumulation streak
    total_net_change_usd: float        # net USD accumulated over window
    active_accumulators_avg: float     # avg number of wallets accumulating per day
    sideways_bonus: bool               # True if price was sideways during accumulation
    detail: str
    data_points: int                   # how many days of data we had
    series: list[dict] = field(default_factory=list)


class AccumulationSignal:
    """
    Computes an accumulation score for a given (symbol, chain_id) pair.
    Uses the provider for raw data and optionally the DB for supplement.
    """

    def __init__(
        self,
        min_consecutive_days: int = 2,
        sideways_threshold_pct: float = 3.0,  # price change % to be considered "sideways"
        lookback_days: int = 14,
    ):
        self.min_consecutive_days = min_consecutive_days
        self.sideways_threshold_pct = sideways_threshold_pct
        self.lookback_days = lookback_days

    async def compute(
        self,
        provider: BaseWhaleProvider,
        symbol: str,
        chain_id: str,
        db: "Session | None" = None,
        price_change_7d_pct: float | None = None,
    ) -> AccumulationResult:
        """
        Returns AccumulationResult with raw_score 0-100.
        `price_change_7d_pct` is used to detect sideways market.
        """
        try:
            series = await provider.get_accumulation_series(
                symbol=symbol,
                chain_id=chain_id,
                top_n_wallets=20,
                days=self.lookback_days,
            )
        except Exception as e:
            logger.warning(f"[AccumulationSignal] Provider error for {symbol}: {e}")
            series = []

        # Fallback: supplement from DB whale_transactions if provider returns nothing
        if not series and db is not None:
            series = self._query_db_series(db, symbol, self.lookback_days)

        if not series:
            return AccumulationResult(
                raw_score=0.0,
                consecutive_days=0,
                total_net_change_usd=0.0,
                active_accumulators_avg=0.0,
                sideways_bonus=False,
                detail="No accumulation data available.",
                data_points=0,
            )

        # Count longest consecutive accumulation streak
        max_streak = 0
        current_streak = 0
        total_net = 0.0
        total_accumulators = 0

        for day in series:
            net = float(day.get("net_balance_change", 0))
            total_net += net
            total_accumulators += int(day.get("active_accumulators", 0))
            if net > 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0

        avg_accumulators = total_accumulators / len(series) if series else 0

        # Score based on consecutive days
        streak_scores = {0: 0, 1: 15, 2: 30, 3: 45, 4: 58, 5: 68, 6: 78, 7: 87}
        raw = streak_scores.get(min(max_streak, 7), 90 if max_streak > 7 else 0)

        # Sideways bonus
        sideways = False
        if price_change_7d_pct is not None and abs(price_change_7d_pct) < self.sideways_threshold_pct:
            sideways = True
            raw = min(100, raw + 10)

        detail_parts = [
            f"{max_streak} hari berturut-turut akumulasi",
            f"Net ±${abs(total_net) / 1_000_000:.2f}M selama {len(series)} hari",
        ]
        if sideways:
            detail_parts.append("harga sideways (+bonus)")
        if avg_accumulators > 5:
            detail_parts.append(f"{avg_accumulators:.0f} dompet aktif akumulasi/hari")

        return AccumulationResult(
            raw_score=round(raw, 1),
            consecutive_days=max_streak,
            total_net_change_usd=round(total_net, 0),
            active_accumulators_avg=round(avg_accumulators, 1),
            sideways_bonus=sideways,
            detail=" — ".join(detail_parts),
            data_points=len(series),
            series=series,
        )

    def _query_db_series(self, db: "Session", symbol: str, days: int) -> list[dict]:
        """
        Supplement: aggregate WhaleTransaction inflows/outflows from DB as a proxy
        for accumulation. Groups by day, filters out exchange-to-exchange transfers.
        """
        try:
            from datetime import datetime, timedelta
            from sqlalchemy import func, case
            from app.models.whale import WhaleTransaction, Wallet, WhaleDirection

            since = datetime.utcnow() - timedelta(days=days)

            rows = (
                db.query(
                    func.date(WhaleTransaction.block_time).label("date"),
                    func.sum(
                        case(
                            (WhaleTransaction.direction == WhaleDirection.OUTFLOW, WhaleTransaction.usd_value),
                            else_=0,
                        )
                    ).label("outflow"),
                    func.sum(
                        case(
                            (WhaleTransaction.direction == WhaleDirection.INFLOW, WhaleTransaction.usd_value),
                            else_=0,
                        )
                    ).label("inflow"),
                    func.count(WhaleTransaction.id).label("count"),
                )
                .join(Wallet, WhaleTransaction.to_wallet_id == Wallet.id, isouter=True)
                .filter(
                    WhaleTransaction.block_time >= since,
                    WhaleTransaction.token_symbol == symbol,
                )
                .group_by(func.date(WhaleTransaction.block_time))
                .order_by(func.date(WhaleTransaction.block_time))
                .all()
            )

            series = []
            for row in rows:
                outflow = float(row.outflow or 0)
                inflow = float(row.inflow or 0)
                net = outflow - inflow   # positive = more exiting CEX = accumulation signal
                series.append({
                    "date": str(row.date),
                    "net_balance_change": net,
                    "active_accumulators": int(row.count or 0),
                    "is_accumulation": net > 0,
                })
            return series
        except Exception as e:
            logger.warning(f"[AccumulationSignal] DB query failed: {e}")
            return []
