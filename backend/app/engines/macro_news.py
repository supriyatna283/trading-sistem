import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

from app.engines.news_calendar import NewsCalendarEngine, _cache as _ff_cache


class MacroNewsEngine:
    """
    Tracks real high-impact economic news (FOMC, NFP, CPI, etc.)
    backed by NewsCalendarEngine (Forex Factory live calendar feed).
    Never fabricates fake FOMC events.
    """

    def __init__(self):
        self._calendar = NewsCalendarEngine()

    def _extract_high_impact_usd(self, raw_events: List[Dict]) -> List[Dict]:
        now_utc = datetime.now(timezone.utc)
        parsed: List[Dict] = []
        for ev in raw_events or []:
            try:
                if ev.get("impact_level", 0) < 3 and str(ev.get("impact", "")).upper() != "HIGH":
                    continue
                currency = str(ev.get("currency", "USD")).upper()
                if currency not in ("USD", "ALL"):
                    continue
                date_str = ev.get("date")
                if not date_str:
                    continue
                dt = datetime.fromisoformat(str(date_str))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                if dt > now_utc - timedelta(minutes=15):
                    parsed.append({
                        "id": ev.get("id", date_str),
                        "title": ev.get("title", "High-Impact USD Event"),
                        "impact": "HIGH",
                        "currency": currency,
                        "time": dt,
                    })
            except Exception:
                continue
        parsed.sort(key=lambda x: x["time"])
        return parsed

    def get_upcoming_news(self, events: Optional[List[Dict]] = None) -> List[Dict]:
        """Returns upcoming high-impact USD news within the next 24 hours."""
        if events is None:
            from app.engines import news_calendar
            events = news_calendar._cache[0] if news_calendar._cache else []
        now_utc = datetime.now(timezone.utc)
        cutoff = now_utc + timedelta(hours=24)
        return [
            e for e in self._extract_high_impact_usd(events)
            if now_utc <= e["time"] <= cutoff
        ]

    async def check_news_proximity_async(self, warning_minutes: int = 60) -> dict:
        """Async version that ensures the live economic calendar cache is populated."""
        try:
            events = await self._calendar.get_events()
        except Exception as e:
            logger.warning(f"MacroNewsEngine calendar fetch error: {e}")
            events = []
        return self.check_news_proximity(warning_minutes=warning_minutes, events=events)

    def check_news_proximity(self, warning_minutes: int = 60, events: Optional[List[Dict]] = None) -> dict:
        """
        Check if we are within 'warning_minutes' of a real high-impact USD event.
        If so, returns a warning dict to restrict trading.
        """
        if events is None:
            from app.engines import news_calendar
            events = news_calendar._cache[0] if news_calendar._cache else []

        now_utc = datetime.now(timezone.utc)
        for e in self._extract_high_impact_usd(events):
            delta = (e["time"] - now_utc).total_seconds() / 60.0
            if -10 <= delta <= warning_minutes:
                mins = max(0, int(round(delta)))
                return {
                    "is_restricted": True,
                    "event": e["title"],
                    "minutes_away": mins,
                    "message": f"DANGER: {e['title']} in {mins} mins. Avoid entries.",
                }

        return {
            "is_restricted": False,
            "event": None,
            "minutes_away": None,
            "message": "No imminent high-impact news.",
        }
