"""
Order Flow Engine — Footprint Chart & Whale Detection
=======================================================
Analyzes trade-by-trade data from Binance to build:
1. Footprint: buy/sell volume at each price level per candle
2. Whale detection: large trades above configurable threshold
"""

import logging
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import math

logger = logging.getLogger(__name__)

# Default thresholds (in USDT notional value)
WHALE_THRESHOLD_USDT = 50_000    # $50k+ = whale trade
SHARK_THRESHOLD_USDT = 10_000   # $10k+ = shark trade
FISH_THRESHOLD_USDT = 1_000     # $1k+ = notable trade

# Tick size for grouping trades into price levels (in % of price)
PRICE_LEVEL_TICK_PCT = 0.05  # 0.05% tick grouping


class FootprintCandle:
    """A single candle with buy/sell volume per price level."""

    def __init__(self, timestamp: int, open_: float, high: float, low: float, close: float):
        self.timestamp = timestamp
        self.open = open_
        self.high = high
        self.low = low
        self.close = close
        self.levels: Dict[float, Dict] = {}   # price -> {buy_vol, sell_vol, delta}
        self.total_buy_vol: float = 0
        self.total_sell_vol: float = 0
        self.total_volume: float = 0

    @property
    def delta(self) -> float:
        return self.total_buy_vol - self.total_sell_vol

    @property
    def delta_pct(self) -> float:
        if self.total_volume == 0:
            return 0
        return (self.delta / self.total_volume) * 100

    @property
    def poc(self) -> Optional[float]:
        """Point of Control — price level with highest volume."""
        if not self.levels:
            return None
        return max(self.levels, key=lambda p: self.levels[p]["total_vol"])

    def add_trade(self, price: float, qty: float, is_buyer_maker: bool):
        """Add a trade to the appropriate price level."""
        tick = self._get_tick_size(price)
        level = round(price / tick) * tick
        level = round(level, 8)

        if level not in self.levels:
            self.levels[level] = {"buy_vol": 0, "sell_vol": 0, "total_vol": 0, "delta": 0}

        if is_buyer_maker:
            # Buyer maker = sell aggressor
            self.levels[level]["sell_vol"] += qty
            self.total_sell_vol += qty
        else:
            # Seller maker = buy aggressor
            self.levels[level]["buy_vol"] += qty
            self.total_buy_vol += qty

        self.levels[level]["total_vol"] = self.levels[level]["buy_vol"] + self.levels[level]["sell_vol"]
        self.levels[level]["delta"] = self.levels[level]["buy_vol"] - self.levels[level]["sell_vol"]
        self.total_volume += qty

    def _get_tick_size(self, price: float) -> float:
        """Compute tick size as a % of price for grouping."""
        return max(price * PRICE_LEVEL_TICK_PCT / 100, 0.000001)

    def to_dict(self) -> dict:
        sorted_levels = sorted(self.levels.items(), key=lambda x: x[0], reverse=True)
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "total_buy_vol": round(self.total_buy_vol, 4),
            "total_sell_vol": round(self.total_sell_vol, 4),
            "total_volume": round(self.total_volume, 4),
            "delta": round(self.delta, 4),
            "delta_pct": round(self.delta_pct, 2),
            "poc": self.poc,
            "levels": [
                {
                    "price": round(p, 8),
                    "buy_vol": round(v["buy_vol"], 4),
                    "sell_vol": round(v["sell_vol"], 4),
                    "delta": round(v["delta"], 4),
                    "total_vol": round(v["total_vol"], 4),
                }
                for p, v in sorted_levels
            ],
        }


class WhaleTrade:
    """A single detected whale/large trade."""

    def __init__(
        self,
        symbol: str,
        price: float,
        qty: float,
        notional: float,
        side: str,
        timestamp: int,
        agg_trade_id: Optional[int] = None,
    ):
        self.symbol = symbol
        self.price = price
        self.qty = qty
        self.notional = notional
        self.side = side  # BUY or SELL
        self.timestamp = timestamp
        self.agg_trade_id = agg_trade_id
        self.tier = self._get_tier(notional)

    def _get_tier(self, notional: float) -> str:
        if notional >= WHALE_THRESHOLD_USDT:
            return "WHALE"
        elif notional >= SHARK_THRESHOLD_USDT:
            return "SHARK"
        elif notional >= FISH_THRESHOLD_USDT:
            return "FISH"
        return "RETAIL"

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "qty": self.qty,
            "notional": round(self.notional, 2),
            "side": self.side,
            "tier": self.tier,
            "timestamp": self.timestamp,  # ms epoch — frontend formats to local TZ
            "agg_trade_id": self.agg_trade_id,
        }


