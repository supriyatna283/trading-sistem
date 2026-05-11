"""
Market Data Engine (V2 - Resilient)
====================================
Collects and processes OHLCV data from Binance REST API.
Supports multi-timeframe aggregation, normalization, and caching via Redis.
Includes SSL workaround and graceful fallback to sample data.
In-memory cache TTL 30s as fallback when Redis is not available.
"""

import httpx
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import json
import time
import logging

logger = logging.getLogger(__name__)

# In-memory cache: {key: {"df": DataFrame, "ts": float}}
_MEM_CACHE: Dict[str, dict] = {}
_MEM_CACHE_TTL = 30  # seconds

# Timeframe mapping
TIMEFRAME_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}

TIMEFRAME_MINUTES = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}

# Base prices for sample data fallback
BASE_PRICES = {
    "BTCUSDT": 67000, "ETHUSDT": 3400, "BNBUSDT": 580,
    "SOLUSDT": 145, "XRPUSDT": 0.62, "ADAUSDT": 0.45,
    "DOGEUSDT": 0.12, "AVAXUSDT": 35, "DOTUSDT": 7.5,
    "LINKUSDT": 15, "EURUSD": 1.08, "GBPUSD": 1.26,
    "USDJPY": 149.5, "XAUUSD": 2340,
}


