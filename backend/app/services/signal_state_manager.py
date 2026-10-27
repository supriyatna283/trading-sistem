"""
Signal State Manager
====================
Real-time signal deduplication + lifecycle tracking.

Innovation:
  - Fingerprint-based deduplication (entry zone hash, not just cooldown)
  - Live price invalidation via OKX ticker (checked every 60s)
  - Signal lifecycle: ACTIVE -> HIT_TP1 | HIT_TP2 | HIT_SL | EXPIRED | CANCELLED
  - New signal for same pair allowed ONLY when previous is resolved
  - No DB needed — ultra-fast in-memory store
"""

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from enum import Enum

import httpx

logger = logging.getLogger(__name__)

# Persistent closed-loop outcome store (survives restart)
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_OUTCOMES_FILE = os.path.join(_DATA_DIR, "signal_outcomes.jsonl")


class SignalStatus(str, Enum):
    ACTIVE    = "ACTIVE"
    HIT_TP1   = "HIT_TP1"
    HIT_TP2   = "HIT_TP2"
    HIT_SL    = "HIT_SL"
    EXPIRED   = "EXPIRED"
    CANCELLED = "CANCELLED"


@dataclass
class SignalRecord:
    fingerprint:   str
    symbol:        str
    direction:     str
    entry_low:     float
    entry_high:    float
    stop_loss:     float
    take_profit_1: float
    take_profit_2: Optional[float]
    timeframe:     str
    score:         int
    grade:         str

    status:           SignalStatus = SignalStatus.ACTIVE
    created_at:       datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at:       datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_price:       Optional[float] = None
    resolution_note:  str = ""

    def age_hours(self) -> float:
        return (datetime.now(timezone.utc) - self.created_at).total_seconds() / 3600

    def is_alive(self) -> bool:
        return self.status == SignalStatus.ACTIVE

    def to_dict(self) -> dict:
        return {
            "fingerprint":     self.fingerprint[:12],
            "symbol":          self.symbol,
            "direction":       self.direction,
            "entry_low":       self.entry_low,
            "entry_high":      self.entry_high,
            "stop_loss":       self.stop_loss,
            "take_profit_1":   self.take_profit_1,
            "take_profit_2":   self.take_profit_2,
            "timeframe":       self.timeframe,
            "score":           self.score,
            "grade":           self.grade,
            "status":          self.status,
            "age_hours":       round(self.age_hours(), 2),
            "last_price":      self.last_price,
            "created_at":      self.created_at.isoformat(),
            "resolution_note": self.resolution_note,
        }


