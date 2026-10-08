"""
Sprint 1 — Pro Trading Tools API
==================================
Endpoints:
  POST /api/v1/pro/pd-zones          — Premium/Discount Zone analysis
  POST /api/v1/pro/liquidity-sweep   — Liquidity Sweep detection
  POST /api/v1/pro/ob-strength       — Order Block strength scoring
  POST /api/v1/pro/position-size     — Advanced position sizing + Kelly
  GET  /api/v1/pro/killzones         — Killzone status (current session)
  POST /api/v1/pro/full-analysis     — All Sprint 1 features + FVG + Trade Plan in one call
  POST /api/v1/pro/fvg-breaker       — FVG + Breaker Block detection
  GET  /api/v1/pro/session-pairs     — Top volume pairs per killzone
"""

import logging
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone

from app.engines.pd_zones import PDZoneEngine
from app.engines.liquidity_sweep import LiquiditySweepEngine
from app.engines.ob_strength import OBStrengthMeter
from app.engines.position_sizing import PositionSizingEngine
from app.engines.market_data import MarketDataEngine
from app.engines.smart_money import SmartMoneyConceptsEngine
from app.engines.fvg_breaker import FVGBreakerEngine
from app.engines.session_pairs import SessionPairsEngine
from app.engines.market_structure import MarketStructureAnalyzer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/pro", tags=["Pro Tools — Sprint 1"])

# Engine singletons
_pd_engine    = PDZoneEngine()
_sweep_engine = LiquiditySweepEngine()
_ob_meter     = OBStrengthMeter()
_size_engine  = PositionSizingEngine()
_data_engine  = MarketDataEngine()
_smc_engine   = SmartMoneyConceptsEngine()
_fvg_engine   = FVGBreakerEngine()
_session_engine = SessionPairsEngine()
_ms_engine    = MarketStructureAnalyzer()

# ─────────────────────────────────────────────────────────────────────────────
# Pydantic request/response models
# ─────────────────────────────────────────────────────────────────────────────

class PDZoneRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    timeframe: str = Field("1h", example="1h")
    htf: str = Field("1d", description="Higher timeframe for range calculation")
    lookback: int = Field(20, ge=5, le=100)


class LiquiditySweepRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    timeframe: str = Field("1h", example="1h")
    lookback: int = Field(80, ge=20, le=200)


class OBStrengthRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    timeframe: str = Field("1h", example="1h")
    htf: str = Field("4h", description="HTF for OB confluence")


class PositionSizeRequest(BaseModel):
    account_balance: float = Field(..., gt=0, example=10000)
    risk_pct: float        = Field(1.0, ge=0.1, le=10.0, example=1.0)
    entry: float           = Field(..., gt=0, example=64000)
    stop_loss: float       = Field(..., gt=0, example=63000)
    direction: str         = Field("BUY", example="BUY")
    win_rate: float        = Field(0.55, ge=0.01, le=0.99, example=0.55)
    avg_rr: float          = Field(2.0, ge=0.1, example=2.0)
    take_profits: Optional[List[float]] = Field(None, example=[65000, 66500, 68000])


class FullAnalysisRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    timeframe: str = Field("1h", example="1h")
    htf: str = Field("4h", example="4h")
    account_balance: Optional[float] = Field(None, example=10000)
    risk_pct: Optional[float] = Field(1.0, example=1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Killzone Session Logic
# ─────────────────────────────────────────────────────────────────────────────

KILLZONES = [
    {"name": "ASIA",         "start": 0,  "end": 7,  "color": "#f59e0b", "desc": "Asia Range — Accumulation"},
    {"name": "LONDON_OPEN",  "start": 7,  "end": 10, "color": "#10b981", "desc": "London Open KZ — High volatility"},
    {"name": "LONDON",       "start": 10, "end": 12, "color": "#3b82f6", "desc": "London Session"},
    {"name": "NY_OPEN",      "start": 12, "end": 15, "color": "#ef4444", "desc": "NY Open KZ — Manipulation + Trend"},
    {"name": "NY_AM",        "start": 15, "end": 17, "color": "#8b5cf6", "desc": "NY AM Session"},
    {"name": "NY_LUNCH",     "start": 17, "end": 19, "color": "#64748b", "desc": "NY Lunch — Low liquidity"},
    {"name": "NY_PM",        "start": 19, "end": 21, "color": "#6366f1", "desc": "NY PM Session"},
    {"name": "DEAD_ZONE",    "start": 21, "end": 24, "color": "#1e293b", "desc": "Dead Zone — Avoid trading"},
]

HIGH_VOLUME_KZ = {"LONDON_OPEN", "NY_OPEN"}  # Best killzones for ICT setups


def _get_killzone_status() -> dict:
    """Return current session, time-to-next-killzone, and all session data."""
    now_utc = datetime.now(timezone.utc)
    hour    = now_utc.hour
    minute  = now_utc.minute

    current_kz = None
    next_kz    = None

    for kz in KILLZONES:
        if kz["start"] <= hour < kz["end"]:
            current_kz = kz
            break

    # Find next killzone
    for kz in KILLZONES:
        if kz["start"] > hour:
            next_kz = kz
            break
    if not next_kz:
        next_kz = KILLZONES[0]  # Wrap around to ASIA

    # Time to next killzone
    if next_kz["start"] > hour:
        mins_to_next = (next_kz["start"] - hour) * 60 - minute
    else:
        # Wraps to next day
        mins_to_next = (24 - hour + next_kz["start"]) * 60 - minute

    hours_to_next = mins_to_next // 60
    rem_mins      = mins_to_next % 60

    is_high_volume = (current_kz or {}).get("name", "") in HIGH_VOLUME_KZ

    return {
        "current_session":    (current_kz or next_kz)["name"],
        "current_kz":         current_kz,
        "next_kz":            next_kz,
        "time_to_next":       f"{hours_to_next}h {rem_mins}m",
        "mins_to_next":       mins_to_next,
        "is_high_volume_kz":  is_high_volume,
        "is_killzone_active": current_kz is not None and current_kz["name"] in HIGH_VOLUME_KZ,
        "utc_time":           now_utc.strftime("%H:%M:%S UTC"),
        "all_sessions":       KILLZONES,
        "trade_advice": (
            "🔥 OPTIMAL — In high-volume killzone!" if is_high_volume else
            "✅ In active session" if current_kz else
            "⏳ Wait for next killzone"
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/killzones")
async def get_killzone_status():
    """
    Get current ICT killzone status.
    Returns active session, time to next killzone, and trade advice.
    """
    return _get_killzone_status()


@router.post("/pd-zones")
async def get_pd_zones(req: PDZoneRequest):
    """
    Premium / Discount Zone analysis.
    Fetches HTF candles and determines if price is in BUY (discount) or SELL (premium) zone.
    """
    try:
        # Fetch HTF data for range calculation
        df_htf = await _data_engine.get_candles(req.symbol, req.htf, limit=100)
        df_entry = await _data_engine.get_candles(req.symbol, req.timeframe, limit=5)

        if df_entry is None or df_entry.empty:
            raise HTTPException(status_code=404, detail=f"No candle data available for {req.symbol}")

        current_price = float(df_entry["close"].iloc[-1])

        if df_htf is None or df_htf.empty:
            df_htf = df_entry

        result = _pd_engine.analyze(df_htf, current_price, lookback=req.lookback, htf_label=req.htf.upper())

        return {
            "symbol":       req.symbol,
            "timeframe":    req.timeframe,
            "htf":          req.htf,
            "current_price": current_price,
            "pd_zone": {
                "zone":                result.zone,
                "zone_pct":            result.zone_pct,
                "zone_color":          result.zone_color,
                "htf_bias":            result.htf_bias,
                "signal":              result.signal,
                "trade_allowed":       result.trade_allowed,
                "is_in_ote":           result.is_in_ote,
                "distance_to_ote_pct": result.distance_to_ote_pct,
                "levels": {
                    "range_high":          result.range_high,
                    "range_low":           result.range_low,
                    "equilibrium":         result.equilibrium,
                    "premium_threshold":   result.premium_threshold,
                    "discount_threshold":  result.discount_threshold,
                    "ote_low":             result.ote_low,
                    "ote_high":            result.ote_high,
                },
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("PD Zone error")
        raise HTTPException(status_code=500, detail=f"PD Zone analysis failed: {str(e)}")


@router.post("/liquidity-sweep")
async def get_liquidity_sweep(req: LiquiditySweepRequest):
    """
    Detect liquidity sweeps (equal highs/lows swept by market maker).
    Returns pools, sweep events, and directional bias.
    """
    try:
        df = await _data_engine.get_candles(req.symbol, req.timeframe, limit=req.lookback + 20)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No candle data for {req.symbol}")

        result = _sweep_engine.analyze(df)

        return {
            "symbol":       req.symbol,
            "timeframe":    req.timeframe,
            **result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Liquidity sweep error")
        raise HTTPException(status_code=500, detail=f"Liquidity sweep analysis failed: {str(e)}")


@router.post("/ob-strength")
async def get_ob_strength(req: OBStrengthRequest):
    """
    Score all active Order Blocks by institutional quality (A+ to D).
    """
    try:
        df_entry = await _data_engine.get_candles(req.symbol, req.timeframe, limit=200)
        df_htf   = await _data_engine.get_candles(req.symbol, req.htf, limit=100)

        if df_entry is None or df_entry.empty:
            raise HTTPException(status_code=404, detail=f"No candle data for {req.symbol}")

        # Get OBs and FVGs from SMC engine
        smc_entry = _smc_engine.analyze(df_entry, req.symbol, req.timeframe)
        smc_htf   = _smc_engine.analyze(df_htf, req.symbol, req.htf) if df_htf is not None and not df_htf.empty else None

        htf_obs = smc_htf.order_blocks if smc_htf else []

        scored = _ob_meter.score_order_blocks(
            df_entry,
            smc_entry.order_blocks,
            smc_entry.fvgs,
            htf_obs,
        )

        return {
            "symbol":        req.symbol,
            "timeframe":     req.timeframe,
            "htf":           req.htf,
            "total_obs":     len(scored),
            "a_plus_count":  sum(1 for s in scored if s.grade == "A+"),
            "order_blocks":  [_ob_meter.to_dict(s) for s in scored],
            "best_ob":       _ob_meter.to_dict(scored[0]) if scored else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("OB strength error")
        raise HTTPException(status_code=500, detail=f"OB strength analysis failed: {str(e)}")


@router.post("/position-size")
async def calculate_position_size(req: PositionSizeRequest):
    """
    Advanced position sizing with Kelly Criterion and Risk of Ruin.
    Supports multiple take profits (TP1, TP2, TP3).
    """
    try:
        result = _size_engine.calculate(
            account_balance=req.account_balance,
            risk_pct=req.risk_pct,
            entry=req.entry,
            stop_loss=req.stop_loss,
            direction=req.direction,
            win_rate=req.win_rate,
            avg_rr=req.avg_rr,
            take_profits=req.take_profits,
        )

        return {
            "result": {
                "position_size":          result.position_size,
                "position_value":         result.position_value,
                "risk_amount":            result.risk_amount,
                "risk_pct":               result.risk_pct,
                "stop_distance":          result.stop_distance,
                "stop_distance_pct":      result.stop_distance_pct,
                "take_profit_1":          result.take_profit_1,
                "take_profit_2":          result.take_profit_2,
                "take_profit_3":          result.take_profit_3,
                "rr_1":                   result.rr_1,
                "rr_2":                   result.rr_2,
                "rr_3":                   result.rr_3,
                "kelly": {
                    "full_kelly_pct":         result.kelly_full,
                    "quarter_kelly_pct":      result.kelly_quarter,
                    "recommended_risk_pct":   result.kelly_recommended_pct,
                },
                "risk_metrics": {
                    "risk_of_ruin_pct":       result.risk_of_ruin_pct,
                    "max_consecutive_losses": result.max_consecutive_losses,
                    "breakeven_win_rate":     result.breakeven_win_rate,
                    "expected_value":         result.expected_value,
                },
                "leverage_sizes": {
                    "1x":   result.leverage_1x_size,
                    "5x":   result.leverage_5x_size,
                    "10x":  result.leverage_10x_size,
                },
                "size_grade":  result.size_grade,
                "warnings":    result.warnings,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Position sizing error")
        raise HTTPException(status_code=500, detail=f"Position sizing calculation failed: {str(e)}")


@router.post("/full-analysis")
async def get_full_sprint1_analysis(req: FullAnalysisRequest):
    """
    Combined analysis: PD zones + Liquidity sweeps + OB strength + Killzone + FVG + Auto Trade Plan.
    Single call for complete institutional analysis overlay.
    """
    try:
        symbol = req.symbol.upper()

        # Fetch data
        df_entry = await _data_engine.get_candles(symbol, req.timeframe, limit=200)
        df_htf   = await _data_engine.get_candles(symbol, req.htf, limit=100)

        if df_entry is None or df_entry.empty:
            raise HTTPException(status_code=404, detail=f"No candle data for {symbol}")

        current_price = float(df_entry["close"].iloc[-1])

        # 1. PD Zones
        pd_result = _pd_engine.analyze(
            df_htf if df_htf is not None and not df_htf.empty else df_entry,
            current_price,
            htf_label=req.htf.upper()
        )

        # 2. Liquidity Sweeps
        sweep_result = _sweep_engine.analyze(df_entry)

        # 3. OB Strength
        smc_entry  = _smc_engine.analyze(df_entry, symbol, req.timeframe)
        smc_htf    = _smc_engine.analyze(df_htf, symbol, req.htf) if df_htf is not None and not df_htf.empty else None
        htf_obs    = smc_htf.order_blocks if smc_htf else []
        scored_obs = _ob_meter.score_order_blocks(df_entry, smc_entry.order_blocks, smc_entry.fvgs, htf_obs)

        # 4. Killzone
        kz_status = _get_killzone_status()

        # 5. FVG + Breaker analysis
        fvg_result_raw = _fvg_engine.analyze(df_entry)
        fvg_data       = _fvg_engine.to_dict(fvg_result_raw)

        # ── Aggregate confluence score (0–16 scale from backend) ────────────
        bias_direction  = sweep_result.get("bias_from_sweep") or fvg_data["signals"]["entry_bias"] or "BUY"
        pd_score        = _pd_engine.score_for_confluence(pd_result, bias_direction)
        sweep_score     = sweep_result.get("score", 0)
        ob_score        = min(5, (scored_obs[0].score // 20) if scored_obs else 0)
        kz_score        = 3 if kz_status["is_killzone_active"] else (1 if kz_status["current_kz"] else 0)
        total_score     = pd_score + sweep_score + ob_score + kz_score
        score_pct       = round((total_score / 16) * 100, 1)

        # ── Auto Trade Plan ─────────────────────────────────────────────────
        trade_plan = None
        entry_zone = None

        # Prefer FVG entry zone aligned with bias
        if bias_direction in ("BUY", "STRONG_BUY"):
            nearest = fvg_data["nearest"]["bullish_fvg"]
            if nearest:
                entry_zone = nearest.get("entry_zone")
        elif bias_direction in ("SELL", "STRONG_SELL"):
            nearest = fvg_data["nearest"]["bearish_fvg"]
            if nearest:
                entry_zone = nearest.get("entry_zone")

        # Fallback to best breaker
        if not entry_zone:
            breaker = fvg_data["nearest"].get("breaker")
            if breaker:
                entry_zone = breaker.get("entry_zone")

        if entry_zone:
            trade_plan = {
                "bias":         bias_direction,
                "entry":        entry_zone.get("entry"),
                "stop_loss":    entry_zone.get("stop_loss"),
                "tp1":          entry_zone.get("tp1"),
                "tp2":          entry_zone.get("tp2"),
                "tp3":          entry_zone.get("tp3"),
                "rr_tp1":       entry_zone.get("rr_tp1"),
                "rr_tp2":       entry_zone.get("rr_tp2"),
                "risk_pct":     entry_zone.get("risk_pct"),
                "quality":      entry_zone.get("quality"),
                "pd_zone":      pd_result.zone,
                "killzone":     kz_status["current_session"],
                "is_killzone":  kz_status["is_killzone_active"],
                "in_ote":       pd_result.is_in_ote,
                "confidence":   score_pct,
            }

        grade = (
            "A+" if total_score >= 13 else
            "A"  if total_score >= 10 else
            "B"  if total_score >= 7  else
            "C"  if total_score >= 4  else "WEAK"
        )

        return {
            "symbol":        symbol,
            "timeframe":     req.timeframe,
            "htf":           req.htf,
            "current_price": current_price,

            "pd_zone": {
                "zone":           pd_result.zone,
                "zone_pct":       pd_result.zone_pct,
                "zone_color":     pd_result.zone_color,
                "signal":         pd_result.signal,
                "htf_bias":       pd_result.htf_bias,
                "trade_allowed":  pd_result.trade_allowed,
                "is_in_ote":      pd_result.is_in_ote,
                "distance_to_ote_pct": pd_result.distance_to_ote_pct,
                "levels": {
                    "range_high":         pd_result.range_high,
                    "range_low":          pd_result.range_low,
                    "equilibrium":        pd_result.equilibrium,
                    "premium_threshold":  pd_result.premium_threshold,
                    "discount_threshold": pd_result.discount_threshold,
                    "ote_low":            pd_result.ote_low,
                    "ote_high":           pd_result.ote_high,
                },
                "score": pd_score,
            },

            "liquidity_sweep": {
                "latest_sweep":     sweep_result.get("latest_sweep"),
                "bias_from_sweep":  sweep_result.get("bias_from_sweep"),
                "confirmed_count":  sweep_result.get("confirmed_count", 0),
                "total_pools":      len(sweep_result.get("pools", [])),
                "pools":            sweep_result.get("pools", [])[:6],
                "score":            sweep_score,
            },

            "ob_strength": {
                "total_obs":    len(scored_obs),
                "a_plus_count": sum(1 for s in scored_obs if s.grade == "A+"),
                "best_ob":      _ob_meter.to_dict(scored_obs[0]) if scored_obs else None,
                "top_obs":      [_ob_meter.to_dict(s) for s in scored_obs[:3]],
                "score":        ob_score,
            },

            "killzone": {
                **kz_status,
                "score": kz_score,
            },

            "fvg": {
                "summary":          fvg_data["summary"],
                "nearest":          fvg_data["nearest"],
                "ict_setup":        fvg_data["ict_setup"],
                "signals":          fvg_data["signals"],
                "bullish_fvgs":     fvg_data["bullish_fvgs"][:5],
                "bearish_fvgs":     fvg_data["bearish_fvgs"][:5],
                "bullish_breakers": fvg_data["bullish_breakers"][:3],
                "bearish_breakers": fvg_data["bearish_breakers"][:3],
            },

            "trade_plan": trade_plan,

            "confluence": {
                "total_score":  total_score,
                "max_score":    16,
                "score_pct":    score_pct,
                "grade":        grade,
                "bias":         bias_direction,
                "signal": (
                    "HIGH CONVICTION ENTRY" if total_score >= 13 else
                    "VALID SETUP"           if total_score >= 10 else
                    "WATCHLIST"             if total_score >= 7  else
                    "WAIT"
                ),
                "breakdown": {
                    "pd_zone":  pd_score,
                    "sweep":    sweep_score,
                    "ob":       ob_score,
                    "killzone": kz_score,
                },
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Full analysis error")
        raise HTTPException(status_code=500, detail=f"Full analysis failed: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# FVG + BREAKER BLOCK endpoint
# ─────────────────────────────────────────────────────────────────────────────

class FVGRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    timeframe: str = Field("1h", example="1h")
    limit: int = Field(150, ge=30, le=300)


@router.post("/fvg-breaker")
async def get_fvg_breaker(req: FVGRequest):
    """
    Fair Value Gap (FVG) + Breaker Block detection.
    - Detects all bullish/bearish FVGs (3-candle imbalance)
    - Identifies IFVG (Inversion FVG) when price mitigates through
    - Detects Consequent Encroachment (CE) level for each FVG
    - Finds Breaker Blocks (failed OBs that reversed)
    - Returns nearest key levels to current price
    """
    try:
        df = await _data_engine.get_candles(req.symbol, req.timeframe, limit=req.limit)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No candle data for {req.symbol}")

        result = _fvg_engine.analyze(df)
        return {
            "symbol":    req.symbol,
            "timeframe": req.timeframe,
            **_fvg_engine.to_dict(result),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("FVG/Breaker error")
        raise HTTPException(status_code=500, detail=f"FVG/Breaker analysis failed: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# MARKET STRUCTURE (MSS/CHoCH) endpoint (Feature #1)
# ─────────────────────────────────────────────────────────────────────────────

class MarketStructureRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    timeframe: str = Field("1h", example="1h")
    lookback: int = Field(200, example=200, ge=50, le=500)
    swing_lookback: int = Field(5, example=5, ge=2, le=20)

@router.post("/market-structure")
async def get_market_structure(req: MarketStructureRequest):
    """
    Market Structure Analyzer.
    Detects HH, HL, LH, LL swing points.
    Identifies Break of Structure (BOS) and Change of Character (CHOCH).
    Returns overall market bias based on recent structure.
    """
    try:
        df = await _data_engine.get_candles(req.symbol, req.timeframe, limit=req.lookback)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No candle data for {req.symbol}")
            
        # Re-initialize engine if swing_lookback differs from default
        engine = _ms_engine if req.swing_lookback == 5 else MarketStructureAnalyzer(swing_lookback=req.swing_lookback)
        result = engine.analyze(df, symbol=req.symbol, timeframe=req.timeframe)
        
        # Combine labels for the same index (e.g. HH and BOS are emitted separately in market_structure.py)
        processed_labels = {}
        for l in result.structure_labels:
            if l.index not in processed_labels:
                processed_labels[l.index] = {"index": l.index, "label": "Unknown", "is_break": False, "break_type": None}
            
            if l.label in ["BOS", "CHOCH"]:
                processed_labels[l.index]["is_break"] = True
                processed_labels[l.index]["break_type"] = l.label
            else:
                processed_labels[l.index]["label"] = l.label
                
        final_labels = list(processed_labels.values())

        return {
            "symbol": result.symbol,
            "timeframe": result.timeframe,
            "bias": result.bias,
            "swing_points": [
                {
                    "index": s.index,
                    "price": s.price,
                    "type": s.type,
                    "time": str(s.time) if s.time else None
                } for s in result.swing_points[-20:] # Return last 20 swings
            ],
            "structure_labels": final_labels[-10:] # Return last 10 structure events
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Market structure error")
        raise HTTPException(status_code=500, detail=f"Market structure analysis failed: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# SESSION PAIRS — top volume pairs per killzone
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/session-pairs")
async def get_session_pairs(
    session: Optional[str] = Query(None, description="Override session: ASIA|LONDON|NY_OPEN|NY_PM|DEAD"),
    top_n:   int           = Query(20,   ge=5, le=50, description="Max pairs to return"),
):
    """
    Returns top-volume trading pairs for the current (or specified) trading session.
    Live data from Binance 24hr ticker. Cached 60 seconds.
    """
    try:
        result = await _session_engine.get_session_pairs(
            session_override=session,
            top_n=top_n,
        )
        return _session_engine.to_dict(result)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Session pairs error")
        raise HTTPException(status_code=500, detail=f"Session pairs fetch failed: {str(e)}")