class OrderFlowEngine:
    """Fetches and analyzes Binance trade data for footprint and whale detection."""

    def __init__(self):
        from app.config import get_settings
        self.settings = get_settings()
        self._whale_cache: Dict[str, List[WhaleTrade]] = defaultdict(list)  # symbol -> recent whales
        self._max_cached_per_symbol = 200

    def get_binance_client(self):
        from binance.client import Client
        return Client(self.settings.BINANCE_API_KEY, self.settings.BINANCE_API_SECRET)

    async def get_footprint(
        self, symbol: str, timeframe: str = "5m", limit: int = 10
    ) -> List[dict]:
        """Build footprint candles for a symbol/timeframe."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._fetch_footprint_sync, symbol, timeframe, limit)
            return result
        except Exception as e:
            logger.error(f"Footprint fetch failed for {symbol}: {e}")
            return []

    def _fetch_footprint_sync(self, symbol: str, timeframe: str, limit: int) -> List[dict]:
        """Synchronous footprint fetch using Binance REST API."""
        from binance.client import Client

        client = self.get_binance_client()

        # 1. Fetch OHLCV klines to get candle boundaries
        klines = client.futures_klines(symbol=symbol, interval=timeframe, limit=limit + 1)
        if not klines:
            return []

        # 2. Compute time range: from oldest kline to now
        start_time = int(klines[0][0])
        end_time = int(klines[-1][6])  # close time of last candle

        # 3. Fetch all agg trades in the time range
        all_trades = []
        current_start = start_time
        while current_start < end_time:
            chunk_end = min(current_start + 3600 * 1000, end_time)
            trades = client.futures_aggregate_trades(
                symbol=symbol,
                startTime=current_start,
                endTime=chunk_end,
            )
            all_trades.extend(trades)
            if not trades:
                break
            current_start = int(trades[-1]["T"]) + 1

        # 4. Build candle objects
        candles: List[FootprintCandle] = []
        for k in klines[:-1]:  # exclude the last (incomplete) candle
            candle = FootprintCandle(
                timestamp=int(k[0]),
                open_=float(k[1]),
                high=float(k[2]),
                low=float(k[3]),
                close=float(k[4]),
            )
            candles.append(candle)

        # 5. Assign each trade to its candle
        for trade in all_trades:
            ts = int(trade["T"])
            qty = float(trade["q"])
            price = float(trade["p"])
            is_buyer_maker = trade["m"]  # True = seller was aggressor

            for candle in candles:
                c_open = candle.timestamp
                c_close = c_open + self._tf_to_ms(timeframe)
                if c_open <= ts < c_close:
                    candle.add_trade(price, qty, is_buyer_maker)
                    break

        return [c.to_dict() for c in candles]

    def _tf_to_ms(self, timeframe: str) -> int:
        """Convert timeframe string to milliseconds."""
        mapping = {
            "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
            "30m": 1_800_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000,
        }
        return mapping.get(timeframe, 300_000)

    async def get_recent_whales(
        self,
        symbol: str,
        threshold_usdt: float = WHALE_THRESHOLD_USDT,
        limit: int = 100,
        lookback_seconds: int = 3600,
    ) -> List[dict]:
        """Fetch recent large trades (whale detection) from Binance agg trades."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._fetch_whales_sync, symbol, threshold_usdt, limit, lookback_seconds
            )
            return result
        except Exception as e:
            logger.error(f"Whale fetch failed for {symbol}: {e}")
            return []

    def _fetch_whales_sync(
        self, symbol: str, threshold_usdt: float, limit: int, lookback_seconds: int
    ) -> List[dict]:
        client = self.get_binance_client()
        start_time = int((datetime.utcnow() - timedelta(seconds=lookback_seconds)).timestamp() * 1000)

        trades = client.futures_aggregate_trades(
            symbol=symbol,
            startTime=start_time,
            limit=1000,
        )

        whales = []
        for t in trades:
            price = float(t["p"])
            qty = float(t["q"])
            notional = price * qty
            if notional < threshold_usdt:
                continue
            side = "SELL" if t["m"] else "BUY"  # m=True means buyer is maker (sell aggressor)
            whale = WhaleTrade(
                symbol=symbol,
                price=price,
                qty=qty,
                notional=notional,
                side=side,
                timestamp=int(t["T"]),
                agg_trade_id=int(t["a"]),
            )
            whales.append(whale.to_dict())

        whales.sort(key=lambda x: x["notional"], reverse=True)
        return whales[:limit]

    async def get_multi_symbol_whales(
        self,
        symbols: List[str],
        threshold_usdt: float = WHALE_THRESHOLD_USDT,
        lookback_seconds: int = 300,
    ) -> List[dict]:
        """Scan multiple symbols for whale trades concurrently."""
        tasks = [
            self.get_recent_whales(sym, threshold_usdt, 50, lookback_seconds)
            for sym in symbols
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_whales = []
        for r in results:
            if isinstance(r, list):
                all_whales.extend(r)
        all_whales.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return all_whales[:200]

    def cache_whale(self, symbol: str, whale: WhaleTrade):
        """Cache a whale trade for the WebSocket stream broadcast."""
        cache = self._whale_cache[symbol]
        cache.append(whale)
        if len(cache) > self._max_cached_per_symbol:
            self._whale_cache[symbol] = cache[-self._max_cached_per_symbol:]

    def get_cached_whales(self, symbol: Optional[str] = None) -> List[dict]:
        if symbol:
            return [w.to_dict() for w in self._whale_cache.get(symbol, [])]
        all_w = []
        for trades in self._whale_cache.values():
            all_w.extend([t.to_dict() for t in trades])
        all_w.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return all_w[:200]

    def get_flow_summary(self, trades: List[dict]) -> dict:
        """Compute buy/sell pressure summary from a list of trades."""
        buy_vol = sum(t["notional"] for t in trades if t["side"] == "BUY")
        sell_vol = sum(t["notional"] for t in trades if t["side"] == "SELL")
        total = buy_vol + sell_vol
        return {
            "buy_pressure": round(buy_vol, 2),
            "sell_pressure": round(sell_vol, 2),
            "total_flow": round(total, 2),
            "buy_pct": round(buy_vol / total * 100, 1) if total > 0 else 50,
            "sell_pct": round(sell_vol / total * 100, 1) if total > 0 else 50,
            "net_flow": round(buy_vol - sell_vol, 2),
            "dominance": "BUY" if buy_vol > sell_vol else "SELL",
            "trade_count": len(trades),
        }


# Singleton
order_flow_engine = OrderFlowEngine()
