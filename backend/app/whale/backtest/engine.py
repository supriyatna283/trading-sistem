"""
Backtest Engine
================
Tests whether historical whale scores correlate with forward price returns.

Methodology:
  1. Load historical whale_scores from DB for a given symbol.
  2. For each score, fetch the price at score_time and N days later.
  3. Compute forward return (%) for each score.
  4. Segment scores by grade (A/B/C/D/F) and measure average return per grade.
  5. Output correlation stats, win rate per grade, and a confusion matrix.

Price data: fetched from CoinGecko (free /market_chart endpoint).
Limitation: CoinGecko free tier only has daily OHLC, 90-day window max.

Usage:
    engine = BacktestEngine()
    result = await engine.run(db, symbol="HYPE", chain_id="hyperliquid", forward_days=7)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

import httpx

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

CG_BASE = "https://api.coingecko.com/api/v3"
SYMBOL_TO_CG_ID = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
    "BNB": "binancecoin", "HYPE": "hyperliquid",
}


@dataclass
class GradeStats:
    grade: str
    count: int
    avg_forward_return_pct: float
    win_rate_pct: float         # % of cases where price went up
    median_return_pct: float
    best_pct: float
    worst_pct: float


@dataclass
class BacktestResult:
    symbol: str
    chain_id: str
    forward_days: int
    total_samples: int
    overall_correlation: float       # Pearson r between score and forward return
    grade_stats: list[GradeStats]
    samples: list[dict]              # raw data for charting
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "chain_id": self.chain_id,
            "forward_days": self.forward_days,
            "total_samples": self.total_samples,
            "overall_correlation": round(self.overall_correlation, 4),
            "grade_stats": [
                {
                    "grade": g.grade,
                    "count": g.count,
                    "avg_forward_return_pct": round(g.avg_forward_return_pct, 2),
                    "win_rate_pct": round(g.win_rate_pct, 1),
                    "median_return_pct": round(g.median_return_pct, 2),
                    "best_pct": round(g.best_pct, 2),
                    "worst_pct": round(g.worst_pct, 2),
                }
                for g in self.grade_stats
            ],
            "samples": self.samples[:100],  # limit for API response size
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "note": self.note,
        }


class BacktestEngine:

    async def _get_price_history(
        self, symbol: str, days: int = 90
    ) -> dict[str, float]:
        """
        Fetch daily close prices from CoinGecko.
        Returns { "YYYY-MM-DD": price_usd }.
        """
        cg_id = SYMBOL_TO_CG_ID.get(symbol.upper(), symbol.lower())
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(
                    f"{CG_BASE}/coins/{cg_id}/market_chart",
                    params={"vs_currency": "usd", "days": str(days), "interval": "daily"},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.warning(f"[BacktestEngine] CoinGecko error for {symbol}: {e}")
            return {}

        prices: dict[str, float] = {}
        for ts_ms, price in data.get("prices", []):
            date_str = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            prices[date_str] = float(price)

        return prices

    async def run(
        self,
        db: "Session",
        symbol: str,
        chain_id: str,
        forward_days: int = 7,
        min_samples: int = 5,
    ) -> BacktestResult:
        """
        Main backtest method.
        """
        import statistics

        # 1. Load historical scores from DB
        try:
            from app.models.whale import WhaleScore, WatchlistCoin
            scores = (
                db.query(WhaleScore)
                .join(WatchlistCoin)
                .filter(
                    WatchlistCoin.symbol == symbol,
                    WatchlistCoin.chain_id == chain_id,
                    # Only use scores old enough to have forward data
                    WhaleScore.scored_at <= datetime.utcnow() - timedelta(days=forward_days),
                )
                .order_by(WhaleScore.scored_at)
                .all()
            )
        except Exception as e:
            logger.error(f"[BacktestEngine] DB query failed: {e}")
            return BacktestResult(
                symbol=symbol, chain_id=chain_id, forward_days=forward_days,
                total_samples=0, overall_correlation=0.0, grade_stats=[],
                samples=[], note=f"DB error: {e}"
            )

        if len(scores) < min_samples:
            return BacktestResult(
                symbol=symbol, chain_id=chain_id, forward_days=forward_days,
                total_samples=len(scores), overall_correlation=0.0, grade_stats=[],
                samples=[],
                note=f"Data tidak cukup untuk backtest (minimum {min_samples} sample, ada {len(scores)})."
            )

        # 2. Fetch price history
        max_days = max(90, forward_days + 10)
        price_history = await self._get_price_history(symbol, days=max_days)

        if not price_history:
            return BacktestResult(
                symbol=symbol, chain_id=chain_id, forward_days=forward_days,
                total_samples=len(scores), overall_correlation=0.0, grade_stats=[],
                samples=[], note="Tidak dapat mengambil data harga dari CoinGecko."
            )

        # 3. Pair each score with forward return
        samples: list[dict] = []
        for score_row in scores:
            scored_date = score_row.scored_at.strftime("%Y-%m-%d")
            forward_date = (score_row.scored_at + timedelta(days=forward_days)).strftime("%Y-%m-%d")

            price_at_score = price_history.get(scored_date)
            price_forward = price_history.get(forward_date)

            if price_at_score and price_forward and price_at_score > 0:
                fwd_return = (price_forward - price_at_score) / price_at_score * 100
                samples.append({
                    "date": scored_date,
                    "score": float(score_row.score),
                    "grade": score_row.grade if hasattr(score_row, "grade") else "?",
                    "price_at_score": price_at_score,
                    "price_forward": price_forward,
                    "forward_return_pct": round(fwd_return, 2),
                    "win": fwd_return > 0,
                })

        if len(samples) < min_samples:
            return BacktestResult(
                symbol=symbol, chain_id=chain_id, forward_days=forward_days,
                total_samples=len(samples), overall_correlation=0.0, grade_stats=[],
                samples=samples,
                note="Data harga tidak mencukupi untuk pasangkan dengan skor."
            )

        # 4. Compute overall correlation (Pearson r)
        score_vals = [s["score"] for s in samples]
        return_vals = [s["forward_return_pct"] for s in samples]
        correlation = self._pearson_r(score_vals, return_vals)

        # 5. Grade statistics
        grade_map: dict[str, list[float]] = {}
        for s in samples:
            g = s["grade"]
            grade_map.setdefault(g, []).append(s["forward_return_pct"])

        grade_stats: list[GradeStats] = []
        for grade, returns in sorted(grade_map.items()):
            wins = sum(1 for r in returns if r > 0)
            grade_stats.append(GradeStats(
                grade=grade,
                count=len(returns),
                avg_forward_return_pct=statistics.mean(returns),
                win_rate_pct=wins / len(returns) * 100,
                median_return_pct=statistics.median(returns),
                best_pct=max(returns),
                worst_pct=min(returns),
            ))

        period_start = datetime.strptime(samples[0]["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        period_end = datetime.strptime(samples[-1]["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)

        return BacktestResult(
            symbol=symbol,
            chain_id=chain_id,
            forward_days=forward_days,
            total_samples=len(samples),
            overall_correlation=correlation,
            grade_stats=grade_stats,
            samples=samples,
            period_start=period_start,
            period_end=period_end,
            note=(
                f"Korelasi Pearson r={correlation:.3f}. "
                f"r > 0.3 = korelasi lemah positif, r > 0.6 = kuat. "
                f"Gunakan untuk kalibrasi bobot, bukan prediksi harga."
            ),
        )

    @staticmethod
    def _pearson_r(x: list[float], y: list[float]) -> float:
        """Compute Pearson correlation coefficient without scipy."""
        n = len(x)
        if n < 2:
            return 0.0
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        den_x = (sum((xi - mean_x) ** 2 for xi in x)) ** 0.5
        den_y = (sum((yi - mean_y) ** 2 for yi in y)) ** 0.5
        if den_x == 0 or den_y == 0:
            return 0.0
        return round(num / (den_x * den_y), 4)
