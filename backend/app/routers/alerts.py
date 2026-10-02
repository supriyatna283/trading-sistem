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


@router.get("/status")
async def alert_status():
    return {
        "wa_configured":    _wa_service.enabled,
        "wa_provider":      _wa_service.provider,
        "registered_phones": list(_configs.keys()),
        "total_configs":    len(_configs),
    }
