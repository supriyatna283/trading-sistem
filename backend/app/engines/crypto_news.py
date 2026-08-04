"""
Crypto News & DXY Engine (V3)
==============================
Fetches:
1. Crypto-specific news from CryptoPanic free API (no key required)
2. DXY (US Dollar Index) trend from Yahoo Finance (free, no key required)
3. Combined macro summary for AI context
"""

import httpx
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Cache storage
_crypto_news_cache: Dict[str, Any] = {"data": [], "ts": 0}
_dxy_cache: Dict[str, Any] = {"data": None, "ts": 0}
_CACHE_TTL = 300  # 5 minutes


class CryptoNewsEngine:
    """
    Fetches crypto-specific news from CryptoPanic (free endpoint, no API key)
    and DXY (US Dollar Index) trend from Yahoo Finance.
    """

    # CryptoPanic free public API
    CRYPTOPANIC_URL = "https://cryptopanic.com/api/free/v1/posts/"

    # Yahoo Finance for DXY
    YAHOO_DXY_URL = "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB"

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=12.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            },
        )

    # ─────────────────────────────────────────────────────────────
    # 1. Crypto News (CryptoPanic)
    # ─────────────────────────────────────────────────────────────
    async def get_crypto_news(
        self,
        symbol: str = "BTC",
        limit: int = 10,
        force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fetch the latest crypto news from CryptoPanic.
        Returns max `limit` items sorted by date (newest first).
        Caches for 5 minutes.
        """
        global _crypto_news_cache
        now = time.time()

        cache_key = symbol.upper()
        if (
            not force_refresh
            and _crypto_news_cache.get("ts", 0)
            and (now - _crypto_news_cache["ts"]) < _CACHE_TTL
            and _crypto_news_cache.get("data")
        ):
            # Filter cached by symbol relevance
            return self._filter_by_symbol(
                _crypto_news_cache["data"], symbol, limit
            )

        try:
            # Base coin symbol (e.g. BTCUSDT → BTC)
            base_coin = symbol.upper().replace("USDT", "").replace("BUSD", "")

            # CryptoPanic free endpoint — public=true means no auth, no filter param needed
            resp = await self.client.get(
                self.CRYPTOPANIC_URL,
                params={
                    "public": "true",
                    "kind": "news",
                },
                timeout=10.0,
            )

            if resp.status_code != 200:
                logger.warning(f"CryptoPanic returned {resp.status_code} — trying fallback")
                return await self._fetch_coindesk_fallback(symbol, limit)

            raw = resp.json()
            results = raw.get("results", [])

            parsed = []
            for item in results:
                try:
                    # Currencies mentioned in the news
                    currencies = [
                        c.get("code", "") for c in item.get("currencies", [])
                    ]
                    is_relevant = (
                        base_coin in currencies
                        or "BTC" in currencies
                        or not currencies  # General market news
                    )

                    # Sentiment
                    votes = item.get("votes", {})
                    positive = votes.get("positive", 0) or 0
                    negative = votes.get("negative", 0) or 0
                    total_votes = positive + negative
                    sentiment = "NEUTRAL"
                    if total_votes > 0:
                        sentiment = (
                            "POSITIF"
                            if positive > negative * 1.5
                            else "NEGATIF"
                            if negative > positive * 1.5
                            else "NETRAL"
                        )

                    parsed.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "published_at": item.get("published_at", ""),
                        "currencies": currencies,
                        "sentiment": sentiment,
                        "is_relevant": is_relevant,
                        "source": item.get("source", {}).get("title", ""),
                    })
                except Exception as e:
                    logger.debug(f"Failed to parse news item: {e}")
                    continue

            _crypto_news_cache = {"data": parsed, "ts": now}
            logger.info(f"Fetched {len(parsed)} crypto news from CryptoPanic")

            return self._filter_by_symbol(parsed, symbol, limit)

        except Exception as e:
            logger.warning(f"CryptoPanic fetch error: {e}")
            return await self._fetch_coindesk_fallback(symbol, limit)

    def _filter_by_symbol(
        self, news: List[Dict], symbol: str, limit: int
    ) -> List[Dict]:
        """Return news relevant to the symbol first, then general news."""
        base = symbol.upper().replace("USDT", "").replace("BUSD", "")
        relevant = [n for n in news if n.get("is_relevant") and base in (n.get("currencies") or [])]
        general = [n for n in news if n not in relevant]
        combined = relevant + general
        return combined[:limit]

    def _fallback_news(self, symbol: str) -> List[Dict]:
        """Return empty list if all sources are unavailable."""
        return []

    async def _fetch_coindesk_fallback(self, symbol: str, limit: int = 5) -> List[Dict]:
        """
        Fallback: Fetch crypto news from CoinDesk RSS feed (no auth needed).
        Used when CryptoPanic is unavailable.
        """
        try:
            base_coin = symbol.upper().replace("USDT", "").replace("BUSD", "")
            resp = await self.client.get(
                "https://www.coindesk.com/arc/outboundfeeds/rss/",
                timeout=8.0,
                headers={"Accept": "application/rss+xml, application/xml, text/xml"},
            )
            if resp.status_code != 200:
                logger.warning(f"CoinDesk RSS returned {resp.status_code}")
                return []

            # Parse basic RSS XML (no external lib needed)
            content = resp.text
            items = []
            import re
            titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", content)
            # Skip channel title (first item)
            titles = titles[1:limit + 1] if len(titles) > 1 else []

            for title in titles:
                is_relevant = base_coin.lower() in title.lower() or "bitcoin" in title.lower() if base_coin == "BTC" else base_coin.lower() in title.lower()
                items.append({
                    "title": title,
                    "url": "",
                    "published_at": "",
                    "currencies": [base_coin] if is_relevant else [],
                    "sentiment": "NETRAL",
                    "is_relevant": is_relevant,
                    "source": "CoinDesk",
                })

            logger.info(f"CoinDesk RSS fallback: fetched {len(items)} items")
            return items[:limit]

        except Exception as e:
            logger.warning(f"CoinDesk RSS fallback error: {e}")
            return []

    # ─────────────────────────────────────────────────────────────
    # 2. DXY (US Dollar Index) from Yahoo Finance
    # ─────────────────────────────────────────────────────────────
    async def get_dxy(self) -> Dict[str, Any]:
        """
        Fetch DXY (US Dollar Index) current value and trend from Yahoo Finance.
        DX-Y.NYB is the DXY continuous futures ticker on Yahoo.
        Caches for 5 minutes.
        """
        global _dxy_cache
        now = time.time()

        if _dxy_cache.get("data") and (now - _dxy_cache["ts"]) < _CACHE_TTL:
            return _dxy_cache["data"]

        try:
            resp = await self.client.get(
                self.YAHOO_DXY_URL,
                params={
                    "interval": "1d",
                    "range": "5d",
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            raw = resp.json()

            chart = raw.get("chart", {})
            result = chart.get("result", [{}])[0] if chart.get("result") else {}

            meta = result.get("meta", {})
            current_price = meta.get("regularMarketPrice", 0)
            prev_close = meta.get("chartPreviousClose", current_price)

            # Calculate trend from last 5 days
            closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            closes = [c for c in closes if c is not None]

            if len(closes) >= 2:
                change_1d = closes[-1] - closes[-2]
                change_pct_1d = (change_1d / closes[-2] * 100) if closes[-2] else 0
                trend_5d = "NAIK" if closes[-1] > closes[0] else "TURUN"
            else:
                change_pct_1d = ((current_price - prev_close) / prev_close * 100) if prev_close else 0
                trend_5d = "NAIK" if change_pct_1d > 0 else "TURUN"

            change_pct_1d = round(change_pct_1d, 2)

            # Impact on crypto: DXY up = bearish for crypto, DXY down = bullish
            crypto_impact = (
                "BEARISH untuk kripto (DXY naik → risk-off)"
                if change_pct_1d > 0.2
                else "BULLISH untuk kripto (DXY turun → risk-on)"
                if change_pct_1d < -0.2
                else "NETRAL"
            )

            data = {
                "value": round(float(current_price), 2),
                "change_pct_1d": change_pct_1d,
                "trend_5d": trend_5d,
                "crypto_impact": crypto_impact,
                "source": "Yahoo Finance",
            }
            _dxy_cache = {"data": data, "ts": now}
            logger.info(f"DXY fetched: {current_price} ({change_pct_1d:+.2f}%)")
            return data

        except Exception as e:
            logger.warning(f"DXY fetch error: {e}")
            return self._fallback_dxy()

    def _fallback_dxy(self) -> Dict[str, Any]:
        return {
            "value": None,
            "change_pct_1d": None,
            "trend_5d": None,
            "crypto_impact": "Data tidak tersedia",
            "source": "unavailable",
        }

    async def close(self):
        await self.client.aclose()
