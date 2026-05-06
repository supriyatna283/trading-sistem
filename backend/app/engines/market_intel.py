"""
Market Intelligence Engine
===========================
Fetches and calculates advanced market data for signal generation:
1. BTC Dominance (CoinGecko)
2. Order Book Depth (Binance)
3. Liquidation Levels (Calculated)
4. Market Cap & Circulating Supply (CoinGecko)
5. Support & Resistance (Pivot Points from OHLCV)
"""

import httpx
import pandas as pd
import numpy as np
import logging
import time
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class MarketIntelEngine:
    """Fetches advanced market intelligence data for confluence scoring."""

    BINANCE_BASE = "https://api.binance.com/api/v3"
    COINGECKO_BASE = "https://api.coingecko.com/api/v3"

    # Map Binance symbols to CoinGecko IDs for market cap lookup
    SYMBOL_TO_COINGECKO = {
        "BTCUSDT": "bitcoin", "ETHUSDT": "ethereum", "BNBUSDT": "binancecoin",
        "SOLUSDT": "solana", "XRPUSDT": "ripple", "ADAUSDT": "cardano",
        "DOGEUSDT": "dogecoin", "AVAXUSDT": "avalanche-2", "DOTUSDT": "polkadot",
        "LINKUSDT": "chainlink", "MATICUSDT": "matic-network", "NEARUSDT": "near",
        "LTCUSDT": "litecoin", "UNIUSDT": "uniswap", "ATOMUSDT": "cosmos",
        "APTUSDT": "aptos", "ARBUSDT": "arbitrum", "OPUSDT": "optimism",
        "SUIUSDT": "sui", "PEPEUSDT": "pepe", "SHIBUSDT": "shiba-inu",
    }

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=10.0,
            verify=False,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        # Caches
        self._btc_dom_cache: Dict[str, Any] = {"data": None, "ts": 0}
        self._mcap_cache: Dict[str, Dict] = {}
        self._CACHE_TTL = 300  # 5 minutes

    # -----------------------------------------------------------------
    # 1. BTC Dominance (CoinGecko /global)
    # -----------------------------------------------------------------
    async def get_btc_dominance(self) -> Dict[str, Any]:
        """Fetch BTC market dominance percentage."""
        now = time.time()
        if self._btc_dom_cache["data"] and (now - self._btc_dom_cache["ts"]) < self._CACHE_TTL:
            return self._btc_dom_cache["data"]

        try:
            resp = await self.client.get(f"{self.COINGECKO_BASE}/global")
            resp.raise_for_status()
            data = resp.json().get("data", {})

            result = {
                "btc_dominance": data.get("market_cap_percentage", {}).get("btc", 0),
                "eth_dominance": data.get("market_cap_percentage", {}).get("eth", 0),
                "total_market_cap_usd": data.get("total_market_cap", {}).get("usd", 0),
                "total_volume_24h_usd": data.get("total_volume", {}).get("usd", 0),
                "market_cap_change_24h_pct": data.get("market_cap_change_percentage_24h_usd", 0),
            }
            self._btc_dom_cache = {"data": result, "ts": now}
            return result
        except Exception as e:
            logger.warning(f"CoinGecko global data fetch failed: {e}")
            return {
                "btc_dominance": 50.0,
                "eth_dominance": 15.0,
                "total_market_cap_usd": 0,
                "total_volume_24h_usd": 0,
                "market_cap_change_24h_pct": 0,
            }

    # -----------------------------------------------------------------
    # 2. Order Book Depth (Binance /depth)
    # -----------------------------------------------------------------
    async def get_order_book_depth(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """Fetch order book and calculate buy/sell wall ratio."""
        try:
            url = f"{self.BINANCE_BASE}/depth"
            resp = await self.client.get(url, params={"symbol": symbol.upper(), "limit": limit})
            resp.raise_for_status()
            data = resp.json()

            bids = data.get("bids", [])
            asks = data.get("asks", [])

            # Sum bid and ask volumes
            total_bid_vol = sum(float(b[1]) for b in bids)
            total_ask_vol = sum(float(a[1]) for a in asks)

            # Buy/sell pressure ratio
            ratio = total_bid_vol / total_ask_vol if total_ask_vol > 0 else 1.0

            # Best bid/ask
            best_bid = float(bids[0][0]) if bids else 0
            best_ask = float(asks[0][0]) if asks else 0
            spread_pct = ((best_ask - best_bid) / best_bid * 100) if best_bid > 0 else 0

            # Find largest walls
            largest_bid_wall = max(bids, key=lambda x: float(x[1])) if bids else [0, 0]
            largest_ask_wall = max(asks, key=lambda x: float(x[1])) if asks else [0, 0]

            return {
                "symbol": symbol,
                "bid_volume": round(total_bid_vol, 4),
                "ask_volume": round(total_ask_vol, 4),
                "buy_sell_ratio": round(ratio, 4),
                "spread_pct": round(spread_pct, 6),
                "best_bid": best_bid,
                "best_ask": best_ask,
                "largest_bid_wall": {"price": float(largest_bid_wall[0]), "qty": float(largest_bid_wall[1])},
                "largest_ask_wall": {"price": float(largest_ask_wall[0]), "qty": float(largest_ask_wall[1])},
                "bias": "BULLISH" if ratio > 1.3 else "BEARISH" if ratio < 0.7 else "NEUTRAL",
            }
        except Exception as e:
            logger.warning(f"Order book fetch failed for {symbol}: {e}")
            return {
                "symbol": symbol,
                "bid_volume": 0, "ask_volume": 0,
                "buy_sell_ratio": 1.0, "spread_pct": 0,
                "best_bid": 0, "best_ask": 0,
                "largest_bid_wall": {"price": 0, "qty": 0},
                "largest_ask_wall": {"price": 0, "qty": 0},
                "bias": "NEUTRAL",
            }

    # -----------------------------------------------------------------
    # 3. Liquidation Levels (Calculated)
    # -----------------------------------------------------------------
    def calculate_liquidation_levels(self, current_price: float, symbol: str = "") -> Dict[str, Any]:
        """
        Estimate liquidation level clusters based on common leverage levels.
        These are price levels where leveraged positions would get liquidated.
        """
        if current_price <= 0:
            return {"symbol": symbol, "levels": [], "nearest_long_liq": 0, "nearest_short_liq": 0}

        leverages = [2, 3, 5, 10, 20, 25, 50, 100]
        levels = []

        for lev in leverages:
            # Long liquidation: price drops by (1/leverage * 100)%
            long_liq = current_price * (1 - 1 / lev)
            # Short liquidation: price rises by (1/leverage * 100)%
            short_liq = current_price * (1 + 1 / lev)

            levels.append({
                "leverage": lev,
                "long_liquidation": round(long_liq, 8),
                "short_liquidation": round(short_liq, 8),
                "long_distance_pct": round((1 / lev) * 100, 2),
                "short_distance_pct": round((1 / lev) * 100, 2),
            })

        # Nearest significant liquidation zones (3x and 5x are the most common retail leverages)
        nearest_long_liq = current_price * (1 - 1 / 5)   # 5x long liq (-20%)
        nearest_short_liq = current_price * (1 + 1 / 5)   # 5x short liq (+20%)

        # High-risk cluster zone: 10x-25x leverage (4-10% from price)
        cluster_zone_low = current_price * (1 - 1 / 10)   # 10x long liq (-10%)
        cluster_zone_high = current_price * (1 + 1 / 10)  # 10x short liq (+10%)

        return {
            "symbol": symbol,
            "current_price": current_price,
            "levels": levels,
            "nearest_long_liq": round(nearest_long_liq, 8),
            "nearest_short_liq": round(nearest_short_liq, 8),
            "cluster_zone": {
                "low": round(cluster_zone_low, 8),
                "high": round(cluster_zone_high, 8),
                "description": "10x-25x leverage liquidation cluster"
            },
        }

    # -----------------------------------------------------------------
    # 4. Market Cap & Supply (CoinGecko)
    # -----------------------------------------------------------------
    async def get_market_cap(self, symbol: str) -> Dict[str, Any]:
        """Fetch market cap and circulating supply for a symbol."""
        now = time.time()
        cache_key = symbol.upper()
        if cache_key in self._mcap_cache and (now - self._mcap_cache[cache_key].get("ts", 0)) < self._CACHE_TTL:
            return self._mcap_cache[cache_key]["data"]

        coin_id = self.SYMBOL_TO_COINGECKO.get(symbol.upper())
        if not coin_id:
            return self._default_mcap(symbol)

        try:
            url = f"{self.COINGECKO_BASE}/coins/{coin_id}"
            resp = await self.client.get(url, params={
                "localization": "false",
                "tickers": "false",
                "community_data": "false",
                "developer_data": "false",
                "sparkline": "false",
            })
            resp.raise_for_status()
            data = resp.json()
            market = data.get("market_data", {})

            result = {
                "symbol": symbol,
                "market_cap_usd": market.get("market_cap", {}).get("usd", 0),
                "circulating_supply": market.get("circulating_supply", 0),
                "total_supply": market.get("total_supply", 0),
                "max_supply": market.get("max_supply"),
                "fully_diluted_valuation": market.get("fully_diluted_valuation", {}).get("usd", 0),
                "market_cap_rank": data.get("market_cap_rank", 999),
                "tier": self._classify_mcap_tier(market.get("market_cap", {}).get("usd", 0)),
            }
            self._mcap_cache[cache_key] = {"data": result, "ts": now}
            return result
        except Exception as e:
            logger.warning(f"CoinGecko market cap fetch failed for {symbol}: {e}")
            return self._default_mcap(symbol)

    def _classify_mcap_tier(self, mcap_usd: float) -> str:
        """Classify market cap tier."""
        if mcap_usd >= 10_000_000_000:  # $10B+
            return "LARGE"
        elif mcap_usd >= 1_000_000_000:  # $1B+
            return "MID"
        elif mcap_usd >= 100_000_000:  # $100M+
            return "SMALL"
        else:
            return "MICRO"

    def _default_mcap(self, symbol: str) -> Dict[str, Any]:
        return {
            "symbol": symbol, "market_cap_usd": 0, "circulating_supply": 0,
            "total_supply": 0, "max_supply": None, "fully_diluted_valuation": 0,
            "market_cap_rank": 999, "tier": "UNKNOWN",
        }

    # -----------------------------------------------------------------
    # 5. Support & Resistance (Pivot Points + Swing)
    # -----------------------------------------------------------------
    def calculate_support_resistance(self, df: pd.DataFrame, symbol: str = "") -> Dict[str, Any]:
        """
        Calculate key Support & Resistance levels using:
        1. Classic Pivot Points (from daily OHLC)
        2. Swing highs/lows
        """
        if df.empty or len(df) < 10:
            return {"symbol": symbol, "pivot": 0, "supports": [], "resistances": [], "nearest_support": 0, "nearest_resistance": 0}

        # Use last complete period for pivot calculation
        high = float(df["high"].astype(float).max())
        low = float(df["low"].astype(float).min())
        close = float(df.iloc[-1]["close"])

        # Classic Pivot Points
        pivot = (high + low + close) / 3
        s1 = 2 * pivot - high
        s2 = pivot - (high - low)
        s3 = low - 2 * (high - pivot)
        r1 = 2 * pivot - low
        r2 = pivot + (high - low)
        r3 = high + 2 * (pivot - low)

        # Swing highs and lows (last 50 candles)
        recent = df.tail(50)
        swing_highs = self._find_swing_levels(recent, "high", lookback=5)
        swing_lows = self._find_swing_levels(recent, "low", lookback=5)

        # Combine and deduplicate
        all_supports = sorted(set([round(s, 8) for s in [s1, s2, s3] + swing_lows if s < close]), reverse=True)
        all_resistances = sorted(set([round(r, 8) for r in [r1, r2, r3] + swing_highs if r > close]))

        nearest_support = all_supports[0] if all_supports else s1
        nearest_resistance = all_resistances[0] if all_resistances else r1

        return {
            "symbol": symbol,
            "current_price": close,
            "pivot": round(pivot, 8),
            "supports": all_supports[:5],  # Top 5 support levels
            "resistances": all_resistances[:5],  # Top 5 resistance levels
            "nearest_support": round(nearest_support, 8),
            "nearest_resistance": round(nearest_resistance, 8),
            "support_distance_pct": round(abs(close - nearest_support) / close * 100, 2) if close > 0 else 0,
            "resistance_distance_pct": round(abs(nearest_resistance - close) / close * 100, 2) if close > 0 else 0,
        }

    def _find_swing_levels(self, df: pd.DataFrame, col: str, lookback: int = 5) -> List[float]:
        """Find swing highs or lows."""
        values = df[col].astype(float).values
        n = len(values)
        levels = []
        is_high = col == "high"

        for i in range(lookback, n - lookback):
            window = values[i - lookback: i + lookback + 1]
            if is_high and values[i] == max(window):
                levels.append(float(values[i]))
            elif not is_high and values[i] == min(window):
                levels.append(float(values[i]))

        return levels

    # -----------------------------------------------------------------
    # Combined overview for one symbol
    # -----------------------------------------------------------------
    async def get_overview(self, symbol: str, df: pd.DataFrame = None, current_price: float = 0) -> Dict[str, Any]:
        """Get combined market intelligence for one symbol."""
        btc_dom = await self.get_btc_dominance()
        orderbook = await self.get_order_book_depth(symbol)
        mcap = await self.get_market_cap(symbol)

        liq_levels = self.calculate_liquidation_levels(current_price or orderbook.get("best_bid", 0), symbol)
        sr_levels = self.calculate_support_resistance(df, symbol) if df is not None and not df.empty else {}

        return {
            "btc_dominance": btc_dom,
            "orderbook": orderbook,
            "liquidation": liq_levels,
            "market_cap": mcap,
            "support_resistance": sr_levels,
        }

    async def close(self):
        await self.client.aclose()
