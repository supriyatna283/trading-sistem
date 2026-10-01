"""
Session Pairs Volume Engine
============================
Returns the top-volume trading pairs active during each ICT killzone session.

Sessions (UTC):
  ASIA    : 00:00 – 07:00  → Crypto-dominant (BTC, ETH, Asian altcoins)
  LONDON  : 07:00 – 12:00  → Forex-dominant + BTC/ETH
  NY_OPEN : 12:00 – 17:00  → Most liquid session; all major pairs
  NY_PM   : 17:00 – 20:00  → Closing wind-down
  DEAD    : 20:00 – 24:00  → Low volume; avoid trading

Data source: Binance 24hr ticker API (live volume & price change)
Fallback: curated static list with estimated volumes
"""

import httpx
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ─── Session definitions ────────────────────────────────
SESSION_CONFIG = {
    "ASIA": {
        "label":     "Asia",
        "utc_range": (0, 7),
        "emoji":     "🌏",
        "color":     "#f59e0b",
        "description": "00:00–07:00 UTC · Low volume · Mark range, don't trade",
        "top_pairs": [
            "BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","SOLUSDT",
            "ADAUSDT","DOGEUSDT","AVAXUSDT","SUIUSDT","TONUSDT",
            "TRXUSDT","NEARUSDT","LINKUSDT","DOTUSDT","MATICUSDT",
        ],
        "focus": "Crypto — Asian exchanges dominate. Mark Asia High/Low.",
    },
    "LONDON": {
        "label":     "London",
        "utc_range": (7, 12),
        "emoji":     "🇬🇧",
        "color":     "#3b82f6",
        "description": "07:00–12:00 UTC · Judas Swing · Sweep Asia High/Low",
        "top_pairs": [
            "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
            "AVAXUSDT","LINKUSDT","DOGEUSDT","ADAUSDT","LTCUSDT",
            "ATOMUSDT","OPUSDT","ARBUSDT","INJUSDT","TIAUSDT",
        ],
        "focus": "BTC leads. Watch for liquidity sweep of Asia range before real move.",
    },
    "NY_OPEN": {
        "label":     "NY Open",
        "utc_range": (12, 17),
        "emoji":     "🗽",
        "color":     "#10b981",
        "description": "12:00–17:00 UTC · Highest volume · Best setups",
        "top_pairs": [
            "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
            "AVAXUSDT","DOGEUSDT","LINKUSDT","ADAUSDT","MATICUSDT",
            "OPUSDT","ARBUSDT","INJUSDT","SUIUSDT","PEPEUSDT",
        ],
        "focus": "Most reliable setups. Confirms or reverses London direction.",
    },
    "NY_PM": {
        "label":     "NY Afternoon",
        "utc_range": (17, 20),
        "emoji":     "🌆",
        "color":     "#8b5cf6",
        "description": "17:00–20:00 UTC · Closing · Reduce exposure",
        "top_pairs": [
            "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
            "AVAXUSDT","DOGEUSDT","LINKUSDT","ADAUSDT","LTCUSDT",
        ],
        "focus": "Wind-down. Close or trail stops. Avoid new positions.",
    },
    "DEAD": {
        "label":     "Dead Zone",
        "utc_range": (20, 24),
        "emoji":     "😴",
        "color":     "#475569",
        "description": "20:00–24:00 UTC · Very low volume · AVOID trading",
        "top_pairs": [
            "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
        ],
        "focus": "No trading. Review setups for next session.",
    },
}


@dataclass
class PairData:
    symbol:          str
    base_asset:      str
    price:           float
    change_24h:      float     # % change
    volume_24h_usd:  float     # USDT volume
    volume_rank:     int       # rank in current session (1 = highest vol)
    high_24h:        float
    low_24h:         float
    is_killzone_fav: bool      # Known high-mover in this session
    session_relevance: str     # "PRIMARY" | "SECONDARY" | "BONUS"


@dataclass
class SessionPairsResult:
    current_session:    str
    session_label:      str
    session_emoji:      str
    session_color:      str
    session_description: str
    session_focus:      str
    utc_hour:           int
    utc_time:           str
    pairs:              List[PairData]
    total_session_vol:  float    # Total USD volume of listed pairs
    top_mover:          Optional[PairData]
    top_volume:         Optional[PairData]
    is_killzone_active: bool
    minutes_to_next:    int      # Minutes until next killzone
    next_session:       str