class SignalStateManager:
    """Real-time signal deduplication + lifecycle manager."""

    SIGNAL_TTL_HOURS    = 48
    PRICE_HIT_TOLERANCE = 0.001   # 0.1%
    CHECK_INTERVAL_SEC  = 60

    def __init__(self):
        self._signals: Dict[str, SignalRecord] = {}   # symbol -> active record
        self._history: List[SignalRecord] = []         # full log (this process)
        self._persisted: List[dict] = []               # loaded from disk (prior runs)
        self._watchdog_task: Optional[asyncio.Task] = None
        self._running = False
        self._load_persisted()

    # ── Fingerprint ─────────────────────────────────────────────────────────

    @staticmethod
    def _fingerprint(symbol, direction, entry_low, entry_high, timeframe) -> str:
        el  = round(entry_low,  4)
        eh  = round(entry_high, 4)
        raw = f"{symbol}:{direction}:{el}:{eh}:{timeframe}"
        return hashlib.sha256(raw.encode()).hexdigest()

    # ── Core API ─────────────────────────────────────────────────────────────

    def can_broadcast(self, symbol, direction, entry_low, entry_high, timeframe):
        fp       = self._fingerprint(symbol, direction, entry_low, entry_high, timeframe)
        existing = self._signals.get(symbol)

        if existing is None:
            return True, "no_prior_signal"
        if existing.fingerprint == fp:
            return False, f"identical_setup_still_{existing.status}"
        if existing.is_alive():
            return False, f"prior_active ({existing.age_hours():.1f}h old)"
        return True, f"prior_resolved ({existing.status})"

    def register_signal(self, symbol, direction, entry_low, entry_high,
                        stop_loss, take_profit_1, take_profit_2,
                        timeframe, score, grade) -> SignalRecord:
        fp  = self._fingerprint(symbol, direction, entry_low, entry_high, timeframe)
        rec = SignalRecord(
            fingerprint=fp, symbol=symbol, direction=direction,
            entry_low=entry_low, entry_high=entry_high,
            stop_loss=stop_loss, take_profit_1=take_profit_1,
            take_profit_2=take_profit_2, timeframe=timeframe,
            score=score, grade=grade,
        )
        self._signals[symbol] = rec
        self._history.append(rec)
        if len(self._history) > 500:
            self._history = self._history[-500:]
        logger.info(f"Signal registered: {symbol} {direction} fp={fp[:10]}")
        return rec

    def force_cancel(self, symbol: str, reason: str = "manual"):
        rec = self._signals.get(symbol)
        if rec and rec.is_alive():
            rec.status = SignalStatus.CANCELLED
            rec.resolution_note = reason
            rec.updated_at = datetime.now(timezone.utc)

    def get_active_signals(self):
        return [r.to_dict() for r in self._signals.values() if r.is_alive()]

    def get_all_signals(self, limit=50):
        return [r.to_dict() for r in self._history[-limit:]]

    def get_signal(self, symbol: str):
        rec = self._signals.get(symbol)
        return rec.to_dict() if rec else None

    # ── Closed-loop persistence & performance stats ─────────────────────────

    def _load_persisted(self):
        """Load prior signal outcomes from disk so stats survive restart."""
        try:
            if not os.path.exists(_OUTCOMES_FILE):
                return
            with open(_OUTCOMES_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self._persisted.append(json.loads(line))
                    except (ValueError, TypeError):
                        continue
            if len(self._persisted) > 2000:
                self._persisted = self._persisted[-2000:]
        except Exception as e:
            logger.warning(f"Failed to load signal history: {e}")

    def _persist_outcome(self, rec: SignalRecord):
        """Append a resolved signal outcome to the persistent journal."""
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
            record = {
                "symbol": rec.symbol,
                "direction": rec.direction,
                "timeframe": rec.timeframe,
                "grade": rec.grade,
                "score": rec.score,
                "status": rec.status.value,
                "created_at": rec.created_at.isoformat(),
                "resolved_at": rec.updated_at.isoformat(),
            }
            with open(_OUTCOMES_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.warning(f"Failed to persist signal outcome: {e}")

    def get_performance_stats(self) -> dict:
        """Aggregate resolved signals into live, closed-loop performance stats."""
        rows = []  # normalized: {status, grade, symbol}
        for r in self._history:
            if r.status in (SignalStatus.ACTIVE, SignalStatus.CANCELLED):
                continue
            rows.append({"status": r.status.value, "grade": r.grade, "symbol": r.symbol})
        for d in self._persisted:
            st = d.get("status", "")
            if st in ("ACTIVE", "CANCELLED", ""):
                continue
            rows.append({"status": st, "grade": d.get("grade", "C"), "symbol": d.get("symbol", "?")})

        total = len(rows)
        if total == 0:
            return {"total_resolved": 0, "win_rate_pct": 0.0, "by_grade": []}

        wins = sum(1 for r in rows if r["status"] in ("HIT_TP1", "HIT_TP2"))
        tp1 = sum(1 for r in rows if r["status"] == "HIT_TP1")
        tp2 = sum(1 for r in rows if r["status"] == "HIT_TP2")
        sl = sum(1 for r in rows if r["status"] == "HIT_SL")
        expired = sum(1 for r in rows if r["status"] == "EXPIRED")

        grades: Dict[str, dict] = {}
        for r in rows:
            g = r["grade"] or "C"
            grades.setdefault(g, {"total": 0, "wins": 0})
            grades[g]["total"] += 1
            if r["status"] in ("HIT_TP1", "HIT_TP2"):
                grades[g]["wins"] += 1

        by_grade = []
        for g in ("A+", "A", "B", "C"):
            if g in grades:
                s = grades[g]
                by_grade.append({"grade": g, "total": s["total"], "win_rate_pct": round(s["wins"] / s["total"] * 100, 1)})
        for g, s in grades.items():
            if g not in ("A+", "A", "B", "C"):
                by_grade.append({"grade": g, "total": s["total"], "win_rate_pct": round(s["wins"] / s["total"] * 100, 1)})

        return {
            "total_resolved": total,
            "wins": wins,
            "losses": sl,
            "expired": expired,
            "win_rate_pct": round(wins / total * 100, 1),
            "tp1_hit_pct": round(tp1 / total * 100, 1),
            "tp2_hit_pct": round(tp2 / total * 100, 1),
            "sl_hit_pct": round(sl / total * 100, 1),
            "by_grade": by_grade,
        }

    # ── Watchdog ─────────────────────────────────────────────────────────────

    async def start_watchdog(self):
        if self._running:
            return
        self._running = True
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())
        logger.info("Signal watchdog started (60s interval)")

    async def stop_watchdog(self):
        self._running = False
        if self._watchdog_task:
            self._watchdog_task.cancel()

    async def _watchdog_loop(self):
        while self._running:
            try:
                await self._check_all_signals()
            except Exception as e:
                logger.warning(f"Signal watchdog error: {e}")
            await asyncio.sleep(self.CHECK_INTERVAL_SEC)

    async def _check_all_signals(self):
        active = {s: r for s, r in self._signals.items() if r.is_alive()}
        if not active:
            return

        prices = await self._fetch_prices(list(active.keys()))

        for symbol, rec in active.items():
            price = prices.get(symbol)
            if price is None:
                continue

            rec.last_price = price
            rec.updated_at = datetime.now(timezone.utc)
            tol = self.PRICE_HIT_TOLERANCE

            if rec.direction.upper() == "LONG":
                if price <= rec.stop_loss * (1 + tol):
                    self._resolve(rec, SignalStatus.HIT_SL, f"SL hit @ {price}")
                elif rec.take_profit_2 and price >= rec.take_profit_2 * (1 - tol):
                    self._resolve(rec, SignalStatus.HIT_TP2, f"TP2 hit @ {price}")
                elif price >= rec.take_profit_1 * (1 - tol):
                    self._resolve(rec, SignalStatus.HIT_TP1, f"TP1 hit @ {price}")
            else:
                if price >= rec.stop_loss * (1 - tol):
                    self._resolve(rec, SignalStatus.HIT_SL, f"SL hit @ {price}")
                elif rec.take_profit_2 and price <= rec.take_profit_2 * (1 + tol):
                    self._resolve(rec, SignalStatus.HIT_TP2, f"TP2 hit @ {price}")
                elif price <= rec.take_profit_1 * (1 + tol):
                    self._resolve(rec, SignalStatus.HIT_TP1, f"TP1 hit @ {price}")

            if rec.is_alive() and rec.age_hours() > self.SIGNAL_TTL_HOURS:
                self._resolve(rec, SignalStatus.EXPIRED, f"TTL {self.SIGNAL_TTL_HOURS}h exceeded")

    def _resolve(self, rec: SignalRecord, status: SignalStatus, note: str):
        rec.status = status
        rec.resolution_note = note
        rec.updated_at = datetime.now(timezone.utc)
        self._persist_outcome(rec)
        logger.info(f"Signal resolved: {rec.symbol} {rec.direction} -> {status} | {note}")

    async def _fetch_prices(self, symbols: List[str]) -> Dict[str, float]:
        prices = {}
        try:
            inst_ids = ",".join(f"{s.replace('USDT','')}-USDT" for s in symbols)
            async with httpx.AsyncClient(timeout=8.0, verify=False) as client:
                resp = await client.get(
                    "https://www.okx.com/api/v5/market/tickers",
                    params={"instType": "SPOT", "instId": inst_ids}
                )
                data = resp.json()
                if data.get("code") == "0":
                    for item in data.get("data", []):
                        sym = item["instId"].replace("-", "")
                        try:
                            prices[sym] = float(item["last"])
                        except (ValueError, KeyError):
                            pass
        except Exception as e:
            logger.warning(f"Price fetch error: {e}")
        return prices


# Global singleton
signal_state_manager = SignalStateManager()