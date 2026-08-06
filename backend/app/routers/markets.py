import asyncio
import json
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse
from app.engines.live_market import live_market_engine, _in_memory_ticker_state

router = APIRouter(prefix="/api/v1/markets", tags=["Markets"])

@router.get("/snapshot")
async def get_markets_snapshot(limit: int = Query(100, description="Number of top coins to fetch")):
    """Returns the initial snapshot of top coins by Market Cap with live Binance prices."""
    data = await live_market_engine.get_snapshot(limit=limit)
    return {"status": "success", "data": data}

@router.get("/sparklines")
async def get_sparklines(symbols: str = Query(..., description="Comma separated symbols, e.g. BTCUSDT,ETHUSDT")):
    """Returns 7d sparkline data for the requested symbols."""
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    data = await live_market_engine.get_sparklines(symbol_list)
    return {"status": "success", "data": data}

@router.get("/stream")
async def stream_live_markets(request: Request, symbols: str = Query("", description="Comma separated symbols to stream")):
    """
    Server-Sent Events (SSE) endpoint to stream live price updates.
    Sends an update every 1 second containing only coins whose price/change has updated.
    """
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    
    async def event_generator():
        q = live_market_engine.subscribe()
        try:
            # Send initial status immediately so frontend knows we're alive or degraded
            yield f"data: {json.dumps({'status': live_market_engine.status, 'updates': []})}\n\n"
            
            while True:
                if await request.is_disconnected():
                    break
                    
                try:
                    # Wait for next payload from queue, timeout every 2 seconds to check disconnect
                    payload = await asyncio.wait_for(q.get(), timeout=2.0)
                    if payload is None: # Sentinel for shutdown
                        break
                        
                    # Filter updates if specific symbols requested
                    if symbol_list:
                        payload["updates"] = [u for u in payload.get("updates", []) if u["symbol"] in symbol_list]
                        
                    yield f"data: {json.dumps(payload)}\n\n"
                    
                except asyncio.TimeoutError:
                    continue
        finally:
            live_market_engine.unsubscribe(q)

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Access-Control-Allow-Origin": "*",
    }
    return StreamingResponse(event_generator(), headers=headers)