class SessionPairsEngine:

    BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"
    _cache: Dict = {}
    _cache_ts: float = 0
    CACHE_TTL = 60  # 60 seconds cache

    def get_current_session(self, utc_hour: int) -> Tuple[str, str, int]:
        """Returns (session_id, next_session_id, minutes_to_next)."""
        sessions_ordered = ["ASIA", "LONDON", "NY_OPEN", "NY_PM", "DEAD"]
        boundaries = [0, 7, 12, 17, 20, 24]

        for i, (sid, start) in enumerate(zip(sessions_ordered, boundaries)):
            end = boundaries[i + 1]
            if start <= utc_hour < end:
                next_sid = sessions_ordered[(i + 1) % len(sessions_ordered)]
                # Minutes to next session start
                next_start = boundaries[i + 1] % 24
                mins_remaining = (next_start - utc_hour) * 60
                return sid, next_sid, max(0, mins_remaining)

        return "DEAD", "ASIA", 0

    async def get_session_pairs(
        self,
        session_override: Optional[str] = None,
        top_n: int = 20,
    ) -> SessionPairsResult:
        """
        Fetch live volume data from Binance and return top pairs for current session.
        Falls back to curated static data if Binance is unreachable.
        """
        now_utc = datetime.now(timezone.utc)
        utc_hour = now_utc.hour
        utc_time = now_utc.strftime("%H:%M UTC")

        if session_override and session_override in SESSION_CONFIG:
            session_id = session_override
            _, next_sid, mins_next = self.get_current_session(utc_hour)
        else:
            session_id, next_sid, mins_next = self.get_current_session(utc_hour)

        cfg = SESSION_CONFIG[session_id]
        is_killzone = session_id in ("LONDON", "NY_OPEN")

        # ── Fetch live data (with cache) ───────────────────────
        ticker_data = await self._fetch_binance_tickers()

        # ── Build pair list ────────────────────────────────────
        pairs = self._build_pairs(
            ticker_data, cfg["top_pairs"], session_id, top_n
        )

        total_vol = sum(p.volume_24h_usd for p in pairs)
        top_vol   = max(pairs, key=lambda p: p.volume_24h_usd) if pairs else None
        top_move  = max(pairs, key=lambda p: abs(p.change_24h)) if pairs else None

        return SessionPairsResult(
            current_session=session_id,
            session_label=cfg["label"],
            session_emoji=cfg["emoji"],
            session_color=cfg["color"],
            session_description=cfg["description"],
            session_focus=cfg["focus"],
            utc_hour=utc_hour,
            utc_time=utc_time,
            pairs=pairs,
            total_session_vol=total_vol,
            top_mover=top_move,
            top_volume=top_vol,
            is_killzone_active=is_killzone,
            minutes_to_next=mins_next,
            next_session=next_sid,
        )

    async def _fetch_binance_tickers(self) -> Dict[str, dict]:
        """Fetch all USDT spot tickers from Binance (cached 60s)."""
        import time as _time
        now = _time.time()
        if self._cache and (now - self._cache_ts) < self.CACHE_TTL:
            return self._cache

        try:
            async with httpx.AsyncClient(timeout=8.0, verify=False) as client:
                resp = await client.get(self.BINANCE_TICKER_URL)
                resp.raise_for_status()
                tickers = resp.json()

            data: Dict[str, dict] = {}
            for t in tickers:
                sym = t.get("symbol", "")
                if sym.endswith("USDT"):
                    data[sym] = t

            self._cache    = data
            self._cache_ts = now
            return data

        except Exception as e:
            logger.warning(f"Binance ticker fetch failed: {e} — using fallback")
            return self._fallback_tickers()

    def _build_pairs(
        self,
        ticker_data: Dict[str, dict],
        session_symbols: List[str],
        session_id: str,
        top_n: int,
    ) -> List[PairData]:

        pairs = []

        # ── Try live data first ────────────────────────────────
        if ticker_data:
            # Build list from all USDT pairs, sorted by quoteVolume
            all_usdt = sorted(
                ticker_data.values(),
                key=lambda t: float(t.get("quoteVolume", 0)),
                reverse=True,
            )

            # Take top_n overall + ensure session faves are included
            seen = set()
            candidates = []

            # First add session-specific favorites if they have live data
            for sym in session_symbols:
                if sym in ticker_data and sym not in seen:
                    candidates.append(ticker_data[sym])
                    seen.add(sym)

            # Fill rest with top-volume USDT pairs
            for t in all_usdt:
                if len(candidates) >= top_n:
                    break
                sym = t.get("symbol", "")
                if sym not in seen and not self._is_stablecoin_pair(sym):
                    candidates.append(t)
                    seen.add(sym)

            # Sort final list by volume
            candidates.sort(key=lambda t: float(t.get("quoteVolume", 0)), reverse=True)

            for rank, t in enumerate(candidates[:top_n], 1):
                sym = t.get("symbol", "")
                price = float(t.get("lastPrice", 0))
                change = float(t.get("priceChangePercent", 0))
                vol_usd = float(t.get("quoteVolume", 0))
                h24 = float(t.get("highPrice", price))
                l24 = float(t.get("lowPrice", price))
                base = sym.replace("USDT", "")
                is_fav = sym in session_symbols

                relevance = (
                    "PRIMARY"   if sym in session_symbols[:5] else
                    "SECONDARY" if sym in session_symbols else
                    "BONUS"
                )

                pairs.append(PairData(
                    symbol=sym, base_asset=base,
                    price=price, change_24h=round(change, 2),
                    volume_24h_usd=vol_usd, volume_rank=rank,
                    high_24h=h24, low_24h=l24,
                    is_killzone_fav=is_fav,
                    session_relevance=relevance,
                ))

        # ── Fallback: static data ──────────────────────────────
        if not pairs:
            pairs = self._static_pairs(session_symbols)

        return pairs

    def _is_stablecoin_pair(self, symbol: str) -> bool:
        stables = ["USDC", "BUSD", "TUSD", "DAI", "FDUSD", "USDP", "PYUSD"]
        return any(symbol.startswith(s) for s in stables)

    def _fallback_tickers(self) -> Dict[str, dict]:
        return {}

    def _static_pairs(self, symbols: List[str]) -> List[PairData]:
        """Curated fallback data when Binance is unreachable."""
        fallback_prices = {
            "BTCUSDT": (67000, 2.3, 2_500_000_000),
            "ETHUSDT": (3400,  1.8, 1_200_000_000),
            "BNBUSDT": (580,   0.9,   180_000_000),
            "SOLUSDT": (145,   3.5,   320_000_000),
            "XRPUSDT": (0.62,  1.2,   210_000_000),
            "ADAUSDT": (0.45,  0.8,    90_000_000),
            "DOGEUSDT":(0.12,  2.1,   140_000_000),
            "AVAXUSDT":(35,    1.5,    85_000_000),
            "LINKUSDT":(15,    2.2,    75_000_000),
            "DOTUSDT": (7.5,   1.1,    60_000_000),
            "MATICUSDT":(0.85, 1.3,    70_000_000),
            "LTCUSDT": (88,    0.7,    55_000_000),
            "NEARUSDT":(6.2,   2.8,    48_000_000),
            "OPUSDT":  (2.1,   3.2,    42_000_000),
            "ARBUSDT": (1.05,  2.9,    38_000_000),
        }
        pairs = []
        for rank, sym in enumerate(symbols, 1):
            p, ch, vol = fallback_prices.get(sym, (1.0, 0.0, 10_000_000))
            pairs.append(PairData(
                symbol=sym, base_asset=sym.replace("USDT",""),
                price=p, change_24h=ch, volume_24h_usd=vol, volume_rank=rank,
                high_24h=p*1.05, low_24h=p*0.95,
                is_killzone_fav=True, session_relevance="PRIMARY",
            ))
        return pairs

    def to_dict(self, r: SessionPairsResult) -> dict:
        def pair_dict(p: PairData) -> dict:
            return {
                "symbol":           p.symbol,
                "base_asset":       p.base_asset,
                "price":            p.price,
                "change_24h":       p.change_24h,
                "volume_24h_usd":   p.volume_24h_usd,
                "volume_24h_fmt":   self._fmt_vol(p.volume_24h_usd),
                "volume_rank":      p.volume_rank,
                "high_24h":         p.high_24h,
                "low_24h":          p.low_24h,
                "is_killzone_fav":  p.is_killzone_fav,
                "session_relevance": p.session_relevance,
            }

        return {
            "current_session":    r.current_session,
            "session_label":      r.session_label,
            "session_emoji":      r.session_emoji,
            "session_color":      r.session_color,
            "session_description": r.session_description,
            "session_focus":      r.session_focus,
            "utc_time":           r.utc_time,
            "utc_hour":           r.utc_hour,
            "is_killzone_active": r.is_killzone_active,
            "minutes_to_next":    r.minutes_to_next,
            "next_session":       r.next_session,
            "total_session_vol_fmt": self._fmt_vol(r.total_session_vol),
            "top_mover":   pair_dict(r.top_mover)  if r.top_mover  else None,
            "top_volume":  pair_dict(r.top_volume) if r.top_volume else None,
            "pairs": [pair_dict(p) for p in r.pairs],
        }

    @staticmethod
    def _fmt_vol(v: float) -> str:
        if v >= 1_000_000_000: return f"${v/1_000_000_000:.2f}B"
        if v >= 1_000_000:     return f"${v/1_000_000:.1f}M"
        if v >= 1_000:         return f"${v/1_000:.1f}K"
        return f"${v:.0f}"
