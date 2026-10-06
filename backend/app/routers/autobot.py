"""
AutoBot Router — REST API endpoints for the auto-trading bot.

Endpoints:
  POST /api/v1/autobot/start          — start monitor loop
  POST /api/v1/autobot/stop           — stop monitor loop (does NOT close positions)
  GET  /api/v1/autobot/status         — running state + open positions + config
  POST /api/v1/autobot/entry          — open a new futures position
  POST /api/v1/autobot/close/{symbol} — manually close a position
  POST /api/v1/autobot/config         — update TP/SL/leverage/margin
  GET  /api/v1/autobot/trades         — last 50 trade log entries
  POST /api/v1/autobot/close-all      — emergency: close all open positions
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
import logging

from ..services.autobot import get_bot, AutoBotManager

router = APIRouter(prefix="/api/v1/autobot", tags=["autobot"])
logger = logging.getLogger("autobot.router")


# ──────────────────────────────────────────────────────────────────────────────
# Request/Response schemas
# ──────────────────────────────────────────────────────────────────────────────

class EntryRequest(BaseModel):
    symbol:     str            = Field(..., example="BTCUSDT")
    direction:  str            = Field(..., example="BUY")     # "BUY" | "SELL"
    margin_usd: Optional[float] = Field(None, example=20.0)


class ConfigRequest(BaseModel):
    tp_usd:     Optional[float] = Field(None, example=10.0, description="Take-profit in USDT")
    sl_usd:     Optional[float] = Field(None, example=3.0,  description="Stop-loss in USDT")
    leverage:   Optional[int]   = Field(None, example=10,   description="Futures leverage")
    margin_usd: Optional[float] = Field(None, example=20.0, description="USDT margin per trade")
    enabled:    Optional[bool]  = Field(None, example=True,  description="Global kill-switch")
    auto_entry: Optional[bool]  = Field(None, example=True, description="Enable automated trading entries")
    min_score:  Optional[float] = Field(None, example=18.0, description="Min confluence score to trade")
    min_rr:     Optional[float] = Field(None, example=1.8, description="Min Risk/Reward ratio")
    max_positions: Optional[int] = Field(None, example=3, description="Max concurrent open positions")
    cooldown_min: Optional[int] = Field(None, example=120, description="Cooldown per symbol after exit")
    max_setup_age_h: Optional[float] = Field(None, example=6.0, description="Max age of setup in hours")
    max_daily_loss: Optional[float] = Field(None, example=10.0, description="Max allowed loss per day before pausing")
    timeframes: Optional[list[str]] = Field(None, example=["1h", "4h"], description="Allowed timeframes")


# ──────────────────────────────────────────────────────────────────────────────
# Dependency: require bot to be initialized
# ──────────────────────────────────────────────────────────────────────────────

def require_bot() -> AutoBotManager:
    bot = get_bot()
    if bot is None:
        raise HTTPException(
            status_code=503,
            detail="AutoBot not initialized. Set BINANCE_API_KEY and BINANCE_API_SECRET in environment.",
        )
    return bot


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/start")
async def start_bot(bot: AutoBotManager = Depends(require_bot)):
    """Start the AutoBot monitor loop."""
    await bot.start()
    return {"status": "started", "message": "AutoBot is now running"}


@router.post("/stop")
async def stop_bot(bot: AutoBotManager = Depends(require_bot)):
    """Stop the AutoBot monitor loop (does NOT close positions)."""
    await bot.stop()
    return {"status": "stopped", "message": "AutoBot stopped. Open positions are NOT closed."}


@router.get("/status")
async def get_status(bot: AutoBotManager = Depends(require_bot)):
    """Get current bot status, open positions, and configuration."""
    return bot.get_status()


@router.post("/entry")
async def open_entry(req: EntryRequest, bot: AutoBotManager = Depends(require_bot)):
    """
    Open a new Binance Futures position.
    
    The monitor loop will automatically:
    - Close when unrealized PnL >= tp_usd ($10)
    - Close with trailing TP when profit pulls back 30% from peak
    - Close when unrealized PnL <= -sl_usd (-$3)
    """
    if req.direction.upper() not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="direction must be 'BUY' or 'SELL'")

    result = await bot.open_position(
        symbol     = req.symbol,
        direction  = req.direction,
        margin_usd = req.margin_usd,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/close/{symbol}")
async def close_position(symbol: str, bot: AutoBotManager = Depends(require_bot)):
    """Manually close a specific open position."""
    result = await bot.close_position(symbol=symbol, reason="manual")
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/close-all")
async def close_all_positions(bot: AutoBotManager = Depends(require_bot)):
    """
    Emergency endpoint: close ALL open positions immediately.
    Use when you want to exit the market fast.
    """
    results = []
    for symbol in list(bot._positions.keys()):
        result = await bot.close_position(symbol=symbol, reason="emergency_close_all")
        results.append(result)

    return {
        "status": "all_closed",
        "closed": len(results),
        "results": results,
    }


@router.post("/config")
async def update_config(req: ConfigRequest, bot: AutoBotManager = Depends(require_bot)):
    """
    Update bot configuration on-the-fly.
    Changes take effect immediately for subsequent monitor checks and new entries.
    """
    result = await bot.update_config(
        tp_usd     = req.tp_usd,
        sl_usd     = req.sl_usd,
        leverage   = req.leverage,
        margin_usd = req.margin_usd,
        enabled    = req.enabled,
        auto_entry = req.auto_entry,
        min_score  = req.min_score,
        min_rr     = req.min_rr,
        max_positions = req.max_positions,
        cooldown_min = req.cooldown_min,
        max_setup_age_h = req.max_setup_age_h,
        max_daily_loss = req.max_daily_loss,
        timeframes = req.timeframes,
    )
    return {"status": "updated", **result}


@router.get("/trades")
async def get_trade_log(limit: int = 50, bot: AutoBotManager = Depends(require_bot)):
    """Get recent trade log (entries + exits)."""
    return {
        "count": min(limit, 200),
        "trades": bot.get_trade_log(limit=limit),
    }
