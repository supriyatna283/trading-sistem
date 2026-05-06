"""
WebSocket Manager
==================
Manages connected WebSocket clients and broadcasts real-time updates.
"""

from fastapi import WebSocket
from typing import Dict, Set
import json
import logging

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.all_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, channel: str = "general"):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        self.active_connections[channel].add(websocket)
        self.all_connections.add(websocket)
        logger.info(f"WebSocket connected to channel: {channel}")

    def disconnect(self, websocket: WebSocket, channel: str = "general"):
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)
        self.all_connections.discard(websocket)
        logger.info(f"WebSocket disconnected from channel: {channel}")

    async def send_to_channel(self, channel: str, data: dict):
        """Send data to all clients in a channel."""
        if channel not in self.active_connections:
            return
        disconnected = set()
        for ws in self.active_connections[channel]:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.add(ws)
        for ws in disconnected:
            self.disconnect(ws, channel)

    async def broadcast(self, data: dict):
        """Broadcast data to all connected clients."""
        disconnected = set()
        for ws in self.all_connections:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.add(ws)
        for ws in disconnected:
            self.all_connections.discard(ws)


# Global instance
ws_manager = WebSocketManager()
