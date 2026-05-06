"""News/Event Calendar Engine
================================
Fetches economic events from the free Forex Factory calendar JSON feed.
Caches results for 60 minutes to avoid hammering the API.
"""

import httpx
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Free public calendar (no API key required)
FF_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# Currencies relevant to crypto (macro drivers)
RELEVANT_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CNY", "AUD", "CAD"}

# Cache: (data, timestamp)
_cache: Optional[tuple] = None
_CACHE_TTL_SECONDS = 3600  # 1 hour


class NewsCalendarEngine:
    """Fetches and filters economic calendar events."""

    async def get_events(self, force_refresh: bool = False) -> List[Dict]:
        """Return this week's economic events, fetched from FF calendar."""
        global _cache

        now = datetime.now(timezone.utc).timestamp()

        # Return cache if valid
        if not force_refresh and _cache is not None:
            data, cached_at = _cache
            if now - cached_at < _CACHE_TTL_SECONDS:
                return data

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(FF_CALENDAR_URL, headers={
                    "User-Agent": "TradingPlatform/1.0"
                })
                resp.raise_for_status()
                raw = resp.json()

            events = self._parse_events(raw)
            _cache = (events, now)
            logger.info(f"Fetched {len(events)} calendar events from Forex Factory")
            return events

        except Exception as e:
            logger.error(f"Calendar fetch error: {e}")
            # Return cached data even if stale
            if _cache:
                return _cache[0]
            return []

    def _parse_events(self, raw: list) -> List[Dict]:
        """Parse and enrich raw Forex Factory event data."""
        events = []
        for item in raw:
            try:
                currency = item.get("country", "").upper()
                impact = item.get("impact", "Low")
                title = item.get("title", "")
                date_str = item.get("date", "")

                # Parse time
                event_time = None
                time_str = None
                if date_str:
                    try:
                        # FF format: "2024-01-15T08:30:00-05:00"
                        event_time = datetime.fromisoformat(date_str)
                        time_str = event_time.strftime("%Y-%m-%d %H:%M UTC")
                    except Exception:
                        time_str = date_str

                events.append({
                    "id": f"{date_str}_{currency}_{title[:20]}".replace(" ", "_"),
                    "title": title,
                    "currency": currency,
                    "impact": impact,
                    "impact_level": self._impact_level(impact),
                    "date": date_str,
                    "time_formatted": time_str,
                    "forecast": item.get("forecast", ""),
                    "previous": item.get("previous", ""),
                    "actual": item.get("actual", ""),
                    "relevant_to_crypto": currency in RELEVANT_CURRENCIES,
                    "description": item.get("description", ""),
                })
            except Exception as e:
                logger.warning(f"Failed to parse event: {e}")
                continue

        # Sort by date
        events.sort(key=lambda x: x.get("date", ""))
        return events

    def _impact_level(self, impact: str) -> int:
        """Convert impact string to numeric level: 3=High, 2=Medium, 1=Low"""
        mapping = {"High": 3, "Medium": 2, "Low": 1, "Holiday": 0}
        return mapping.get(impact, 1)

    def filter_today(self, events: List[Dict]) -> List[Dict]:
        """Filter events to today only (UTC)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return [e for e in events if e.get("date", "").startswith(today)]

    def filter_high_impact(self, events: List[Dict]) -> List[Dict]:
        """Filter to High-impact events only."""
        return [e for e in events if e.get("impact_level", 0) >= 3]

    def get_next_high_impact(self, events: List[Dict]) -> Optional[Dict]:
        """Get the next upcoming high-impact event."""
        now = datetime.now(timezone.utc)
        for event in self.filter_high_impact(events):
            try:
                event_dt = datetime.fromisoformat(event["date"])
                if event_dt.tzinfo is None:
                    event_dt = event_dt.replace(tzinfo=timezone.utc)
                if event_dt > now:
                    # Add countdown in seconds
                    result = dict(event)
                    result["seconds_until"] = int((event_dt - now).total_seconds())
                    return result
            except Exception:
                continue
        return None
