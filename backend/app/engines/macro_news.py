import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

class MacroNewsEngine:
    """
    Tracks high-impact economic news (FOMC, NFP, CPI, etc.)
    For Sprint D: Institutional Edge.
    In a real environment, this would fetch from ForexFactory or similar API.
    """

    def __init__(self):
        # We simulate a high-impact event that happens today at a specific hour
        # to demonstrate the warning capability.
        now_utc = datetime.now(timezone.utc)
        self.mock_events = [
            {
                "id": 1,
                "title": "FOMC Press Conference",
                "impact": "HIGH",
                "currency": "USD",
                "time": now_utc + timedelta(minutes=45), # 45 mins from now
            },
            {
                "id": 2,
                "title": "Core CPI m/m",
                "impact": "HIGH",
                "currency": "USD",
                "time": now_utc - timedelta(hours=2), # Past event
            }
        ]

    def get_upcoming_news(self) -> List[Dict]:
        """Returns upcoming high-impact news within the next 24 hours."""
        now_utc = datetime.now(timezone.utc)
        upcoming = []
        for e in self.mock_events:
            if e["time"] > now_utc:
                upcoming.append(e)
        return upcoming

    def check_news_proximity(self, warning_minutes: int = 60) -> dict:
        """
        Check if we are within 'warning_minutes' of a high-impact event.
        If so, returns a warning dict to freeze trading.
        """
        now_utc = datetime.now(timezone.utc)
        for e in self.mock_events:
            if e["time"] > now_utc:
                delta = (e["time"] - now_utc).total_seconds() / 60
                if delta <= warning_minutes:
                    return {
                        "is_restricted": True,
                        "event": e["title"],
                        "minutes_away": int(delta),
                        "message": f"DANGER: {e['title']} in {int(delta)} mins. Avoid entries."
                    }
        
        return {
            "is_restricted": False,
            "event": None,
            "minutes_away": None,
            "message": "No imminent high-impact news."
        }
