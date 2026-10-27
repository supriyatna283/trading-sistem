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

import asyncio
import time
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
from app.engines.market_maker_flow import MarketMakerFlowEngine
from app.engines.garch_volatility import GARCHVolatilityEngine
from app.engines.wyckoff import WyckoffEngine
from app.engines.options_perps import OptionsPerpsEngine
from app.engines.mtf_confirmation import MTFConfirmationEngine
from app.engines.macro_news import MacroNewsEngine
from app.engines.smt_divergence import SMTDivergenceEngine
from app.engines.volume_profile import VolumeProfileEngine
from app.engines.sentiment import SentimentEngine
import httpx

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/pro", tags=["Pro Tools"])

def _prep_df(df, timeframe: str):
    """Extract data provenance and drop the unclosed forming candle to prevent repainting."""
    if df is None or df.empty:
        return df, "unavailable", False
    data_source = str(df.attrs.get("data_source", "live"))
    is_synthetic = bool(df.attrs.get("is_synthetic", False)) or data_source == "synthetic"
    cleaned = MarketDataEngine.drop_unclosed(df, timeframe)
    if cleaned.empty:
        cleaned = df
    cleaned.attrs["data_source"] = data_source
    cleaned.attrs["is_synthetic"] = is_synthetic
    return cleaned, data_source, is_synthetic


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
_mm_engine    = MarketMakerFlowEngine()
_garch_engine = GARCHVolatilityEngine()
_wyckoff_engine = WyckoffEngine()
_options_engine = OptionsPerpsEngine()
_mtf_engine   = MTFConfirmationEngine()
_macro_engine = MacroNewsEngine()
_smt_engine   = SMTDivergenceEngine()
_vp_engine    = VolumeProfileEngine()
_sentiment_engine = SentimentEngine()

_PERP_SNAPSHOT_CACHE: dict = {}
_PERP_SNAPSHOT_TTL = 45.0  # seconds


