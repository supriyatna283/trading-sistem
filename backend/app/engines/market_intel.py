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
        "LINKUSDT": "chainlink", "POLUSDT": "polygon-ecosystem-token", "NEARUSDT": "near",
        "LTCUSDT": "litecoin", "UNIUSDT": "uniswap", "ATOMUSDT": "cosmos",
        "APTUSDT": "aptos", "ARBUSDT": "arbitrum", "OPUSDT": "optimism",
        "SUIUSDT": "sui", "PEPEUSDT": "pepe", "1000PEPEUSDT": "pepe",
        "SHIBUSDT": "shiba-inu", "1000SHIBUSDT": "shiba-inu", "BONKUSDT": "bonk",
        "1000BONKUSDT": "bonk", "WIFUSDT": "dogwifcoin", "TONUSDT": "the-open-network",
        "FETUSDT": "fetch-ai", "RENDERUSDT": "render-token", "TAOUSDT": "bittensor",
        "INJUSDT": "injective-protocol", "TIAUSDT": "celestia", "JUPUSDT": "jupiter-exchange-solana",
        "PYTHUSDT": "pyth-network", "JTOUSDT": "jito-governance-token", "ONDOUSDT": "ondo-finance",
        "SEIUSDT": "sei-network", "STRKUSDT": "starknet", "AAVEUSDT": "aave", "FILUSDT": "filecoin",
        "ZECUSDT": "zcash", "ASTERUSDT": "aster", "HYPEUSDT": "hyperliquid"
    }

    # Static market-cap tier fallback so scanner never blocks on CoinGecko rate limits
    LARGE_CAP_SYMBOLS = {
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
        "ADAUSDT", "TRXUSDT", "AVAXUSDT", "TONUSDT", "LINKUSDT", "SHIBUSDT",
        "1000SHIBUSDT", "SUIUSDT", "DOTUSDT", "BCHUSDT", "LTCUSDT", "NEARUSDT",
    }

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=3.5,
            verify=False,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        # Caches
        self._btc_dom_cache: Dict[str, Any] = {"data": None, "ts": 0}
        self._mcap_cache: Dict[str, Dict] = {}
        self._ob_cache: Dict[str, Dict] = {}
        self._batch_mcap_ts: float = 0.0
        self._CACHE_TTL = 600  # 10 minutes
        self._OB_CACHE_TTL = 45  # 45 seconds

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
        """Fetch order book (OKX primary + Binance fallback) with 45s cache."""
        sym = symbol.upper()
        now = time.time()
        cached_ob = self._ob_cache.get(sym)
        if cached_ob and (now - cached_ob["ts"]) < self._OB_CACHE_TTL:
            return cached_ob["data"]

        bids = []
        asks = []
        try:
            # 1. Try OKX public orderbook first (fast, non-geo-blocked)
            okx_inst = sym.replace("USDT", "-USDT")
            r_okx = await self.client.get(
                "https://www.okx.com/api/v5/market/books",
                params={"instId": okx_inst, "sz": limit},
            )
            if r_okx.status_code == 200:
                okx_data = r_okx.json().get("data", [])
                if okx_data:
                    bids = okx_data[0].get("bids", [])
                    asks = okx_data[0].get("asks", [])

            # 2. Fallback to Binance /depth
            if not bids and not asks:
                url = f"{self.BINANCE_BASE}/depth"
                resp = await self.client.get(url, params={"symbol": sym, "limit": limit})
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

            res_ob = {
                "symbol": sym,
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
            self._ob_cache[sym] = {"data": res_ob, "ts": now}
            return res_ob
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
    async def prefetch_market_caps(self, symbols: Optional[List[str]] = None) -> None:
        """Batch-fetch market caps for all symbols in a SINGLE CoinGecko /coins/markets call."""
        now = time.time()
        if (now - self._batch_mcap_ts) < self._CACHE_TTL and self._mcap_cache:
            return

        target_syms = [s.upper() for s in (symbols or list(self.SYMBOL_TO_COINGECKO.keys()))]
        id_to_syms: Dict[str, List[str]] = {}
        for s in target_syms:
            cid = self.SYMBOL_TO_COINGECKO.get(s)
            if cid:
                id_to_syms.setdefault(cid, []).append(s)

        if not id_to_syms:
            return

        try:
            resp = await self.client.get(
                f"{self.COINGECKO_BASE}/coins/markets",
                params={
                    "vs_currency": "usd",
                    "ids": ",".join(id_to_syms.keys()),
                    "per_page": 250,
                    "page": 1,
                    "sparkline": "false",
                },
            )
            if resp.status_code == 200:
                items = resp.json()
                for item in items:
                    cid = item.get("id")
                    mcap_val = float(item.get("market_cap") or 0)
                    for sym in id_to_syms.get(cid, []):
                        res = {
                            "symbol": sym,
                            "market_cap_usd": mcap_val,
                            "circulating_supply": float(item.get("circulating_supply") or 0),
                            "total_supply": float(item.get("total_supply") or 0),
                            "max_supply": item.get("max_supply"),
                            "fully_diluted_valuation": float(item.get("fully_diluted_valuation") or 0),
                            "market_cap_rank": item.get("market_cap_rank") or 999,
                            "tier": self._classify_mcap_tier(mcap_val),
                        }
                        self._mcap_cache[sym] = {"data": res, "ts": now}
                self._batch_mcap_ts = now
        except Exception as e:
            logger.debug(f"CoinGecko batch market cap prefetch skipped: {e}")

    async def get_market_cap(self, symbol: str) -> Dict[str, Any]:
        """Return cached market cap or static tier classification without N+1 HTTP stalls."""
        now = time.time()
        cache_key = symbol.upper()
        if cache_key in self._mcap_cache and (now - self._mcap_cache[cache_key].get("ts", 0)) < self._CACHE_TTL:
            return self._mcap_cache[cache_key]["data"]

        # Trigger batch prefetch once if cache is cold
        if (now - self._batch_mcap_ts) >= self._CACHE_TTL:
            await self.prefetch_market_caps([cache_key])
            if cache_key in self._mcap_cache:
                return self._mcap_cache[cache_key]["data"]

        fallback = self._default_mcap(cache_key)
        self._mcap_cache[cache_key] = {"data": fallback, "ts": now}
        return fallback

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
        sym = symbol.upper()
        tier = "LARGE" if sym in self.LARGE_CAP_SYMBOLS else ("MID" if sym in self.SYMBOL_TO_COINGECKO else "SMALL")
        return {
            "symbol": sym,
            "market_cap_usd": 15_000_000_000 if tier == "LARGE" else (2_000_000_000 if tier == "MID" else 250_000_000),
            "circulating_supply": 0,
            "total_supply": 0,
            "max_supply": None,
            "fully_diluted_valuation": 0,
            "market_cap_rank": 10 if tier == "LARGE" else 50,
            "tier": tier,
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

        highs_all = df["high"].astype(float).values
        lows_all = df["low"].astype(float).values
        closes_all = df["close"].astype(float).values
        close = float(closes_all[-1])

        # Classic Pivot Points from the previous completed session window
        # (24 bars on intraday, or previous completed bar on 1d/1w) instead of
        # the entire 200-bar extremes which push R1/S1 unrealistically far away.
        n = len(df)
        tf_val = str(df.iloc[-1]["timeframe"]) if "timeframe" in df.columns else "1h"
        sess_bars = 1 if tf_val in ("1d", "1w") else min(24, max(6, n // 4))
        prev_end = max(1, n - 1)
        prev_start = max(0, prev_end - sess_bars)
        high = float(np.max(highs_all[prev_start:prev_end]))
        low = float(np.min(lows_all[prev_start:prev_end]))
        prev_close = float(closes_all[prev_end - 1])

        pivot = (high + low + prev_close) / 3.0
        s1 = 2 * pivot - high
        s2 = pivot - (high - low)
        s3 = low - 2 * (high - pivot)
        r1 = 2 * pivot - low
        r2 = pivot + (high - low)
        r3 = high + 2 * (pivot - low)

        # Estimate ATR(14) for clustering nearby swing levels
        trs = [
            max(highs_all[i] - lows_all[i], abs(highs_all[i] - closes_all[i - 1]), abs(lows_all[i] - closes_all[i - 1]))
            for i in range(1, n)
        ]
        atr = float(np.mean(trs[-14:])) if trs else close * 0.005
        cluster_tol = max(atr * 0.35, close * 0.0015)

        recent = df.tail(min(n, 120))
        swing_highs = self._find_swing_levels(recent, "high", lookback=4)
        swing_lows = self._find_swing_levels(recent, "low", lookback=4)

        def _cluster_levels(candidates: List[float], descending: bool) -> List[float]:
            if not candidates:
                return []
            pts = sorted(candidates)
            clusters: List[List[float]] = [[pts[0]]]
            for p in pts[1:]:
                if abs(p - clusters[-1][-1]) <= cluster_tol:
                    clusters[-1].append(p)
                else:
                    clusters.append([p])
            means = [round(float(sum(c) / len(c)), 8) for c in clusters]
            return sorted(means, reverse=descending)

        all_supports = _cluster_levels([s for s in [s1, s2, s3] + swing_lows if 0 < s < close], descending=True)
        all_resistances = _cluster_levels([r for r in [r1, r2, r3] + swing_highs if r > close], descending=False)

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
    # 6. Open Interest Trend (OKX)
    # -----------------------------------------------------------------
    async def get_open_interest_trend(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch Open Interest data from OKX to see if it's increasing or decreasing.
        Uses a local cache to compare previous scans.
        """
        now = time.time()
        cache_key = symbol.upper()

        if not hasattr(self, "_oi_cache"):
            self._oi_cache = {}

        try:
            base = symbol.upper().replace("USDT", "")
            instId = f"{base}-USDT-SWAP"
            url = f"https://www.okx.com/api/v5/public/open-interest"
            resp = await self.client.get(url, params={"instId": instId})
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") == "0" and data.get("data"):
                current_oi = float(data["data"][0].get("oi", 0))
                
                trend = "flat"
                change_pct = 0.0
                
                if cache_key in self._oi_cache:
                    prev_oi = self._oi_cache[cache_key]["value"]
                    if prev_oi > 0:
                        change_pct = (current_oi - prev_oi) / prev_oi * 100
                        if change_pct > 0.5:
                            trend = "increasing"
                        elif change_pct < -0.5:
                            trend = "decreasing"
                
                self._oi_cache[cache_key] = {"value": current_oi, "ts": now}
                
                return {
                    "trend": trend,
                    "value": current_oi,
                    "change_pct": round(change_pct, 2)
                }
        except Exception as e:
            logger.debug(f"Failed to fetch OI for {symbol}: {e}")
            
        return {"trend": "flat", "value": 0, "change_pct": 0}

    # -----------------------------------------------------------------
    # Combined overview for one symbol
    # -----------------------------------------------------------------
    async def get_overview(self, symbol: str, df: pd.DataFrame = None, current_price: float = 0) -> Dict[str, Any]:
        """Get combined market intelligence for one symbol."""
        btc_dom = await self.get_btc_dominance()
        orderbook = await self.get_order_book_depth(symbol)
        mcap = await self.get_market_cap(symbol)
        oi_trend = await self.get_open_interest_trend(symbol)

        liq_levels = self.calculate_liquidation_levels(current_price or orderbook.get("best_bid", 0), symbol)
        sr_levels = self.calculate_support_resistance(df, symbol) if df is not None and not df.empty else {}

        return {
            "btc_dominance": btc_dom,
            "orderbook": orderbook,
            "liquidation": liq_levels,
            "market_cap": mcap,
            "support_resistance": sr_levels,
            "open_interest": oi_trend,
        }

    async def close(self):
        await self.client.aclose()
