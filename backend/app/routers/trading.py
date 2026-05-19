"""
Trading Router — Auto-Trading Endpoints
==========================================
Execute orders, manage auto-trade config, close positions.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import logging
from app.database import get_db
from app.models.trade_setup import TradeSetup
from app.engines.trading_engine import trading_engine
from app.schemas.trading import AutoTradeConfig, OrderRequest
from app.security import require_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/trading", tags=["Trading"])


@router.get("/config")
async def get_config():
    """Get current auto-trade configuration."""
    return {"config": trading_engine.config.dict()}


@router.put("/config", dependencies=[Depends(require_api_key)])
async def update_config(cfg: AutoTradeConfig):
    """Update auto-trade configuration."""
    trading_engine.update_config(cfg)
    return {"message": "Config updated", "config": cfg.dict()}


@router.get("/status")
async def get_status():
    """Get trading engine connection status."""
    connected = trading_engine.is_connected()
    return {
        "connected": connected,
        "auto_trading_enabled": trading_engine.config.enabled,
        "dry_run": trading_engine.config.dry_run,
        "max_positions": trading_engine.config.max_positions,
        "risk_per_trade": trading_engine.config.risk_per_trade,
    }


@router.post("/execute", dependencies=[Depends(require_api_key)])
async def execute_order(req: OrderRequest):
    """Execute a manual order."""
    result = trading_engine.execute_order(req)
    return {"result": result.dict()}


@router.post("/execute/{setup_id}", dependencies=[Depends(require_api_key)])
async def execute_from_setup(setup_id: int, db: Session = Depends(get_db)):
    """Execute an order from an existing trade setup (from DB)."""
    setup = db.query(TradeSetup).filter(TradeSetup.id == setup_id).first()
    if not setup:
        return {"error": f"Setup #{setup_id} not found"}

    req = OrderRequest(
        symbol=setup.symbol,
        side=setup.direction,
        price=setup.entry_low,
        stop_loss=setup.stop_loss,
        take_profit=setup.take_profit_1,
        setup_id=setup_id,
    )

    result = trading_engine.execute_order(req)

    # Update setup status if order was placed
    if result.success:
        setup.status = "TRIGGERED"
        db.commit()

    return {"result": result.dict(), "setup_id": setup_id}


@router.post("/close/{symbol}", dependencies=[Depends(require_api_key)])
async def close_position(symbol: str):
    """Close an open position for a symbol."""
    result = trading_engine.close_position(symbol.upper())
    return {"result": result.dict()}