async def _fetch_live_perp_snapshot(symbol: str, spot_price: float, df_daily) -> dict:
    """
    Fetch live perpetual futures metrics (Funding Rate, Mark Price, Open Interest,
    Long/Short Account Ratio) from Binance Futures with OKX V5 Swap fallback.
    """
    sym = symbol.upper()
    if not sym.endswith("USDT"):
        sym = f"{sym}USDT"
    now = time.time()
    cached_snap = _PERP_SNAPSHOT_CACHE.get(sym)
    if cached_snap and (now - cached_snap["ts"]) < _PERP_SNAPSHOT_TTL:
        return cached_snap["data"]

    base = sym[:-4]
    okx_inst = f"{base}-USDT-SWAP"

    funding_8h_pct: Optional[float] = None
    mark_price: Optional[float] = None
    oi_coins: Optional[float] = None
    oi_usd: Optional[float] = None
    oi_trend: str = "STABLE"
    ls_ratio: Optional[float] = None
    source: Optional[str] = None

    # 1. Try Binance Futures via SentimentEngine
    try:
        f_list, oi_list, ls_data = await __import__("asyncio").gather(
            _sentiment_engine.get_funding_rates([sym]),
            _sentiment_engine.get_open_interest([sym]),
            _sentiment_engine.get_long_short_ratio(sym, period="1h"),
            return_exceptions=True,
        )
        if isinstance(f_list, list) and f_list:
            # Binance lastFundingRate is decimal (e.g. 0.0001 = 0.01%)
            funding_8h_pct = float(f_list[0].get("funding_rate", 0.0)) * 100.0
            mp = float(f_list[0].get("mark_price", 0.0))
            if mp > 0:
                mark_price = mp
            source = "binance"
        if isinstance(oi_list, list) and oi_list:
            oi_coins = float(oi_list[0].get("open_interest_coin", 0.0))
            if oi_coins > 0:
                oi_usd = oi_coins * (mark_price or spot_price)
                source = source or "binance"
        if isinstance(ls_data, dict) and ls_data.get("ratio") is not None:
            ls_ratio = float(ls_data["ratio"])
            source = source or "binance"
    except Exception as e:
        logger.debug(f"Binance perp snapshot fallback for {sym}: {e}")

    # 2. Fallback to OKX Public V5 Swap API in PARALLEL for any missing metrics
    if funding_8h_pct is None or oi_usd is None or ls_ratio is None:
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                r_f, r_mp, r_oi, r_ls = await asyncio.gather(
                    client.get("https://www.okx.com/api/v5/public/funding-rate", params={"instId": okx_inst})
                    if funding_8h_pct is None else asyncio.sleep(0),
                    client.get("https://www.okx.com/api/v5/public/mark-price", params={"instType": "SWAP", "instId": okx_inst})
                    if mark_price is None else asyncio.sleep(0),
                    client.get("https://www.okx.com/api/v5/public/open-interest", params={"instType": "SWAP", "instId": okx_inst})
                    if oi_usd is None else asyncio.sleep(0),
                    client.get("https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio", params={"ccy": base, "period": "1H"})
                    if ls_ratio is None else asyncio.sleep(0),
                    return_exceptions=True,
                )
                if hasattr(r_f, "status_code") and r_f.status_code == 200:
                    d_f = r_f.json().get("data", [])
                    if d_f:
                        funding_8h_pct = float(d_f[0].get("fundingRate", 0.0)) * 100.0
                        source = source or "okx"

                if hasattr(r_mp, "status_code") and r_mp.status_code == 200:
                    d_mp = r_mp.json().get("data", [])
                    if d_mp and float(d_mp[0].get("markPx", 0) or 0) > 0:
                        mark_price = float(d_mp[0]["markPx"])

                if hasattr(r_oi, "status_code") and r_oi.status_code == 200:
                    d_oi = r_oi.json().get("data", [])
                    if d_oi:
                        oi_ccy = float(d_oi[0].get("oiCcy", 0.0) or 0.0)
                        oi_usd_val = float(d_oi[0].get("oiUsd", 0.0) or 0.0)
                        oi_coins = oi_ccy if oi_ccy > 0 else None
                        oi_usd = oi_usd_val if oi_usd_val > 0 else (oi_ccy * (mark_price or spot_price) if oi_ccy > 0 else None)
                        source = source or "okx"

                if hasattr(r_ls, "status_code") and r_ls.status_code == 200:
                    d_ls = r_ls.json().get("data", [])
                    if d_ls and len(d_ls[0]) >= 2:
                        ls_ratio = float(d_ls[0][1])
                        source = source or "okx"
        except Exception as e:
            logger.debug(f"OKX perp snapshot fallback failed for {sym}: {e}")

    # Infer OI / participation trend from recent volume & close expansion when live OI is present
    if df_daily is not None and len(df_daily) >= 7 and "volume" in df_daily.columns:
        vols = df_daily["volume"].astype(float).values
        recent_v = float(vols[-1])
        avg_v = float(vols[-7:-1].mean()) if len(vols) >= 7 else float(vols.mean())
        if avg_v > 0:
            if recent_v >= avg_v * 1.15:
                oi_trend = "RISING"
            elif recent_v <= avg_v * 0.85:
                oi_trend = "FALLING"
            else:
                oi_trend = "STABLE"

    snap = {
        "funding_8h_pct": funding_8h_pct,
        "mark_price": mark_price,
        "oi_coins": oi_coins,
        "oi_usd": oi_usd,
        "oi_trend": oi_trend if source else "UNAVAILABLE",
        "ls_ratio": ls_ratio,
        "source": source,
    }
    if source:
        _PERP_SNAPSHOT_CACHE[sym] = {"data": snap, "ts": now}
    return snap

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


class VolatilityRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    timeframe: str = Field("1d", example="1d")
    limit: int = Field(100, ge=30, le=500)


class MMFlowRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    timeframe: str = Field("1h", example="1h")
    limit: int = Field(100, ge=20, le=500)


class WyckoffRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    timeframe: str = Field("1h", example="1h")
    limit: int = Field(150, ge=50, le=500)


class OptionsPerpsRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")


class MTFAlignmentRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")


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
        # Fetch HTF + entry candles in parallel
        df_htf_raw, df_entry_raw = await asyncio.gather(
            _data_engine.get_candles(req.symbol, req.htf, limit=100),
            _data_engine.get_candles(req.symbol, req.timeframe, limit=10),
        )

        if df_entry_raw is None or df_entry_raw.empty:
            raise HTTPException(status_code=404, detail=f"No candle data available for {req.symbol}")

        df_entry, data_source, is_synthetic = _prep_df(df_entry_raw, req.timeframe)
        df_htf, _, _ = _prep_df(df_htf_raw, req.htf)
        current_price = float(df_entry["close"].iloc[-1])

        if df_htf is None or df_htf.empty:
            df_htf = df_entry

        result = _pd_engine.analyze(df_htf, current_price, lookback=req.lookback, htf_label=req.htf.upper())

        return {
            "symbol":       req.symbol,
            "timeframe":    req.timeframe,
            "htf":          req.htf,
            "current_price": current_price,
            "data_source":  data_source,
            "is_synthetic": is_synthetic,
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
        df_raw = await _data_engine.get_candles(req.symbol, req.timeframe, limit=req.lookback + 20)
        if df_raw is None or df_raw.empty:
            raise HTTPException(status_code=404, detail=f"No candle data for {req.symbol}")

        df, data_source, is_synthetic = _prep_df(df_raw, req.timeframe)
        result = _sweep_engine.analyze(df)

        return {
            "symbol":       req.symbol,
            "timeframe":    req.timeframe,
            "data_source":  data_source,
            "is_synthetic": is_synthetic,
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
        df_entry_raw, df_htf_raw = await asyncio.gather(
            _data_engine.get_candles(req.symbol, req.timeframe, limit=200),
            _data_engine.get_candles(req.symbol, req.htf, limit=100),
        )

        if df_entry_raw is None or df_entry_raw.empty:
            raise HTTPException(status_code=404, detail=f"No candle data for {req.symbol}")

        df_entry, data_source, is_synthetic = _prep_df(df_entry_raw, req.timeframe)
        df_htf, _, _ = _prep_df(df_htf_raw, req.htf)

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
            "data_source":   data_source,
            "is_synthetic":  is_synthetic,
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
                "margin_required": {
                    "1x":   result.margin_1x,
                    "5x":   result.margin_5x,
                    "10x":  result.margin_10x,
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
        correlated_sym = "ETHUSDT" if symbol == "BTCUSDT" else "BTCUSDT"

        # Fetch all required candles + macro news in PARALLEL (1 network round-trip instead of 4!)
        df_entry_raw, df_htf_raw, df_corr_raw, macro_status = await asyncio.gather(
            _data_engine.get_candles(symbol, req.timeframe, limit=200),
            _data_engine.get_candles(symbol, req.htf, limit=100),
            _data_engine.get_candles(correlated_sym, req.timeframe, limit=200),
            _macro_engine.check_news_proximity_async(warning_minutes=60),
        )

        if df_entry_raw is None or df_entry_raw.empty:
            raise HTTPException(status_code=404, detail=f"No candle data for {symbol}")

        df_entry, data_source, is_synthetic = _prep_df(df_entry_raw, req.timeframe)
        df_htf, _, _ = _prep_df(df_htf_raw, req.htf)
        df_corr, _, _ = _prep_df(df_corr_raw, req.timeframe)

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

        # 6. Market Structure & MMFlow for enhanced scoring
        ms_result = _ms_engine.analyze(df_entry, symbol, req.timeframe)
        structure_score = 3 if any(l.label in ["BOS", "CHOCH"] for l in ms_result.structure_labels[-5:]) else 0

        mm_result = _mm_engine.analyze(df_entry)
        mm_score = mm_result.confluence_score

        # 8. SMT Divergence Check (Sprint D)
        if df_corr is not None and not df_corr.empty:
            smt_result = _smt_engine.analyze(df_entry, df_corr, symbol, correlated_sym)
        else:
            smt_result = None

        # 9. Volume Profile Check (Sprint D)
        vp_result = _vp_engine.analyze(df_entry)

        # ── Aggregate confluence score (0–24 scale from backend) ────────────
        bias_direction  = sweep_result.get("bias_from_sweep") or fvg_data["signals"]["entry_bias"] or "NEUTRAL"
        pd_score        = _pd_engine.score_for_confluence(pd_result, bias_direction)
        sweep_score     = sweep_result.get("score", 0)
        ob_score        = min(5, ((scored_obs[0].score + 10) // 20) if scored_obs else 0)
        kz_score        = 3 if kz_status["is_killzone_active"] else (1 if kz_status["current_kz"] else 0)

        total_score     = pd_score + sweep_score + ob_score + kz_score + structure_score + mm_score
        max_score       = 24
        score_pct       = round((total_score / max_score) * 100, 1)
        macro_restricted = macro_status["is_restricted"]

        # Cap the score and force WAIT/NEUTRAL during high-impact news or synthetic fallback data.
        if is_synthetic:
            score_pct = min(score_pct, 35)
            grade = "WAIT"
            signal = "SYNTHETIC DATA — NO LIVE TRADE"
        elif macro_restricted:
            score_pct = min(score_pct, 40)
            grade = "WAIT"
            signal = "NEUTRAL"
        else:
            grade = ("A+" if score_pct >= 90 else "A" if score_pct >= 80 else
                     "B"  if score_pct >= 65 else "C" if score_pct >= 50 else
                     "D"  if score_pct >= 30 else "WAIT")
            signal = ("HIGH CONVICTION ENTRY" if total_score >= 19 else
                      "VALID SETUP"           if total_score >= 15 else
                      "WATCHLIST"             if total_score >= 11 else
                      "WAIT")

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

        if entry_zone and not macro_restricted and not is_synthetic:
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
                "exit_strategy": {
                    "tp1_action": "Close 50% & move SL to Break Even",
                    "tp2_action": "Close 30% & trail SL by 1 ATR",
                    "tp3_action": "Let remaining 20% run / manually trail"
                }
            }

        return {
            "symbol":        symbol,
            "timeframe":     req.timeframe,
            "htf":           req.htf,
            "current_price": current_price,
            "data_source":   data_source,
            "is_synthetic":  is_synthetic,

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
                "max_score":    24,
                "score_pct":    score_pct,
                "grade":        grade,
                "bias":         bias_direction,
                "signal":        signal,
                "macro_restricted": macro_status["is_restricted"],
                "macro_message": macro_status["message"],
                "breakdown": {
                    "pd_zone":  pd_score,
                    "sweep":    sweep_score,
                    "ob":       ob_score,
                    "killzone": kz_score,
                    "structure": structure_score,
                    "mm_flow":  mm_score,
                },
                "smt": {
                    "is_divergent": smt_result.is_divergent if smt_result else False,
                    "type": smt_result.smt_type if smt_result else "NONE",
                    "description": smt_result.description if smt_result else "No SMT data",
                } if smt_result else None,
                "volume_profile": {
                    "poc_price": vp_result.poc_price,
                    "vah_price": vp_result.vah_price,
                    "val_price": vp_result.val_price,
                } if vp_result else None,
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
        df_raw = await _data_engine.get_candles(req.symbol, req.timeframe, limit=req.limit)
        if df_raw is None or df_raw.empty:
            raise HTTPException(status_code=404, detail=f"No candle data for {req.symbol}")

        df, data_source, is_synthetic = _prep_df(df_raw, req.timeframe)
        result = _fvg_engine.analyze(df)
        return {
            "symbol":       req.symbol,
            "timeframe":    req.timeframe,
            "data_source":  data_source,
            "is_synthetic": is_synthetic,
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
        df_raw = await _data_engine.get_candles(req.symbol, req.timeframe, limit=req.lookback)
        if df_raw is None or df_raw.empty:
            raise HTTPException(status_code=404, detail=f"No candle data for {req.symbol}")

        df, data_source, is_synthetic = _prep_df(df_raw, req.timeframe)

        # Re-initialize engine if swing_lookback differs from default
        engine = _ms_engine if req.swing_lookback == 5 else MarketStructureAnalyzer(swing_lookback=req.swing_lookback)
        result = engine.analyze(df, symbol=req.symbol, timeframe=req.timeframe)

        # Map swing indices -> swing labels (HH, HL, LH, LL)
        swing_label_by_idx = {}
        for l in result.structure_labels:
            if l.label in ("HH", "HL", "LH", "LL"):
                swing_label_by_idx[l.index] = l.label

        # Build enriched structure events (both swing labels and close-break BOS/CHOCH)
        final_labels = []
        for l in result.structure_labels:
            if l.label in ("BOS", "CHOCH"):
                # Match the swing point whose level was broken (l.price is the broken swing level)
                broken_sw = None
                for sw in reversed(result.swing_points):
                    if sw.index < l.index and abs(sw.price - l.price) <= max(1e-8, abs(l.price) * 1e-6):
                        broken_sw = sw
                        break
                if broken_sw is not None:
                    sw_lbl = swing_label_by_idx.get(broken_sw.index, "Swing High" if broken_sw.type == "HIGH" else "Swing Low")
                    direction = "BULLISH" if broken_sw.type == "HIGH" else "BEARISH"
                else:
                    sw_lbl = "Structure Level"
                    direction = result.bias if result.bias in ("BULLISH", "BEARISH") else "BULLISH"
                final_labels.append({
                    "index": l.index,
                    "label": sw_lbl,
                    "is_break": True,
                    "break_type": l.label,
                    "direction": direction,
                    "broken_level": l.price,
                    "time": str(l.time) if l.time else None,
                })
            else:
                final_labels.append({
                    "index": l.index,
                    "label": l.label,
                    "is_break": False,
                    "break_type": None,
                    "direction": "BULLISH" if l.label in ("HH", "HL") else "BEARISH",
                    "broken_level": l.price,
                    "time": str(l.time) if l.time else None,
                })

        return {
            "symbol": result.symbol,
            "timeframe": result.timeframe,
            "data_source": data_source,
            "is_synthetic": is_synthetic,
            "bias": result.bias,
            "swing_points": [
                {
                    "index": s.index,
                    "price": s.price,
                    "type": s.type,
                    "swing_label": swing_label_by_idx.get(s.index, s.type),
                    "time": str(s.time) if s.time else None,
                } for s in result.swing_points[-20:]
            ],
            "structure_labels": final_labels[-25:],
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


# ─────────────────────────────────────────────────────────────────────────────
# MMFlow and Volatility Endpoints (Sprint A additions)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/mm-flow")
async def get_mm_flow(req: MMFlowRequest):
    """Get market maker flow analysis."""
    try:
        df = await _data_engine.get_candles(req.symbol, req.timeframe, limit=req.limit)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No candle data for {req.symbol}")
        
        result = _mm_engine.analyze(df)
        return {
            "symbol": req.symbol,
            "timeframe": req.timeframe,
            "candle_delta": result.candle_delta,
            "cumulative_delta": result.cumulative_delta,
            "delta_trend": result.delta_trend,
            "vwap_deviation_pct": result.vwap_deviation_pct,
            "price_vs_vwap": result.price_vs_vwap,
            "mm_phase": result.mm_phase,
            "absorption_detected": result.absorption_detected,
            "confluence_score": result.confluence_score,
        }
    except Exception as e:
        logger.exception("MM Flow error")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/volatility")
async def get_volatility(req: VolatilityRequest):
    """Get GARCH volatility forecast for SL sizing."""
    try:
        df = await _data_engine.get_candles(req.symbol, req.timeframe, limit=req.limit)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No candle data for {req.symbol}")
        
        result = _garch_engine.analyze(df)
        return {
            "symbol": req.symbol,
            "timeframe": req.timeframe,
            "vol_regime": result.vol_regime,
            "current_vol_daily": result.current_vol_daily,
            "expected_daily_move_pct": result.expected_daily_move_pct,
            "atr_equivalent": result.atr_equivalent,
        }
    except Exception as e:
        logger.exception("Volatility error")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Sprint B Endpoints: Wyckoff, Options/Perps, MTF Alignment
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/wyckoff")
async def get_wyckoff(req: WyckoffRequest):
    """Detect Wyckoff phases (Accumulation / Distribution) for macro context."""
    try:
        df_raw = await _data_engine.get_candles(req.symbol, req.timeframe, limit=req.limit)
        if df_raw is None or df_raw.empty:
            raise HTTPException(status_code=404, detail=f"No candle data for {req.symbol}")
        df, data_source, is_synthetic = _prep_df(df_raw, req.timeframe)
        result = _wyckoff_engine.analyze(df, lookback=req.limit)
        return {
            "symbol": req.symbol,
            "timeframe": req.timeframe,
            "schematic": result.schematic,
            "phase": result.phase,
            "is_actionable": result.is_actionable,
            "signal": result.signal,
            "events": [{"name": e.name, "description": e.description} for e in result.events],
            "description": result.description,
            "range_high": result.trading_range_high,
            "range_low": result.trading_range_low,
        }
    except Exception as e:
        logger.exception("Wyckoff error")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/options-perps")
async def get_options_perps(req: OptionsPerpsRequest):
    """Options & perps analysis connected to live Binance/OKX perpetual futures feeds."""
    try:
        df_raw = await _data_engine.get_candles(req.symbol, "1d", limit=35)
        if df_raw is None or df_raw.empty:
            raise HTTPException(status_code=404, detail=f"No candle data for {req.symbol}")

        df, data_source, is_synthetic = _prep_df(df_raw, "1d")
        spot_price = float(df["close"].iloc[-1])

        # Realized 30-day annualized volatility
        returns = df["close"].pct_change().dropna()
        hist_vol = float(returns.std() * (365 ** 0.5)) if len(returns) > 1 else 0.5

        # Fetch live perpetual futures metrics (Binance Futures -> OKX Swap fallback)
        perp_snap = await _fetch_live_perp_snapshot(req.symbol, spot_price, df)
        live_funding = perp_snap["funding_8h_pct"]
        live_ls = perp_snap["ls_ratio"]
        live_mark = perp_snap["mark_price"]
        live_oi_trend = perp_snap["oi_trend"]

        result = _options_engine.analyze(
            spot_price=spot_price,
            iv_30d=hist_vol if hist_vol > 0 else 0.5,
            funding_rate_8h=live_funding if live_funding is not None else 0.0,
            long_short_ratio=live_ls if live_ls is not None else 1.0,
            perp_price=live_mark,
            oi_trend=live_oi_trend if live_oi_trend != "UNAVAILABLE" else "STABLE",
        )

        has_live_perp = perp_snap["source"] is not None
        disclaimer = (
            None
            if has_live_perp
            else "Live exchange derivatives feed sedang tidak terjangkau; metrik perpetual ditampilkan sebagai N/A."
        )

        return {
            "symbol": req.symbol.upper(),
            "data_source": data_source,
            "is_synthetic": is_synthetic,
            "perp_source": perp_snap["source"] or "unavailable",
            "spot_price": result.spot_price,
            "mark_price": live_mark,
            "iv_30d_pct": round(result.iv_30d, 2),
            "put_call_ratio": result.put_call_ratio,
            "max_pain": result.max_pain_strike,
            "skew_pct": result.skew,
            "options_bias": result.options_bias,
            "signals": result.signals,
            "confluence_score": result.confluence_score,
            "funding_rate_8h": round(live_funding, 4) if live_funding is not None else None,
            "funding_annualized": result.perp.funding_annualized if (result.perp and live_funding is not None) else None,
            "funding_sentiment": result.perp.funding_sentiment if (result.perp and live_funding is not None) else "UNAVAILABLE",
            "oi_trend": live_oi_trend,
            "open_interest_usd": round(perp_snap["oi_usd"], 2) if perp_snap["oi_usd"] is not None else None,
            "open_interest_coins": round(perp_snap["oi_coins"], 2) if perp_snap["oi_coins"] is not None else None,
            "long_short_ratio": round(live_ls, 3) if live_ls is not None else None,
            "ls_signal": result.perp.ls_signal if (result.perp and live_ls is not None) else "UNAVAILABLE",
            "basis_pct": result.perp.basis_pct if (result.perp and live_mark is not None) else None,
            "carry_signal": result.perp.carry_signal if (result.perp and live_mark is not None) else "FLAT",
            "data_disclaimer": disclaimer,
        }
    except Exception as e:
        logger.exception("Options/Perps error")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mtf-alignment")
async def get_mtf_alignment(req: MTFAlignmentRequest):
    """True Multi-Timeframe Alignment Check (1d, 4h, 1h, 15m, 5m) fetched in parallel."""
    try:
        tfs = ["1d", "4h", "1h", "15m", "5m"]
        raw_dfs = await asyncio.gather(
            *[_data_engine.get_candles(req.symbol, tf, limit=100) for tf in tfs]
        )
        candles_by_tf = {}
        for tf, df_raw in zip(tfs, raw_dfs):
            df, _, _ = _prep_df(df_raw, tf)
            candles_by_tf[tf] = df
            
        result = _mtf_engine.analyze(candles_by_tf, req.symbol)
        return {
            "symbol": req.symbol,
            "dominant_bias": result["dominant_bias"],
            "confirmed": result["confirmed"],
            "confirmation_level": result["confirmation_level"],
            "agreement_score": result["agreement_score"],
            "per_tf": result["per_tf"],
        }
    except Exception as e:
        logger.exception("MTF Alignment error")
        raise HTTPException(status_code=500, detail=str(e))

