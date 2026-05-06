"""
Order Flow Router — Footprint & Smart Tape Endpoints
=====================================================
REST endpoints for footprint data and whale detection.
WebSocket endpoint for real-time Smart Tape feed.
"""

import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.engines.order_flow_engine import order_flow_engine, WHALE_THRESHOLD_USDT, FISH_THRESHOLD_USDT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/orderflow", tags=["Order Flow"])


# ─── Footprint ───

@router.get("/footprint/{symbol}")
async def get_footprint(
    symbol: str,
    timeframe: str = Query("5m", description="Candle timeframe"),
    limit: int = Query(10, description="Number of candles", ge=1, le=50),
):
    """
    Get footprint candles for a symbol: buy/sell volume per price level,
    delta, Point of Control (POC), and cumulative delta.
    """
    candles = await order_flow_engine.get_footprint(symbol.upper(), timeframe, limit)
    flow_summary = {}
    if candles:
        all_deltas = [c["delta"] for c in candles]
        total_buy = sum(c["total_buy_vol"] for c in candles)
        total_sell = sum(c["total_sell_vol"] for c in candles)
        flow_summary = {
            "cumulative_delta": round(sum(all_deltas), 4),
            "total_buy_vol": round(total_buy, 4),
            "total_sell_vol": round(total_sell, 4),
            "dominance": "BUY" if total_buy > total_sell else "SELL",
        }
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "candles": candles,
        "flow_summary": flow_summary,
    }


# ─── Whale / Smart Tape ───

@router.get("/whales/{symbol}")
async def get_whales(
    symbol: str,
    threshold_usdt: float = Query(WHALE_THRESHOLD_USDT, description="Minimum notional value in USDT"),
    limit: int = Query(50, ge=1, le=200),
    lookback_seconds: int = Query(3600, description="Lookback window in seconds"),
):
    """
    Fetch large trades (whale detection) for a single symbol.
    Returns sorted by notional value descending.
    """
    trades = await order_flow_engine.get_recent_whales(
        symbol.upper(), threshold_usdt, limit, lookback_seconds
    )
    summary = order_flow_engine.get_flow_summary(trades)
    return {
        "symbol": symbol.upper(),
        "threshold_usdt": threshold_usdt,
        "lookback_seconds": lookback_seconds,
        "trades": trades,
        "summary": summary,
        "whale_count": len([t for t in trades if t["tier"] == "WHALE"]),
        "shark_count": len([t for t in trades if t["tier"] == "SHARK"]),
    }


@router.get("/whales/scan/multi")
async def scan_multi_symbols(
    symbols: str = Query("BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT"),
    threshold_usdt: float = Query(WHALE_THRESHOLD_USDT),
    lookback_seconds: int = Query(300),
):
    """
    Scan multiple symbols for whale trades concurrently (default: last 5 minutes).
    """
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()][:20]
    trades = await order_flow_engine.get_multi_symbol_whales(sym_list, threshold_usdt, lookback_seconds)
    summary = order_flow_engine.get_flow_summary(trades)
    return {
        "symbols": sym_list,
        "threshold_usdt": threshold_usdt,
        "lookback_seconds": lookback_seconds,
        "trades": trades,
        "summary": summary,
    }


@router.get("/whales/live/cached")
async def get_cached_whales(symbol: Optional[str] = Query(None)):
    """
    Get cached whale trades collected from the real-time WebSocket stream.
    Optionally filter by symbol.
    """
    trades = order_flow_engine.get_cached_whales(symbol.upper() if symbol else None)
    summary = order_flow_engine.get_flow_summary(trades)
    return {"trades": trades, "summary": summary, "count": len(trades)}


# ─── Real-time WebSocket ───

@router.websocket("/ws/tape")
async def tape_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time Smart Tape feed.
    Streams whale/large trades as they occur across all monitored symbols.
    Connect at: ws://127.0.0.1:8000/api/v1/orderflow/ws/tape
    """
    from app.services.tape_ws_manager import smart_tape_manager
    await websocket.accept()
    logger.info("📡 Smart Tape WebSocket client connected")

    # Send initial cached trades
    cached = order_flow_engine.get_cached_whales()
    if cached:
        import json
        await websocket.send_text(json.dumps({"type": "initial", "data": cached}))

    try:
        await smart_tape_manager.connect_client(websocket)
    except WebSocketDisconnect:
        logger.info("📴 Smart Tape WebSocket client disconnected")
    except Exception as e:
        logger.warning(f"Tape WS error: {e}")
