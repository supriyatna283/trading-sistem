"""WebSocket API endpoint."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.websocket_manager import ws_manager
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/market/{symbol}")
async def market_ws(websocket: WebSocket, symbol: str):
    """
    WebSocket proxy endpoint for real-time market data updates.
    Frontend connects here, we proxy via Binance WebSocket.
    """
    # Accept timeframe via query string (e.g. ?tf=1h)
    tf = websocket.query_params.get("tf", "1h")
    
    # Internal channel format: market:BTCUSDT:1h
    channel = f"market:{symbol.upper()}:{tf}"
    
    try:
        await ws_manager.connect(websocket, channel)
        logger.info(f"Client connected to market WS: {symbol} ({tf})")
        
        # Subscribe Binance proxy
        from app.services.binance_ws_client import binance_proxy
        
        await binance_proxy.subscribe(symbol, tf)
        
        while True:
            data = await websocket.receive_text()
            # Respond to ping or other commands if needed
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel)
        logger.info(f"Client disconnected from market WS: {symbol}")
    except Exception as e:
        logger.error(f"Error in market WS for {symbol}: {e}")
        ws_manager.disconnect(websocket, channel)

@router.websocket("/ws/tickers")
async def tickers_ws(websocket: WebSocket):
    """
    WebSocket proxy endpoint for real-time tickers updates.
    Frontend connects here, we proxy via Binance WebSocket.
    Accepts a 'symbols' query parameter (comma-separated).
    """
    symbols_query = websocket.query_params.get("symbols", "")
    symbols = [s.strip() for s in symbols_query.split(",") if s.strip()]
    
    channel = "tickers"
    try:
        await ws_manager.connect(websocket, channel)
        logger.info(f"Client connected to tickers WS: {len(symbols)} symbols")
        
        if symbols:
            from app.services.binance_ws_client import binance_proxy
            
            await binance_proxy.subscribe_tickers(symbols)
            
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel)
        logger.info("Client disconnected from tickers WS")
    except Exception as e:
        logger.error(f"Error in tickers WS: {e}")
        ws_manager.disconnect(websocket, channel)


@router.websocket("/ws/alerts")
async def alerts_ws(websocket: WebSocket):
    """WebSocket endpoint for real-time alert notifications."""
    await ws_manager.connect(websocket, "alerts")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "alerts")
