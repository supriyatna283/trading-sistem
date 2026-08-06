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
        last_sent_state = {}
        
        while True:
            if await request.is_disconnected():
                break
                
            updates = []
            
            # If specific symbols requested, only track those. Otherwise track all in memory (which is top 100 via snapshot typically).
            target_symbols = symbol_list if symbol_list else list(_in_memory_ticker_state.keys())
            
            for sym in target_symbols:
                current_state = _in_memory_ticker_state.get(sym)
                if not current_state:
                    continue
                    
                # Check if state changed since last sent
                last_state = last_sent_state.get(sym)
                if not last_state or last_state["timestamp"] < current_state["timestamp"]:
                    updates.append({
                        "symbol": sym,
                        "price": current_state["price"],
                        "change_24h": current_state["change_24h"],
                        "volume_24h": current_state["volume_24h"]
                    })
                    last_sent_state[sym] = current_state.copy()
            
            if updates:
                yield f"data: {json.dumps(updates)}\n\n"
                
            await asyncio.sleep(1.0) # Throttle updates to 1 per second to save browser CPU

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Access-Control-Allow-Origin": "*",
    }
    return StreamingResponse(event_generator(), headers=headers)