class MarketDataEngine:
    """Fetches, normalizes, and caches market OHLCV data with resilient fallback."""

    BINANCE_BASE = "https://api.binance.com/api/v3"
    BINANCE_FUTURES_BASE = "https://fapi.binance.com/fapi/v1"
    OKX_BASE = "https://www.okx.com/api/v5"

    def __init__(self, redis_client=None):
        self.redis = redis_client
        
        # Support HTTP Proxy for regions where Binance might be blocked
        import os
        proxy_url = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
        
        # SSL verify=False + follow_redirects for environments with SSL issues
        # Reduced timeout to 5.0s for snappier fallbacks
        self.client = httpx.AsyncClient(
            timeout=5.0,
            verify=False,
            follow_redirects=True,
            proxy=proxy_url if proxy_url else None,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        self._mem_cache = _MEM_CACHE  # shared across instances
        self._symbols_cache = {"data": None, "ts": 0}

    async def fetch_symbols(self) -> List[Dict]:
        """Fetch all USDT trading pairs from OKX with caching."""
        now = time.time()
        if self._symbols_cache["data"] and (now - self._symbols_cache["ts"]) < 300:
            return self._symbols_cache["data"]

        symbols_dict = {}

        # Primary: OKX SWAP instruments (perpetual futures)
        try:
            url = f"{self.OKX_BASE}/public/instruments"
            params = {"instType": "SWAP"}
            resp = await self.client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") == "0" and data.get("data"):
                for inst in data["data"]:
                    inst_id = inst.get("instId", "")
                    # Only USDT-margined pairs
                    if inst_id.endswith("-USDT-SWAP") and inst.get("state") == "live":
                        # Convert OKX format (BTC-USDT-SWAP) to standard (BTCUSDT)
                        base = inst_id.split("-")[0]
                        symbol = f"{base}USDT"
                        symbols_dict[symbol] = {
                            "symbol": symbol,
                            "baseAsset": base,
                            "quoteAsset": "USDT",
                            "name": f"{base} / USDT",
                            "category": "crypto",
                            "exchange": "okx",
                        }
                logger.info(f"📊 OKX: Loaded {len(symbols_dict)} USDT-SWAP instruments")
        except Exception as e:
            logger.error(f"Failed to fetch OKX instruments: {e}")

        # Fallback: OKX SPOT instruments
        if not symbols_dict:
            try:
                url = f"{self.OKX_BASE}/public/instruments"
                params = {"instType": "SPOT"}
                resp = await self.client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

                if data.get("code") == "0" and data.get("data"):
                    for inst in data["data"]:
                        inst_id = inst.get("instId", "")
                        if inst_id.endswith("-USDT") and inst.get("state") == "live":
                            base = inst_id.split("-")[0]
                            symbol = f"{base}USDT"
                            symbols_dict[symbol] = {
                                "symbol": symbol,
                                "baseAsset": base,
                                "quoteAsset": "USDT",
                                "name": f"{base} / USDT",
                                "category": "crypto",
                                "exchange": "okx",
                            }
                    logger.info(f"📊 OKX SPOT fallback: Loaded {len(symbols_dict)} instruments")
            except Exception as e:
                logger.error(f"Failed to fetch OKX SPOT instruments: {e}")

        symbols = list(symbols_dict.values())
        symbols.sort(key=lambda x: x["symbol"])

        if symbols:
            self._symbols_cache = {"data": symbols, "ts": now}
            return symbols

        # Ultimate fallback: top pairs
        logger.warning("All OKX fetches failed, using static fallback list")
        return [
            {"symbol": "BTCUSDT", "name": "Bitcoin / USDT", "category": "crypto", "exchange": "okx"},
            {"symbol": "ETHUSDT", "name": "Ethereum / USDT", "category": "crypto", "exchange": "okx"},
            {"symbol": "SOLUSDT", "name": "Solana / USDT", "category": "crypto", "exchange": "okx"},
            {"symbol": "BNBUSDT", "name": "BNB / USDT", "category": "crypto", "exchange": "okx"},
            {"symbol": "XRPUSDT", "name": "XRP / USDT", "category": "crypto", "exchange": "okx"},
            {"symbol": "DOGEUSDT", "name": "DOGE / USDT", "category": "crypto", "exchange": "okx"},
            {"symbol": "ADAUSDT", "name": "ADA / USDT", "category": "crypto", "exchange": "okx"},
            {"symbol": "AVAXUSDT", "name": "AVAX / USDT", "category": "crypto", "exchange": "okx"},
            {"symbol": "DOTUSDT", "name": "DOT / USDT", "category": "crypto", "exchange": "okx"},
            {"symbol": "LINKUSDT", "name": "LINK / USDT", "category": "crypto", "exchange": "okx"},
        ]

    # ---------------------------------------------------------
    # OKX (Primary for HF)
    # ---------------------------------------------------------
    async def fetch_okx_candles(
        self, symbol: str, interval: str = "1h", limit: int = 200
    ) -> pd.DataFrame:
        """Fetch OHLCV from OKX REST API."""
        okx_interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m",
            "1h": "1H", "4h": "4H", "1d": "1D",
        }
        
        # OKX format is instId=BTC-USDT
        okx_symbol = symbol.replace("USDT", "-USDT")
        bar = okx_interval_map.get(interval, "1H")
        
        url = f"{self.OKX_BASE}/market/candles"
        params = {
            "instId": okx_symbol,
            "bar": bar,
            "limit": limit
        }
        
        try:
            resp = await self.client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") != "0" or not data.get("data"):
                logger.warning(f"OKX returned no data for {symbol}: {data}")
                return self._empty_df()
            
            # OKX returns: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
            rows = []
            for r in data["data"]:
                rows.append({
                    "open_time": int(r[0]),
                    "open": float(r[1]),
                    "high": float(r[2]),
                    "low": float(r[3]),
                    "close": float(r[4]),
                    "volume": float(r[5]),
                })
            
            df = pd.DataFrame(rows)
            df = self._normalize(df, symbol, interval)
            # OKX returns newest first, so sort chronologically
            df = df.sort_values("open_time").reset_index(drop=True)
            await self._cache(symbol, interval, df)
            return df
        except Exception as e:
            logger.error(f"OKX fetch error for {symbol} ({interval}): {e}")
            return self._empty_df()

    async def close(self):
        await self.client.aclose()

    # ---------------------------------------------------------
    # Binance (Primary)
    # ---------------------------------------------------------
    async def fetch_binance_candles(
        self, symbol: str, interval: str = "1h", limit: int = 200
    ) -> pd.DataFrame:
        """Fetch OHLCV from Binance REST API (supports up to 1000 per request)."""
        binance_interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m",
            "1h": "1h", "4h": "4h", "1d": "1d",
        }
        
        bi = binance_interval_map.get(interval, "1h")
        
        async def _fetch(baseUrl: str):
            all_data = []
            remaining = limit
            end_time = None
            url = f"{baseUrl}/klines"
            
            while remaining > 0:
                batch_size = min(remaining, 1000)
                params = {
                    "symbol": symbol.upper(),
                    "interval": bi,
                    "limit": batch_size,
                }
                if end_time:
                    params["endTime"] = end_time
                
                resp = await self.client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                
                if not data:
                    break
                
                all_data.extend(data)
                remaining -= len(data)
                end_time = int(data[0][0]) - 1
                
                if len(data) < batch_size:
                    break
            return all_data

        try:
            try:
                all_data = await _fetch(self.BINANCE_BASE)
            except httpx.HTTPStatusError as e:
                # Fallback to futures if bad request (not listed on spot)
                if e.response.status_code == 400:
                    all_data = await _fetch(self.BINANCE_FUTURES_BASE)
                else:
                    raise e
            
            if not all_data:
                logger.warning(f"Binance returned no data for {symbol}")
                return self._empty_df()
            
            # Binance returns: [open_time, o, h, l, c, vol, close_time, quote_vol, trades, ...]
            rows = []
            for r in all_data:
                try:
                    rows.append({
                        "open_time": int(r[0]),
                        "open": r[1],
                        "high": r[2],
                        "low": r[3],
                        "close": r[4],
                        "volume": r[5],
                    })
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse Binance candle row {r}: {e}")
                    continue
            
            df = pd.DataFrame(rows)
            df = self._normalize(df, symbol, interval)
            df = df.sort_values("open_time").reset_index(drop=True)
            await self._cache(symbol, interval, df)
            return df
        except httpx.HTTPStatusError as e:
            logger.error(f"Binance HTTP error for {symbol} ({interval}): {e.response.status_code} - {e.response.text}")
            return self._empty_df()
        except Exception as e:
            logger.exception(f"Binance fetch error for {symbol} ({interval}): {e}")
            return self._empty_df()



    async def fetch_historical_candles(
        self, symbol: str, interval: str, start_ts: int, end_ts: int
    ) -> pd.DataFrame:
        """
        Fetch a large historical range for backtesting from Binance.
        start_ts and end_ts must be in milliseconds.
        Binance paginates forward in time.
        """
        binance_interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m",
            "1h": "1h", "4h": "4h", "1d": "1d",
        }

        bi = binance_interval_map.get(interval, "1h")

        async def _fetch_historical(baseUrl: str):
            all_data = []
            current_start = start_ts
            url = f"{baseUrl}/klines"
            
            while current_start < end_ts:
                params = {
                    "symbol": symbol.upper(),
                    "interval": bi,
                    "limit": 1000,
                    "startTime": current_start,
                    "endTime": end_ts,
                }
                
                resp = await self.client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

                if not data:
                    break

                all_data.extend(data)
                
                if len(data) < 1000:
                    break
                    
                current_start = int(data[-1][0]) + 1
            return all_data

        try:
            try:
                all_data = await _fetch_historical(self.BINANCE_BASE)
            except httpx.HTTPStatusError as e:
                # Fallback to futures if bad request
                if e.response.status_code == 400:
                    all_data = await _fetch_historical(self.BINANCE_FUTURES_BASE)
                else:
                    raise e

            if not all_data:
                return self._empty_df()

            rows = []
            for r in all_data:
                try:
                    rows.append({
                        "open_time": int(r[0]),
                        "open": r[1],
                        "high": r[2],
                        "low": r[3],
                        "close": r[4],
                        "volume": r[5],
                    })
                except Exception:
                    continue

            df = pd.DataFrame(rows)
            df = self._normalize(df, symbol, interval)
            # Sort chronologically
            df = df.sort_values("open_time").reset_index(drop=True)
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch historical Binance data for {symbol}: {e}")
            return self._empty_df()

    # ---------------------------------------------------------
    # Resilient fetch (Binance → Sample Data fallback)
    # ---------------------------------------------------------
    async def get_candles(
        self, symbol: str, timeframe: str = "1h", limit: int = 200
    ) -> pd.DataFrame:
        """Main entry point — fetches candles with caching + fallback."""
        # 1. Check cache
        cached = await self._get_cache(symbol, timeframe)
        if cached is not None and len(cached) >= limit:
            return cached.tail(limit).reset_index(drop=True)

        # 2. Try OKX (Primary for HF)
        df = await self.fetch_okx_candles(symbol, timeframe, limit)
        
        # 3. Try Binance (Secondary Fallback)
        if df.empty:
            df = await self.fetch_binance_candles(symbol, timeframe, limit)

        # 4. Final fallback to sample data
        if df.empty:
            logger.warning(f"All data sources failed for {symbol}, using sample data")
            base = BASE_PRICES.get(symbol.upper(), 100)
            df = self.generate_sample_data(
                symbol=symbol.upper(), timeframe=timeframe, 
                periods=limit, base_price=base,
            )

        return df

    # ---------------------------------------------------------
    # Generate sample / demo data
    # ---------------------------------------------------------
    @staticmethod
    def generate_sample_data(
        symbol: str = "BTCUSDT",
        timeframe: str = "1h",
        periods: int = 200,
        base_price: float = 67000.0,
    ) -> pd.DataFrame:
        """Generate realistic sample OHLCV data for demo/testing."""
        np.random.seed(hash(symbol + timeframe) % 2**31)
        
        freq_map = {
            "1m": "1min", "5m": "5min", "15m": "15min",
            "1h": "1h", "4h": "4h", "1d": "1D",
        }
        freq = freq_map.get(timeframe, "1h")
        
        timestamps = pd.date_range(
            end=datetime.utcnow(), periods=periods, freq=freq
        )
        
        price = base_price
        rows = []
        for ts in timestamps:
            # Use trending random walk for more realistic structure
            change = np.random.normal(0, 0.003) * price
            o = price
            h = o + abs(np.random.normal(0, 0.002) * price)
            l = o - abs(np.random.normal(0, 0.002) * price)
            c = o + change
            h = max(h, o, c)
            l = min(l, o, c)
            vol = abs(np.random.normal(1000, 300))
            rows.append({
                "symbol": symbol,
                "timeframe": timeframe,
                "open_time": ts,
                "open": round(o, 8),
                "high": round(h, 8),
                "low": round(l, 8),
                "close": round(c, 8),
                "volume": round(vol, 2),
            })
            price = c
        return pd.DataFrame(rows)

    # ---------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------
    def _normalize(self, df: pd.DataFrame, symbol: str, timeframe: str) -> pd.DataFrame:
        """Normalize raw exchange data into standard format."""
        df["open_time"] = pd.to_datetime(df["open_time"].astype(float), unit="ms")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        df["symbol"] = symbol.upper()
        df["timeframe"] = timeframe
        return df[["symbol", "timeframe", "open_time", "open", "high", "low", "close", "volume"]].copy()

    def _empty_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            columns=["symbol", "timeframe", "open_time", "open", "high", "low", "close", "volume"]
        )

    async def _cache(self, symbol: str, timeframe: str, df: pd.DataFrame):
        """Cache candle data in Redis (primary) or in-memory (fallback)."""
        key = f"candles:{symbol}:{timeframe}"
        # Always store in memory cache
        self._mem_cache[key] = {"df": df.copy(), "ts": time.time()}
        if self.redis is None:
            return
        try:
            data = df.to_json(orient="records", date_format="iso")
            self.redis.setex(key, 300, data)  # 5 min TTL in Redis
        except Exception as e:
            logger.warning(f"Redis cache write failed: {e}")

    async def _get_cache(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Read cached candle data from Redis (primary) or in-memory (fallback)."""
        key = f"candles:{symbol}:{timeframe}"
        # Try Redis first
        if self.redis is not None:
            try:
                raw = self.redis.get(key)
                if raw:
                    return pd.read_json(raw, orient="records")
            except Exception as e:
                logger.warning(f"Redis cache read failed: {e}")
        # Fallback: in-memory cache with TTL
        entry = self._mem_cache.get(key)
        if entry and (time.time() - entry["ts"]) < _MEM_CACHE_TTL:
            logger.info(f"In-memory cache hit for {key}")
            return entry["df"].copy()
        return None
