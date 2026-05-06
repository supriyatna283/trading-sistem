"""News/Event Calendar API Router"""

from fastapi import APIRouter, Query
from app.engines.news_calendar import NewsCalendarEngine

router = APIRouter(prefix="/api/v1/calendar", tags=["Economic Calendar"])

calendar_engine = NewsCalendarEngine()


@router.get("")
async def get_calendar(force_refresh: bool = Query(False)):
    """Get this week's economic events."""
    events = await calendar_engine.get_events(force_refresh=force_refresh)
    next_high = calendar_engine.get_next_high_impact(events)
    return {
        "events": events,
        "total": len(events),
        "next_high_impact": next_high,
    }


@router.get("/today")
async def get_today_events():
    """Get today's economic events only."""
    events = await calendar_engine.get_events()
    today_events = calendar_engine.filter_today(events)
    return {
        "events": today_events,
        "total": len(today_events),
    }


@router.get("/high-impact")
async def get_high_impact_events():
    """Get all high-impact events this week."""
    events = await calendar_engine.get_events()
    high = calendar_engine.filter_high_impact(events)
    next_high = calendar_engine.get_next_high_impact(events)
    return {
        "events": high,
        "total": len(high),
        "next_event": next_high,
    }
