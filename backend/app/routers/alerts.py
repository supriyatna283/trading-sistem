"""
WhatsApp Alert Router
=====================
Endpoints for configuring and testing WhatsApp trading alerts.
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.engines.alert_engine import ICTAlertEngine, AlertConfig, AlertType
from app.services.whatsapp_service import WhatsAppService, WAMessage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/alerts", tags=["WhatsApp Alerts"])

# Singletons
_alert_engine = ICTAlertEngine()
_wa_service   = WhatsAppService()

# In-memory config store (replace with DB in production)
_configs: dict[str, AlertConfig] = {}


# ─── Request / Response models ─────────────────────────────────────────────────

class AlertConfigRequest(BaseModel):
    phone:             str
    enabled:           bool = True
    killzone_start:    bool = True
    fvg_hit:           bool = True
    sweep_confirmed:   bool = True
    composite_score:   bool = True
    volume_spike:      bool = False
    daily_brief:       bool = True
    min_score:         int  = 70
    min_grade:         str  = "A"
    symbols:           List[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    only_killzone:     bool = True
    cooldown_hours:    int  = 4
    max_per_hour:      int  = 3


class ManualAlertRequest(BaseModel):
    phone:      str
    alert_type: AlertType = AlertType.TEST
    symbol:     str       = "BTCUSDT"
    timeframe:  str       = "1h"
    score:      int       = 85
    grade:      str       = "A+"
    entry:      Optional[float] = None
    sl:         Optional[float] = None
    tp1:        Optional[float] = None
    tp2:        Optional[float] = None
    rr:         Optional[float] = None
    extra:      dict      = {}


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/config/{phone}")
async def get_config(phone: str):
    cfg = _configs.get(phone)
    if not cfg:
        return {"found": False, "message": "No config found for this number."}
    return {"found": True, "config": cfg.__dict__}


@router.post("/config")
async def save_config(req: AlertConfigRequest):
    cfg = AlertConfig(**req.dict())
    _configs[req.phone] = cfg
    return {"ok": True, "message": "Alert config saved.", "config": cfg.__dict__}


@router.post("/test")
async def send_test_alert(phone: str = Query(..., description="Phone e.g. 628123456789")):
    """Send a test WhatsApp message to verify connection."""
    dummy_cfg = AlertConfig(
        phone=phone, enabled=True, only_killzone=False,
        min_score=0, min_grade="C", cooldown_hours=0, max_per_hour=999,
        symbols=[],  # empty = no symbol filter
    )
    data = {"score": 85, "grade": "A+", "min_score": 70, "min_grade": "A", "cooldown_hours": 4, "max_per_hour": 3}
    alert = _alert_engine.generate_alert(AlertType.TEST, "TEST", dummy_cfg, data)
    if not alert:
        # Fallback: build message directly and send without going through engine filters
        from app.engines.alert_engine import TradeAlert
        test_msg = (
            f"\u2705 *TEST ALERT \u2014 TradingSistem WA Aktif!*\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"\U0001f389 Koneksi WhatsApp berhasil!\n\n"
            f"\U0001f4f1 *Alert yang aktif:*\n"
            f"  \u2022 \U0001f3af ICT Setup A/A+ grade\n"
            f"  \u2022 \u2b1c FVG hit alert (CE level)\n"
            f"  \u2022 \U0001f30a Liquidity sweep confirmed\n"
            f"  \u2022 \U0001f5fd Killzone start reminder\n"
            f"  \u2022 \U0001f305 Daily brief (London open)\n\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"_TradingSistem \u00b7 ICT Methodology_"
        )
        result = await _wa_service.send(WAMessage(to=phone, text=test_msg))
        return {"ok": result["ok"], "detail": result.get("detail"), "preview": test_msg}

    result = await _wa_service.send(WAMessage(to=phone, text=alert.message))
    return {"ok": result["ok"], "detail": result.get("detail"), "preview": alert.message}


@router.post("/send")
async def send_manual_alert(req: ManualAlertRequest):
    """Manually trigger a specific alert type (bypasses filters)."""
    dummy_cfg = AlertConfig(
        phone=req.phone, enabled=True, only_killzone=False,
        min_score=0, min_grade="C", cooldown_hours=0, max_per_hour=999,
        symbols=[],  # empty = no symbol filter
    )
    data = {
        "score": req.score, "grade": req.grade,
        "entry": req.entry, "sl": req.sl,
        "tp1": req.tp1, "tp2": req.tp2, "rr": req.rr,
        "timeframe": req.timeframe,
        **req.extra,
    }
    alert = _alert_engine.generate_alert(req.alert_type, req.symbol, dummy_cfg, data)
    if not alert:
        return {"ok": False, "detail": "Alert suppressed"}

    result = await _wa_service.send(WAMessage(to=req.phone, text=alert.message))
    return {"ok": result["ok"], "alert_type": req.alert_type, "preview": alert.message, "detail": result.get("detail")}


@router.get("/preview/{alert_type}")
async def preview_alert(
    alert_type: AlertType,
    symbol:  str            = Query("BTCUSDT"),
    score:   int            = Query(85),
    grade:   str            = Query("A+"),
    entry:   Optional[float]= Query(None),
    sl:      Optional[float]= Query(None),
    tp1:     Optional[float]= Query(None),
    tp2:     Optional[float]= Query(None),
    rr:      Optional[float]= Query(None),
):
    """Preview what a WhatsApp message will look like (no actual send)."""
    dummy_cfg = AlertConfig(
        phone="preview", enabled=True, only_killzone=False,
        min_score=0, min_grade="C", cooldown_hours=0, max_per_hour=999,
        symbols=[symbol],
    )
    data = {
        "score": score, "grade": grade,
        "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2, "rr": rr,
        "fvg_type": "Bullish", "fvg_high": (entry or 67000)*1.003, "fvg_low": entry or 67000,
        "ce_level": (entry or 67000)*1.0015,
        "fill_pct": 25, "in_discount": True, "fvg_fresh": True, "ob_active": True,
        "sweep_confirmed": True, "entry_bias": "STRONG BUY",
        "sweep_type": "Equal Lows", "displacement": True,
        "top_pairs": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT"],
        "min_score": 70, "min_grade": "A", "cooldown_hours": 4, "max_per_hour": 3,
    }
    alert = _alert_engine.generate_alert(alert_type, symbol, dummy_cfg, data)
    if not alert:
        return {"ok": False, "preview": "Alert suppressed by engine"}
    return {"ok": True, "alert_type": alert_type, "symbol": symbol, "preview": alert.message}

@router.post("/test-broadcast")
async def test_broadcast(
    symbol: str = Query("BTCUSDT"),
    score: float = Query(26.0, description="Score out of 30. e.g. 26 = A+"),
    direction: str = Query("LONG")
):
    """Simulate auto_scheduler generating a setup to test the broadcast filters (grade, killzone)."""
    class MockSetup:
        pass
    
    setup = MockSetup()
    setup.symbol = symbol
    setup.direction = direction
    setup.entry_low = 65000
    setup.entry_high = 65200
    setup.stop_loss = 64500
    setup.take_profit_1 = 66000
    setup.take_profit_2 = 67000
    setup.take_profit_3 = 68000
    setup.risk_reward = 2.5
    setup.confluence_score = score
    setup.confluence_details = {
        "smc": {"fvgs": [{"type": "bullish"}], "liquidity_sweeps": True},
        "structure": {"in_discount": True}
    }
    
    log_result = await broadcast_setup_alert(setup, "1h")
    return {
        "ok": True, 
        "message": f"Broadcast triggered for {symbol}.", 
        "broadcast_log": log_result
    }

@router.get("/status")
async def alert_status():
    return {
        "wa_configured":    _wa_service.enabled,
        "wa_provider":      _wa_service.provider,
        "registered_phones": list(_configs.keys()),
        "total_configs":    len(_configs),
    }


# ─── Internal Broadcast API ────────────────────────────────────────────────────
import os
from app.services.signal_state_manager import signal_state_manager

# Pre-seed owner config if available
_owner_phone = os.getenv("WA_OWNER_PHONE")
if _owner_phone:
    _configs[_owner_phone] = AlertConfig(
        phone=_owner_phone, enabled=True, only_killzone=True,
        min_score=70, min_grade="A", cooldown_hours=4, max_per_hour=5,
        symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
    )

async def broadcast_setup_alert(setup_schema, timeframe: str):
    """Called internally by auto_scheduler. Includes fingerprint-based dedup."""
    if not _configs:
        logger.warning("No WA configs available for broadcast.")
        return []

    score_scaled = int((setup_schema.confluence_score / 30.0) * 100)
    if score_scaled >= 85: grade = "A+"
    elif score_scaled >= 75: grade = "A"
    elif score_scaled >= 60: grade = "B"
    else: grade = "C"

    # ── Fingerprint check (real-time dedup) ──────────────────────────────────
    allowed, reason = signal_state_manager.can_broadcast(
        setup_schema.symbol,
        setup_schema.direction,
        setup_schema.entry_low,
        getattr(setup_schema, "entry_high", setup_schema.entry_low * 1.001),
        timeframe,
    )
    if not allowed:
        logger.info(f"Signal blocked by state manager: {setup_schema.symbol} — {reason}")
        return [{"phone": "ALL", "status": "blocked_by_state_manager", "reason": reason}]

    bias = "STRONG BUY" if setup_schema.direction.upper() == "LONG" else "STRONG SELL" if setup_schema.direction.upper() == "SHORT" else "NEUTRAL"
    data = {
        "score": score_scaled, "grade": grade, "entry_bias": bias,
        "entry": setup_schema.entry_low, "sl": setup_schema.stop_loss,
        "tp1": setup_schema.take_profit_1, "tp2": setup_schema.take_profit_2,
        "rr": setup_schema.risk_reward, "timeframe": timeframe,
    }
    try:
        data["fvg_fresh"]       = bool(setup_schema.confluence_details.get("smc", {}).get("fvgs", []))
        data["sweep_confirmed"] = bool(setup_schema.confluence_details.get("smc", {}).get("liquidity_sweeps", []))
        data["in_discount"]     = bool(setup_schema.confluence_details.get("structure", {}).get("in_discount", False))
    except:
        pass

    logger.info(f"Broadcasting WA: {setup_schema.symbol} [{timeframe}] score={score_scaled} grade={grade}")

    results = []
    wa_sent = False
    for phone, config in _configs.items():
        if not config.enabled:
            results.append({"phone": phone, "status": "skipped_disabled"})
            continue
        alert = _alert_engine.generate_alert(AlertType.COMPOSITE_SCORE, setup_schema.symbol, config, data)
        if alert:
            res = await _wa_service.send(WAMessage(to=phone, text=alert.message))
            wa_sent = True
            logger.info(f"WA send to {phone}: ok={res.get('ok')} | {res.get('detail','')}")
            results.append({"phone": phone, "status": "sent", "wa_ok": res.get("ok"), "wa_detail": res.get("detail")})
        else:
            results.append({"phone": phone, "status": "suppressed_by_ict_filters"})

    # ── Register into state manager only if at least 1 WA actually sent ──────
    if wa_sent:
        signal_state_manager.register_signal(
            symbol=setup_schema.symbol,
            direction=setup_schema.direction,
            entry_low=setup_schema.entry_low,
            entry_high=getattr(setup_schema, "entry_high", setup_schema.entry_low * 1.001),
            stop_loss=setup_schema.stop_loss,
            take_profit_1=setup_schema.take_profit_1,
            take_profit_2=setup_schema.take_profit_2,
            timeframe=timeframe,
            score=score_scaled,
            grade=grade,
        )

    return results


# ─── Signal Log Endpoints ─────────────────────────────────────────────────────

@router.get("/signal-log")
async def get_signal_log(limit: int = Query(50, description="Max records to return")):
    """View all signals (active + resolved) tracked by the state manager."""
    return {
        "active":  signal_state_manager.get_active_signals(),
        "history": signal_state_manager.get_all_signals(limit=limit),
        "total_active": len(signal_state_manager.get_active_signals()),
    }

@router.get("/signal-log/{symbol}")
async def get_signal_for_symbol(symbol: str):
    """Check the current signal state for a specific symbol."""
    result = signal_state_manager.get_signal(symbol.upper())
    if not result:
        return {"found": False, "message": f"No signal tracked for {symbol.upper()}"}
    return {"found": True, "signal": result}

@router.post("/signal-cancel/{symbol}")
async def cancel_signal(symbol: str, reason: str = Query("manual_cancel")):
    """Manually cancel an active signal to allow a new one for that symbol."""
    signal_state_manager.force_cancel(symbol.upper(), reason)
    return {"ok": True, "message": f"Signal for {symbol.upper()} cancelled. New signals now allowed."}
