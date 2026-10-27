"""
AI Chart Analysis Router — NVIDIA Nemotron SSE Streaming (V4 — Ultimate)
=========================================================================
Architecture:
  MarketDataEngine → Technical Indicators → Confluence Engine → Signal Engine
  + NewsCalendarEngine (berita Forex) + CryptoNewsEngine (berita kripto + DXY)
  + MarketIntelEngine (BTC.D) + SentimentEngine (F&G, Funding Rate, L/S Ratio)
  + QuickAnalyticsEngine (Order Flow Delta, Quick Win Rate) [V4 NEW]
  → Full Market Summary → NVIDIA Nemotron (system+user split) → SSE stream

V4 Upgrades:
  - Order Flow Delta: buy vs sell pressure dari Binance agg trades (no auth)
  - Quick Win Rate: estimasi win rate historis dari data candle lokal
  - Signal Grade (A+/A/B/C) berdasarkan confluence score percentile
  - Long/Short Ratio dari Binance Futures
  - System/User message split untuk konsistensi persona AI
  - Self-Critique section: AI wajib tantang analisisnya sendiri
"""

import asyncio
import json
import logging
import os
import time
import re
from pathlib import Path
from typing import AsyncGenerator, Optional, List

from fastapi import APIRouter, Request, Query, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import get_settings
from app.security import require_api_key, rate_limit
from app.engines.market_data import MarketDataEngine
from app.engines.market_structure import MarketStructureAnalyzer
from app.engines.smart_money import SmartMoneyConceptsEngine
from app.engines.confluence import ConfluenceEngine, MAX_SCORE
from app.engines.news_calendar import NewsCalendarEngine
from app.engines.market_intel import MarketIntelEngine
from app.engines.sentiment import SentimentEngine
from app.engines.crypto_news import CryptoNewsEngine
from app.engines.quick_analytics import QuickAnalyticsEngine
from app.engines.mtf_confirmation import MTFConfirmationEngine
from app.engines.liquidity_sweep import LiquiditySweepEngine
from app.engines.setup_generator import calculate_trade_levels
from app.utils.indicators import (
    calculate_rsi, calculate_ema, calculate_macd,
    calculate_bollinger_bands, calculate_stoch_rsi,
    calculate_vwap, calculate_adx, detect_candle_pattern,
    calculate_volume_profile, detect_divergence,
)
from app.routers.order_flow import _fetch_kline_pressure
from app.engines.order_flow_engine import order_flow_engine

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["AI Analysis"])

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
AI_MODEL_NAME = "deepseek-reasoner"
_RUNTIME_DEEPSEEK_KEY: str = ""


def _resolve_deepseek_key(override_key: Optional[str] = None) -> str:
    """Resolve active DeepSeek API key from request override, runtime memory, .env, or Settings."""
    if override_key and override_key.strip():
        return override_key.strip()
    if _RUNTIME_DEEPSEEK_KEY:
        return _RUNTIME_DEEPSEEK_KEY
    env_k = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if env_k:
        return env_k
    settings = get_settings()
    return (getattr(settings, "DEEPSEEK_API_KEY", "") or "").strip()


def _mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return ""
    return f"{key[:5]}••••{key[-4:]}"


def _persist_deepseek_key_to_env(api_key: str) -> None:
    """Persist DEEPSEEK_API_KEY into backend/.env so it survives server restarts."""
    try:
        env_path = Path(__file__).resolve().parents[2] / ".env"
        lines: list[str] = []
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()
        updated = False
        new_lines = []
        for line in lines:
            if line.strip().startswith("DEEPSEEK_API_KEY="):
                new_lines.append(f"DEEPSEEK_API_KEY={api_key}")
                updated = True
            else:
                new_lines.append(line)
        if not updated:
            new_lines.append(f"DEEPSEEK_API_KEY={api_key}")
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    except Exception as e:
        logger.warning(f"[DeepSeek] Could not write DEEPSEEK_API_KEY to .env: {e}")


def _get_deepseek_client(override_key: Optional[str] = None) -> AsyncOpenAI:
    key = _resolve_deepseek_key(override_key)
    return AsyncOpenAI(
        base_url=DEEPSEEK_BASE_URL,
        api_key=key or "missing-key",
    )

# ──────────────────────────────────────────────────────────────
# Timeframe-Aware In-Memory Cache (Token Saver)
# ──────────────────────────────────────────────────────────────
_AI_CACHE: dict[str, dict] = {}
_AI_CACHE_TTL = 300  # Default fallback TTL (5 minutes)
_AI_CACHE_TTL_BY_TF: dict[str, int] = {
    "1m": 120,
    "5m": 240,
    "15m": 450,
    "30m": 600,
    "1h": 900,
    "4h": 1800,
    "1d": 3600,
}


def _get_tf_ttl(timeframe: str) -> int:
    return _AI_CACHE_TTL_BY_TF.get((timeframe or "1h").lower(), _AI_CACHE_TTL)


def _cache_key(symbol: str, timeframe: str) -> str:
    return f"{symbol.upper()}:{timeframe}"


def _get_cached(symbol: str, timeframe: str) -> Optional[dict]:
    key = _cache_key(symbol, timeframe)
    entry = _AI_CACHE.get(key)
    ttl = _get_tf_ttl(timeframe)
    if entry and (time.time() - entry["ts"]) < ttl:
        return entry["data"]
    return None


def _set_cache(symbol: str, timeframe: str, data: dict):
    key = _cache_key(symbol, timeframe)
    _AI_CACHE[key] = {"data": data, "ts": time.time()}


def _clear_cache(symbol: str = "", timeframe: str = ""):
    """Clear AI cache. If symbol given, clear that pair. Otherwise clear all."""
    if symbol:
        key = _cache_key(symbol, timeframe) if timeframe else None
        if key and key in _AI_CACHE:
            del _AI_CACHE[key]
            return 1
        # Clear all TFs for this symbol
        removed = 0
        prefix = symbol.upper() + ":"
        for k in list(_AI_CACHE.keys()):
            if k.startswith(prefix):
                del _AI_CACHE[k]
                removed += 1
        return removed
    else:
        count = len(_AI_CACHE)
        _AI_CACHE.clear()
        return count


# ──────────────────────────────────────────────────────────────
# Engine singletons
# ──────────────────────────────────────────────────────────────
_data_engine = MarketDataEngine()
_structure_engine = MarketStructureAnalyzer()
_smc_engine = SmartMoneyConceptsEngine()
_confluence_engine = ConfluenceEngine()
_news_engine = NewsCalendarEngine()
_intel_engine = MarketIntelEngine()
_sentiment_engine = SentimentEngine()
_crypto_news_engine = CryptoNewsEngine()
_quick_analytics = QuickAnalyticsEngine()
_mtf_engine = MTFConfirmationEngine()
_sweep_engine = LiquiditySweepEngine()


# ──────────────────────────────────────────────────────────────
# Pydantic models for Chat endpoint
# ──────────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    symbol: str = "BTCUSDT"
    timeframe: str = "1h"
    question: str
    history: List[ChatMessage] = []
    market_context: Optional[dict] = None  # ctx snapshot from /analyze
    api_key: Optional[str] = None


class DeepSeekKeyRequest(BaseModel):
    api_key: str


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
def _safe_float(v, decimals=4) -> Optional[float]:
    """Convert any numeric-ish value to Python float safely."""
    if v is None:
        return None
    try:
        return round(float(v), decimals)
    except Exception:
        return None


def _signal_grade(score: int, max_score: int) -> str:
    """Grade a signal A+/A/B/C based on confluence score percentile."""
    if max_score <= 0:
        return "C"
    pct = (score / max_score) * 100
    if pct >= 80:
        return "A+"
    elif pct >= 65:
        return "A"
    elif pct >= 45:
        return "B"
    return "C"


def _detect_session() -> str:
    """Return detailed trading session name based on UTC hour.
    Sub-divides ASIA session for better crypto timing awareness.
    """
    from datetime import datetime, timezone
    utc_hour = datetime.now(timezone.utc).hour
    if 0 <= utc_hour < 4:
        return "EARLY ASIA (Tokyo Open)"
    elif 4 <= utc_hour < 8:
        return "LATE ASIA (Pre-London)"
    elif 8 <= utc_hour < 12:
        return "LONDON"
    elif 12 <= utc_hour < 16:
        return "LONDON/NEW YORK OVERLAP"
    elif 16 <= utc_hour < 21:
        return "NEW YORK"
    return "OFF-HOURS"


# ──────────────────────────────────────────────────────────────
# Setup level wrapper — delegates to shared canonical function
# from setup_generator.py to ensure AI and Setup Engine levels
# are ALWAYS identical (single source of truth).
# ──────────────────────────────────────────────────────────────
def _calculate_setup_levels(ctx: dict, smc_obj=None, entry_df=None) -> dict:
    """
    Compute trade levels using the SAME canonical algorithm as SetupEngine.
    - smc_obj: raw SmartMoneyAnalysis object (has .order_blocks with .mitigated attr)
    - entry_df: raw DataFrame for swing point detection
    If neither is available, falls back to ctx-based ATR estimate.

    AUDIT FIXES:
    - Fix #1: TP calculated from entry_high/entry_low (not spot price) in BUG FIX blocks
    - Fix #4: Minimum R:R gate of 1.5 enforced post-calculation
    - Fix #11: Returns tp_probability dict for frontend display
    """
    signal = ctx["signal"]
    price = ctx["price"]["current"]
    atr = ctx.get("atr") or ctx.get("indicators", {}).get("atr") or 0

    if signal == "WAIT":
        return {
            "entry_low": None, "entry_high": None,
            "stop_loss": None, "tp1": None, "tp2": None, "tp3": None,
            "risk_reward": None, "atr": atr, "risk_per_unit": None,
            "invalidation_level": None,
            "tp_probability": {"tp1": None, "tp2": None, "tp3": None},
        }

    direction = "BUY" if signal == "BUY" else "SELL"

    if smc_obj is not None and entry_df is not None and not entry_df.empty:
        # Use canonical shared function — same as SetupEngine
        entry_low, entry_high, sl, tp1, tp2, tp3 = calculate_trade_levels(
            direction, price, smc_obj, entry_df
        )
    else:
        # Minimal ATR fallback when SMC object not available
        sl_dist = max(atr * 1.5, price * 0.003) if atr > 0 else price * 0.005
        if direction == "BUY":
            entry_high = price - (atr * 0.3 if atr > 0 else price * 0.001)
            entry_low = price - (atr * 0.8 if atr > 0 else price * 0.003)
            sl = entry_low - sl_dist
            risk = entry_high - sl
            effective_risk = max(risk, atr * 1.0) if atr > 0 else risk
            tp1 = entry_high + effective_risk * 2.0
            tp2 = entry_high + effective_risk * 3.0
            tp3 = entry_high + effective_risk * 4.5
        else:
            entry_low = price + (atr * 0.3 if atr > 0 else price * 0.001)
            entry_high = price + (atr * 0.8 if atr > 0 else price * 0.003)
            sl = entry_high + sl_dist
            risk = sl - entry_low
            effective_risk = max(risk, atr * 1.0) if atr > 0 else risk
            tp1 = entry_low - effective_risk * 2.0
            tp2 = entry_low - effective_risk * 3.0
            tp3 = entry_low - effective_risk * 4.5

    # Trader Pro: Risk dihitung dari worst-case fill (entry_high untuk BUY, entry_low untuk SELL)
    risk = abs(entry_high - sl) if direction == "BUY" else abs(sl - entry_low)
    atr_val = ctx.get("atr") or ctx.get("indicators", {}).get("atr") or 0

    # ── BUG FIX #1: SL must be at minimum 0.5×ATR away from entry. ──
    # If SL ends up too close (calculated from a tiny OB), force it to 1.0×ATR.
    # FIX: TP is now based on entry_high/entry_low, NOT spot price.
    if risk > 0 and atr_val > 0 and risk < atr_val * 0.5:
        logger.warning(f"[SetupLevels] SL too tight ({risk:.6f} < 0.5×ATR={atr_val*0.5:.6f}). Forcing SL to 1.0×ATR.")
        if direction == "BUY":
            sl = entry_low - atr_val * 1.0
        else:
            sl = entry_high + atr_val * 1.0
        risk = abs(entry_high - sl) if direction == "BUY" else abs(sl - entry_low)
        effective_risk = max(risk, atr_val * 1.0)
        if direction == "BUY":
            tp1 = entry_high + effective_risk * 2.0
            tp2 = entry_high + effective_risk * 3.0
            tp3 = entry_high + effective_risk * 4.5
        else:
            tp1 = entry_low - effective_risk * 2.0
            tp2 = entry_low - effective_risk * 3.0
            tp3 = entry_low - effective_risk * 4.5

    rr1 = round(abs(tp1 - entry_high if direction == "BUY" else entry_low - tp1) / risk, 2) if risk > 0 else None

    # ── BUG FIX #1b: Cap R:R at 5.0 — anything above is almost certainly a calculation error. ──
    # FIX: TP recalculated from entry_high/entry_low, not price.
    if rr1 and rr1 > 5.0:
        logger.warning(f"[SetupLevels] R:R={rr1} exceeds cap of 5.0. Resetting to ATR-based SL.")
        if direction == "BUY":
            sl = entry_low - atr_val * 1.0
        else:
            sl = entry_high + atr_val * 1.0
        risk = abs(entry_high - sl) if direction == "BUY" else abs(sl - entry_low)
        effective_risk = max(risk, atr_val * 1.0)
        if direction == "BUY":
            tp1 = entry_high + effective_risk * 2.0
            tp2 = entry_high + effective_risk * 3.0
            tp3 = entry_high + effective_risk * 4.5
        else:
            tp1 = entry_low - effective_risk * 2.0
            tp2 = entry_low - effective_risk * 3.0
            tp3 = entry_low - effective_risk * 4.5
        rr1 = round(abs(tp1 - entry_high if direction == "BUY" else entry_low - tp1) / risk, 2) if risk > 0 else None

    # ── FIX #4: Minimum R:R gate = 1.5. If still below after all fixes, widen TP. ──
    if rr1 is not None and rr1 < 1.5 and risk > 0:
        logger.warning(f"[SetupLevels] R:R={rr1} below minimum 1.5. Widening TP targets.")
        effective_risk = max(risk, atr_val * 1.0) if atr_val > 0 else risk
        if direction == "BUY":
            tp1 = entry_high + effective_risk * 2.0
            tp2 = entry_high + effective_risk * 3.0
            tp3 = entry_high + effective_risk * 4.5
        else:
            tp1 = entry_low - effective_risk * 2.0
            tp2 = entry_low - effective_risk * 3.0
            tp3 = entry_low - effective_risk * 4.5
        rr1 = round(abs(tp1 - entry_high if direction == "BUY" else entry_low - tp1) / risk, 2) if risk > 0 else None

    # ── FIX #10: Invalidation Level — swing beyond SL (pre-entry danger zone) ──
    # For BUY: invalidation = SL - 0.5×ATR (price should not close below here)
    # For SELL: invalidation = SL + 0.5×ATR
    if sl and atr_val > 0:
        invalidation_level = (sl - atr_val * 0.5) if direction == "BUY" else (sl + atr_val * 0.5)
    else:
        invalidation_level = sl

    # ── FIX #11: Dynamic TP Probability based on market conditions ──
    # Instead of hardcoded 75/55/30, adjust based on:
    #   - ADX (trend strength): strong trend = higher TP2/TP3 probability
    #   - RR ratio: tighter RR = higher TP1 probability
    #   - Confluence %: higher confluence = higher all-round probability
    adx_ctx = ctx.get("indicators", {}).get("adx") or 20
    conf_pct_ctx = ctx.get("confluence", {}).get("pct", 50)
    rr_val = rr1 or 2.0

    # Base probabilities
    tp1_base, tp2_base, tp3_base = 70, 50, 25

    # ADX boost: strong trend (ADX > 30) increases extension target hit rate
    if adx_ctx > 35:
        tp1_base += 5; tp2_base += 10; tp3_base += 10
    elif adx_ctx > 25:
        tp2_base += 5; tp3_base += 5
    elif adx_ctx < 18:
        tp2_base -= 10; tp3_base -= 10  # ranging = extensions rarely hit

    # Confluence boost: high confluence setups are statistically stronger
    if conf_pct_ctx >= 70:
        tp1_base += 5; tp2_base += 5; tp3_base += 5
    elif conf_pct_ctx < 35:
        tp1_base -= 10; tp2_base -= 5

    # RR adjustment: very tight RR means TP1 is closer (easier to reach)
    if rr_val < 1.5:
        tp1_base += 5
    elif rr_val > 3.5:
        tp1_base -= 5  # very wide target is harder to reach

    tp_probability = {
        "tp1": max(30, min(90, tp1_base)),
        "tp2": max(20, min(75, tp2_base)),
        "tp3": max(10, min(50, tp3_base)),
    }

    return {
        "entry_low": _safe_float(entry_low),
        "entry_high": _safe_float(entry_high),
        "stop_loss": _safe_float(sl),
        "tp1": _safe_float(tp1),
        "tp2": _safe_float(tp2),
        "tp3": _safe_float(tp3),
        "risk_reward": rr1,
        "atr": _safe_float(atr_val),
        "risk_per_unit": _safe_float(risk),
        "invalidation_level": _safe_float(invalidation_level),
        "tp_probability": tp_probability,
    }


# ──────────────────────────────────────────────────────────────
# Market context builder (V2 — richer engine pipeline)
# ──────────────────────────────────────────────────────────────
async def _build_market_context(symbol: str, timeframe: str) -> dict:
    """
    V3: Runs the full engine pipeline + macro/news data.
    Returns a rich structured market summary.
    Raw candles are NOT sent to the AI.
    """
    # 1. Fetch multi-timeframe candles + macro data (all parallel)
    # FIX #2 (KRITIS): Expand supported TFs to include 30m dan 5m.
    # Sebelumnya: hanya [1d, 4h, 1h, 15m] — user yang pakai 30m/5m di chart
    # selalu dapat analisis 1h (mismatch). Sekarang 30m dan 5m didukung.
    HTF_TIMEFRAMES = ["1d", "4h", "1h", "30m", "15m", "5m"]
    # entry_tf = TF yang dipilih user, selama ada di list. Fallback ke 1h jika tidak dikenal.
    entry_tf = timeframe if timeframe in HTF_TIMEFRAMES else "1h"

    # Parallel fetch: candles + macro + news
    base_coin = symbol.upper().replace("USDT", "").replace("BUSD", "")
    (
        *candle_results,
        forex_news_raw,
        crypto_news_raw,
        btc_dom_raw,
        fng_raw,
        funding_raw,
        dxy_raw,
        ls_ratio_raw,
        order_flow_raw,
    ) = await asyncio.gather(
        *[_data_engine.get_candles_with_source(symbol.upper(), tf, 220) for tf in HTF_TIMEFRAMES],
        _news_engine.get_events(),
        _crypto_news_engine.get_crypto_news(symbol, limit=5),
        _intel_engine.get_btc_dominance(),
        _sentiment_engine.get_fear_and_greed(),
        _sentiment_engine.get_funding_rates([symbol]),
        _crypto_news_engine.get_dxy(),
        _sentiment_engine.get_long_short_ratio(symbol),
        _fetch_kline_pressure(symbol, "15m", 4), # Sprint 1: Whale Intel 1H volume
        return_exceptions=True,
    )
    results = candle_results

    candles_by_tf: dict = {}
    # Sample/synthetic detection is now exact: MarketDataEngine reports which venue
    # produced each frame ("okx" | "binance" | "synthetic"). The old volume-variance
    # heuristic produced false positives on illiquid coins and is gone.
    sample_data_tfs: list = []  # TFs whose candles are synthetic (random walk)
    live_prices_by_tf: dict = {}
    for i, res in enumerate(results):
        tf = HTF_TIMEFRAMES[i]
        if isinstance(res, Exception):
            continue
        df, src = res
        if df is not None and not df.empty:
            if src == "synthetic":
                sample_data_tfs.append(tf)
                logger.warning(f"[AI] Synthetic candles for {symbol}/{tf} (all data sources failed)")
            live_prices_by_tf[tf] = float(df.iloc[-1]["close"])
            # Anti-repaint: drop unclosed forming bar before running structure/SMC/indicators
            closed_df = MarketDataEngine.drop_unclosed(df, tf)
            candles_by_tf[tf] = closed_df if len(closed_df) >= 30 else df

    # Flag sample data di entry TF
    is_sample_data = entry_tf in sample_data_tfs

    if is_sample_data:
        return {"error": (
            f"Data pasar {symbol.upper()} ({entry_tf}) tidak tersedia dari exchange — "
            "yang tersedia hanya data simulasi. Analisis AI dibatalkan agar tidak menyesatkan."
        )}

    entry_df = candles_by_tf.get(entry_tf)
    if entry_df is None or entry_df.empty:
        return {"error": f"Data candle utama ({entry_tf}) tidak tersedia. Analisis dibatalkan."}
        
    if len(candles_by_tf) < 2:
        return {"error": "Data candle tidak cukup (minimal butuh Entry TF + 1 HTF). Analisis dibatalkan."}

    # 1b. Process macro data (graceful fallback if any failed)
    forex_news_list = forex_news_raw if isinstance(forex_news_raw, list) else []
    crypto_news_list = crypto_news_raw if isinstance(crypto_news_raw, list) else []
    btc_dom = btc_dom_raw if isinstance(btc_dom_raw, dict) else {}
    fng = fng_raw if isinstance(fng_raw, dict) else {}
    funding_list = funding_raw if isinstance(funding_raw, list) else []
    dxy = dxy_raw if isinstance(dxy_raw, dict) else {}
    ls_ratio = ls_ratio_raw if isinstance(ls_ratio_raw, dict) else {}
    funding_data = funding_list[0] if funding_list else {}

    # BUG FIX #2: Build order_flow with dynamic interpretation based on whale count
    # kline pressure (buy_pct/sell_pct/delta_usd) comes from _fetch_kline_pressure.
    # If it fails (HF IP block on Futures), fall back to whale count as the signal.
    pressure = order_flow_raw if isinstance(order_flow_raw, dict) else {}
    cached_whales = order_flow_engine.get_cached_whales(symbol.upper())
    whale_buys = [w for w in cached_whales if w.get("tier") == "WHALE" and w.get("side") == "BUY"]
    whale_sells = [w for w in cached_whales if w.get("tier") == "WHALE" and w.get("side") == "SELL"]
    
    # Determine if kline pressure data is valid (not default 50/50)
    buy_pct_raw = pressure.get("buy_pct", 50.0)
    sell_pct_raw = pressure.get("sell_pct", 50.0)
    delta_usd_raw = pressure.get("delta_usd", 0.0)
    kline_valid = (buy_pct_raw != 50.0 or sell_pct_raw != 50.0 or delta_usd_raw != 0.0)
    
    # Build dynamic interpretation
    total_whale = len(whale_buys) + len(whale_sells)
    if total_whale > 0:
        if len(whale_buys) > len(whale_sells) * 1.5:
            whale_interp = f"🐋 Whale dominan BELI ({len(whale_buys)}B vs {len(whale_sells)}S) — potensi akumulasi institusi"
        elif len(whale_sells) > len(whale_buys) * 1.5:
            whale_interp = f"🐋 Whale dominan JUAL ({len(whale_sells)}S vs {len(whale_buys)}B) — distribusi institusi aktif"
        else:
            whale_interp = f"🐋 Whale seimbang ({len(whale_buys)}B / {len(whale_sells)}S) — tidak ada sinyal arah kuat"
    else:
        whale_interp = "Tidak ada whale activity tercatat dalam cache"
    
    if kline_valid:
        kline_interp = f"Kline pressure: Buy {buy_pct_raw}% / Sell {sell_pct_raw}% | {whale_interp}"
    else:
        kline_interp = f"Kline pressure N/A (Futures API diblok dari server) | {whale_interp}"

    order_flow = {
        "buy_pct": round(buy_pct_raw, 1),
        "sell_pct": round(sell_pct_raw, 1),
        "delta_usd": round(delta_usd_raw, 0),
        "whale_buy_count": len(whale_buys),
        "whale_sell_count": len(whale_sells),
        "interpretation": kline_interp,
    }

    # Build full_sentiment dict (same structure as SentimentEngine.get_full_sentiment())
    # so ConfluenceEngine gets the same data as SetupEngine does.
    full_sentiment = {
        "fear_and_greed": fng,
        "market_metrics": funding_list,
    }

    # Filter: only high-impact Forex news (next 24h)
    from datetime import datetime, timezone, timedelta
    now_utc = datetime.now(timezone.utc)
    high_impact_forex = []
    for ev in forex_news_list:
        if ev.get("impact_level", 0) >= 3 and ev.get("relevant_to_crypto"):
            try:
                evt = datetime.fromisoformat(ev["date"])
                if evt.tzinfo is None:
                    evt = evt.replace(tzinfo=timezone.utc)
                if now_utc - timedelta(hours=2) <= evt <= now_utc + timedelta(hours=24):
                    high_impact_forex.append({
                        "title": ev["title"],
                        "currency": ev["currency"],
                        "time": ev.get("time_formatted", ""),
                        "forecast": ev.get("forecast", ""),
                        "previous": ev.get("previous", ""),
                    })
            except Exception:
                pass

    # Funding rate interpretation
    funding_rate = _safe_float(funding_data.get("funding_rate", 0), 6) or 0
    if funding_rate > 0.0005:
        funding_label = "POSITIF TINGGI → risiko long squeeze"
    elif funding_rate < -0.0005:
        funding_label = "NEGATIF → risiko short squeeze"
    else:
        funding_label = "NETRAL"

    # Fear & Greed interpretation
    fng_value = fng.get("value", 50)
    fng_class = fng.get("classification", "Neutral")

    # 2. Market structure analysis (all HTFs, parallel)
    structure_tasks = []
    structure_tfs = []
    for tf, df in candles_by_tf.items():
        structure_tasks.append(asyncio.to_thread(_structure_engine.analyze, df, symbol, tf))
        structure_tfs.append(tf)

    structure_results = await asyncio.gather(*structure_tasks, return_exceptions=True)
    structure_by_tf: dict = {}
    for tf, result in zip(structure_tfs, structure_results):
        if not isinstance(result, Exception):
            structure_by_tf[tf] = result

    entry_structure = structure_by_tf.get(entry_tf) if entry_tf in structure_by_tf else structure_by_tf.get("1h")

    # 3. SMC + ICT Liquidity Sweep analysis on entry TF
    try:
        smc = await asyncio.to_thread(_smc_engine.analyze, entry_df, symbol, entry_tf)
    except Exception as e:
        logger.warning(f"SMC error: {e}")
        smc = None

    try:
        sweep_data = await asyncio.to_thread(_sweep_engine.analyze, entry_df)
    except Exception as e:
        logger.warning(f"LiquiditySweep error: {e}")
        sweep_data = {}

    # 3b. MTF Confirmation (parallel structure results already done above)
    try:
        mtf_result = await asyncio.to_thread(_mtf_engine.analyze, candles_by_tf, symbol.upper())
    except Exception as e:
        logger.warning(f"[AI] MTF confirmation failed: {e}")
        mtf_result = None

    # 4. Confluence scoring — NOW uses full macro data (same as SetupEngine)
    try:
        conf = await asyncio.to_thread(
            _confluence_engine.score,
            candles_by_tf, symbol, entry_tf,
            full_sentiment,   # sentiment_data
            forex_news_list,  # news_events
            mtf_result,       # mtf_result
            None,             # market_intel_data (optional, skip for speed)
        )
        confluence_score = conf.total_score if conf else 0
        max_score = conf.max_score if conf else MAX_SCORE
        conf_details = conf.details if conf else {}
        recommendation = conf.recommendation if conf else "NEUTRAL"
    except Exception as e:
        logger.warning(f"Confluence scoring failed: {e}")
        confluence_score = 0
        max_score = MAX_SCORE
        conf_details = {}
        recommendation = "NEUTRAL"

    # 5. Technical indicators — Full suite (RSI, MACD, Fibonacci as primary; ADX, EMA, Stoch RSI as context)
    from app.utils.indicators import calculate_fibonacci
    try:
        rsi_val = calculate_rsi(entry_df)
        macd_line, signal_line, macd_hist = calculate_macd(entry_df)
        fib_data = calculate_fibonacci(entry_df)

        # Re-activated context indicators (non-primary but valuable for regime + gauges)
        try:
            stoch_k, stoch_d = calculate_stoch_rsi(entry_df)
        except Exception:
            stoch_k = stoch_d = None

        try:
            adx_val = calculate_adx(entry_df)
        except Exception:
            adx_val = None

        try:
            ema200 = calculate_ema(entry_df, 200)
            ema50  = calculate_ema(entry_df, 50)
            ema20  = calculate_ema(entry_df, 20)
        except Exception:
            ema20 = ema50 = ema200 = None

        try:
            bb_upper, bb_mid, bb_lower, bb_bw = calculate_bollinger_bands(entry_df)
        except Exception:
            bb_upper = bb_mid = bb_lower = bb_bw = None

        try:
            vwap_data = calculate_vwap(entry_df) or {}
        except Exception:
            vwap_data = {}

        # ATR calculation (manual since no standalone function in indicators.py)
        if len(entry_df) >= 2:
            _h = entry_df["high"].astype(float).values
            _l = entry_df["low"].astype(float).values
            _c = entry_df["close"].astype(float).values
            _trs = [max(_h[i]-_l[i], abs(_h[i]-_c[i-1]), abs(_l[i]-_c[i-1])) for i in range(1, len(entry_df))]
            atr_val = float(sum(_trs[-14:]) / min(14, len(_trs))) if _trs else None
        else:
            atr_val = None
    except Exception as e:
        logger.warning(f"Indicators error: {e}")
        rsi_val = macd_hist = macd_line = signal_line = fib_data = atr_val = None
        ema20 = ema50 = ema200 = bb_upper = bb_mid = bb_lower = bb_bw = stoch_k = stoch_d = adx_val = None
        vwap_data = {}

    # 5b. Divergence detection — single call returns both RSI & MACD flags
    try:
        div = detect_divergence(entry_df)
    except Exception:
        div = None

    rsi_div = macd_div = None
    if isinstance(div, dict):
        d_type = div.get("type") or "none"
        d_str = f"{d_type} divergence (strength {div.get('strength', 0)})"
        rsi_div = d_str if div.get("rsi_divergence") else None
        macd_div = d_str if div.get("macd_divergence") else None

    # 5c. Candle pattern
    try:
        candle_pattern = detect_candle_pattern(entry_df)
    except Exception:
        candle_pattern = None

    # 5d. Volume profile
    try:
        vp = calculate_volume_profile(entry_df)
        poc = _safe_float(vp.get("poc")) if vp else None
        # BUG FIX #3: volume profile returns 'vah'/'val', not 'va_high'/'va_low'
        va_high = _safe_float(vp.get("vah")) if vp else None
        va_low = _safe_float(vp.get("val")) if vp else None
    except Exception:
        poc = va_high = va_low = None

    # 6. Price data (preserve live ticker price while indicators use closed candle)
    last = entry_df.iloc[-1]
    prev = entry_df.iloc[-2] if len(entry_df) > 1 else last
    closed_close = float(last["close"])
    last_close = float(live_prices_by_tf.get(entry_tf, closed_close))
    last_high = max(float(last["high"]), last_close)
    last_low = min(float(last["low"]), last_close)
    last_volume = float(last["volume"])
    prev_volume = float(prev["volume"])
    volume_change_pct = round((last_volume - prev_volume) / prev_volume * 100, 1) if prev_volume > 0 else 0

    # Volume Profile position & VWAP
    vwap_val = _safe_float(vwap_data.get("vwap")) if isinstance(vwap_data, dict) else None
    if poc and va_high and va_low:
        if last_close > va_high:
            vp_position = "ABOVE_VAH (Bullish Imbalance / Breakout)"
        elif last_close < va_low:
            vp_position = "BELOW_VAL (Bearish Imbalance / Discount)"
        else:
            vp_position = "INSIDE_VA (Fair Value Equilibrium)"
    else:
        vp_position = "UNKNOWN"

    # EMA Stack Alignment (20 / 50 / 200)
    if ema20 and ema50 and ema200:
        if ema20 > ema50 > ema200:
            ema_stack = "BULLISH_STACK (EMA20 > EMA50 > EMA200)"
        elif ema20 < ema50 < ema200:
            ema_stack = "BEARISH_STACK (EMA20 < EMA50 < EMA200)"
        else:
            ema_stack = "MIXED_CROSS"
    else:
        ema_stack = "UNKNOWN"

    # Sprint 2: Market Regime detection (now uses real ADX + EMA200 + BB)
    # FIX #6 (KRITIS): Perbaiki market regime detection.
    # Masalah sebelumnya:
    #   1. bb_bw > 15 = unconditional override TRENDING_BULL/BEAR → hampir selalu HIGH_VOLATILITY di crypto
    #   2. Threshold 15 terlalu rendah untuk crypto (crypto selalu volatile)
    # Fix:
    #   1. bb_bw threshold dinaikkan ke 25 (lebih relevan untuk crypto)
    #   2. HIGH_VOLATILITY hanya di-set jika bb_bw tinggi DAN ADX juga tinggi (trendy AND volatile)
    #   3. Urutan priority: TRENDING > CONSOLIDATING, HIGH_VOLATILITY hanya sebagai modifier
    market_regime = "RANGING"
    adx_num = float(adx_val) if adx_val is not None else 0.0
    ema200_num = float(ema200) if ema200 is not None else None

    if adx_num < 18:
        market_regime = "CONSOLIDATING"
    elif adx_num > 25:
        # ADX kuat → ada trend
        if ema200_num and last_close > ema200_num:
            market_regime = "TRENDING_BULL"
        elif ema200_num and last_close < ema200_num:
            market_regime = "TRENDING_BEAR"
        else:
            market_regime = "TRENDING"
        # HIGH_VOLATILITY hanya jika bb_bw SANGAT tinggi (>25) DAN ada trend kuat
        # Threshold 25 lebih tepat untuk crypto dibanding 15 sebelumnya
        if bb_bw and bb_bw > 25 and adx_num > 30:
            market_regime = "HIGH_VOLATILITY"
    else:
        # ADX antara 18-25: ranging dengan sedikit bias
        market_regime = "RANGING"

    # Sprint 2: Relative Strength vs BTC (using 1d candle)
    rs_vs_btc = "N/A"
    try:
        if "1d" in candles_by_tf and len(candles_by_tf["1d"]) > 1:
            df_1d = candles_by_tf["1d"]
            close_1d = float(df_1d.iloc[-1]["close"])
            prev_1d = float(df_1d.iloc[-2]["close"])
            asset_change_24h = (close_1d - prev_1d) / prev_1d * 100
            btc_change_24h = float(btc_dom.get("market_cap_change_24h_pct") or 0)
            diff = asset_change_24h - btc_change_24h
            if diff > 2:
                rs_vs_btc = f"Outperforming BTC (+{diff:.1f}%)"
            elif diff < -2:
                rs_vs_btc = f"Underperforming BTC ({diff:.1f}%)"
            else:
                rs_vs_btc = f"Neutral vs BTC ({diff:.1f}%)"
    except Exception:
        pass

    # ATR fallback — FIX #2: use single candle range without *2 multiplier
    if atr_val is None:
        atr_val = last_high - last_low

    # 7. Signal direction
    if recommendation in ("STRONG_BUY", "BUY"):
        signal = "BUY"
    elif recommendation in ("STRONG_SELL", "SELL"):
        signal = "SELL"
    else:
        signal = "WAIT"

    # 8. SMC detailed summary
    unmitigated_obs = [ob for ob in (smc.order_blocks if smc else []) if not ob.mitigated]
    unfilled_fvgs = [f for f in (smc.fvgs if smc else []) if not f.filled]
    liq_levels = smc.liquidity_levels if smc else []

    ob_list = [
        {"type": ob.type, "high": _safe_float(ob.high), "low": _safe_float(ob.low)}
        for ob in unmitigated_obs[:5]
    ]
    fvg_list = [
        {"type": f.type, "high": _safe_float(f.high), "low": _safe_float(f.low)}
        for f in unfilled_fvgs[:5]
    ]
    
    # Confluence highlights — V5 (Fibonacci + MACD + RSI as primary signal generators)
    fib_det  = conf_details.get("fibonacci", {})
    macd_det = conf_details.get("macd", {})
    rsi_det  = conf_details.get("rsi", {})
    confluence_highlights = {
        # Signal Generators (12 pts max)
        "fibonacci_near_key_level": bool(fib_det.get("is_near_key_level", False)),
        "macd_momentum_aligned":    bool(macd_det.get("aligned", False)),
        "rsi_zone_aligned":         bool(rsi_det.get("aligned", False)),
        # Context Filters (6 pts max)
        "htf_bias_aligned":         bool(conf_details.get("htf_bias", {}).get("aligned", False)),
        "bos_choch_confirmed":      bool(conf_details.get("structure", {}).get("confirmed", False)),
        "volume_confirmed":         bool(conf_details.get("volume", {}).get("confirmed", False)),
        "session_quality":          bool(conf_details.get("session", {}).get("in_session", False)),
        "news_clear":               bool(conf_details.get("news", {}).get("clear", False)),
    }

    liq_prices = [_safe_float(l.price) for l in liq_levels if hasattr(l, "price")][:10]

    # Recent structure labels (last 8)
    recent_labels = []
    if entry_structure:
        recent_labels = [
            {"label": l.label, "price": _safe_float(l.price, 6)}
            for l in entry_structure.structure_labels[-8:]
        ]

    # HTF biases
    htf_biases = {
        tf: (structure_by_tf[tf].bias if tf in structure_by_tf else "UNKNOWN")
        for tf in ["1d", "4h", "1h", "15m"]
    }

    # Premium/discount zone
    pd_mid = _safe_float(smc.premium_discount_mid if smc and hasattr(smc, "premium_discount_mid") else None)
    pd_zone = "PREMIUM" if pd_mid and last_close > pd_mid else ("DISCOUNT" if pd_mid else "UNKNOWN")

    # Re-align fib_data nearest level & distance with live last_close so AI sees 0 discrepancy
    if isinstance(fib_data, dict) and fib_data.get("retracement_levels") and last_close > 0:
        _ret = fib_data["retracement_levels"]
        if _ret:
            _closest_k, _closest_v = min(_ret.items(), key=lambda kv: abs(float(kv[1]) - last_close))
            _dist_pct = abs(float(_closest_v) - last_close) / last_close * 100.0
            fib_data["nearest_level"] = f"{_closest_k} ({_safe_float(_closest_v)})"
            fib_data["nearest_distance_pct"] = round(_dist_pct, 3)
            fib_data["is_near_key_level"] = bool(_dist_pct <= 0.8 and str(_closest_k) in ("0.382", "0.5", "0.618", "0.786"))

    # Confluence highlights — V5 keys (Fibonacci + MACD + RSI as primary signals)
    fib_det  = conf_details.get("fibonacci", {})
    macd_det = conf_details.get("macd", {})
    rsi_det  = conf_details.get("rsi", {})
    confluence_highlights = {
        # ── Signal Generators (12 pts) ──
        "📐 Fibonacci (dekat level kunci)": bool(fib_det.get("is_near_key_level", False)),
        "📊 MACD (momentum aligned)":        bool(macd_det.get("aligned", False)),
        "📉 RSI (zona optimal)":             bool(rsi_det.get("aligned", False)),
        # ── Context Filters (6 pts) ──
        "🧭 HTF Bias Aligned":              bool(conf_details.get("htf_bias", {}).get("aligned", False)),
        "🏗️ Struktur BOS/CHOCH Confirmed":  bool(conf_details.get("structure", {}).get("confirmed", False)),
        "📦 Volume Confirmation":            bool(conf_details.get("volume", {}).get("confirmed", False)),
        "⏰ Session Quality (London/NY)":    bool(conf_details.get("session", {}).get("in_session", False)),
        "📰 News Clear (no high impact)":   bool(conf_details.get("news", {}).get("clear", False)),
    }

    ctx = {
        "symbol": symbol.upper(),
        "timeframe": entry_tf,
        "session": _detect_session(),
        "price": {
            "current": _safe_float(last_close),
            "high": _safe_float(last_high),
            "low": _safe_float(last_low),
            "volume": _safe_float(last_volume, 2),
            "volume_change_pct": volume_change_pct,
        },
        "htf_biases": htf_biases,
        "entry_bias": entry_structure.bias if entry_structure else "UNKNOWN",
        "signal": signal,
        "confluence": {
            "score": confluence_score,
            "max_score": max_score,
            "pct": round(confluence_score / max_score * 100) if max_score else 0,
            "recommendation": recommendation,
            "highlights": confluence_highlights,
        },
        "indicators": {
            # ── Primary Signal Generators (Fibonacci + MACD + RSI) ──
            "rsi": _safe_float(rsi_val, 1),
            "macd_line": _safe_float(macd_line, 6),
            "macd_signal": _safe_float(signal_line, 6),
            "macd_histogram": _safe_float(macd_hist, 6),
            # Fibonacci levels
            "fib_swing_high": _safe_float(fib_data.get("swing_high")) if fib_data else None,
            "fib_swing_low": _safe_float(fib_data.get("swing_low")) if fib_data else None,
            "fib_direction": fib_data.get("direction") if fib_data else None,
            "fib_price_zone": fib_data.get("price_zone") if fib_data else None,
            "fib_nearest_level": fib_data.get("nearest_level") if fib_data else None,
            "fib_nearest_dist_pct": _safe_float(fib_data.get("nearest_distance_pct"), 3) if fib_data else None,
            "fib_is_near_key": fib_data.get("is_near_key_level") if fib_data else None,
            "fib_retracements": fib_data.get("retracement_levels") if fib_data else {},
            "fib_extensions": fib_data.get("extension_levels") if fib_data else {},
            # ── Context indicators (re-activated: ADX, EMA, Stoch RSI) ──
            "atr": _safe_float(atr_val),
            "adx": _safe_float(adx_val, 1),
            "stoch_k": _safe_float(stoch_k, 1),
            "stoch_d": _safe_float(stoch_d, 1),
            "ema20": _safe_float(ema20),
            "ema50": _safe_float(ema50),
            "ema200": _safe_float(ema200),
            "bb_upper": _safe_float(bb_upper),
            "bb_lower": _safe_float(bb_lower),
            "bb_bandwidth": _safe_float(bb_bw, 2),
            "vwap": vwap_val,
            "poc": poc,
            "va_high": va_high,
            "va_low": va_low,
            "vp_position": vp_position,
            "ema_stack": ema_stack,
            "rsi_divergence": str(rsi_div) if rsi_div else None,
            "macd_divergence": str(macd_div) if macd_div else None,
            "candle_pattern": candle_pattern.get("pattern") if isinstance(candle_pattern, dict) and candle_pattern.get("pattern") else None,
            "market_regime": market_regime,
        },
        "smc": {
            "unmitigated_ob_count": len(unmitigated_obs),
            "unfilled_fvg_count": len(unfilled_fvgs),
            "liquidity_levels_count": len(liq_levels),
            "recent_structure": recent_labels,
            "pd_mid": pd_mid,
            "pd_zone": pd_zone,
            "latest_sweep": sweep_data.get("latest_sweep") if isinstance(sweep_data, dict) else None,
            "bias_from_sweep": sweep_data.get("bias_from_sweep") if isinstance(sweep_data, dict) else None,
            "confirmed_sweeps": sweep_data.get("confirmed_count", 0) if isinstance(sweep_data, dict) else 0,
        },
        # Internal detail for setup level calculation
        "smc_detail": {
            "order_blocks": ob_list,
            "fvg_zones": fvg_list,
            "liquidity_prices": [p for p in liq_prices if p is not None],
        },
        "atr": _safe_float(atr_val),
        # ── V3: Macro & Fundamental data ──────────────────────────
        "macro": {
            "btc_dominance": _safe_float(btc_dom.get("btc_dominance"), 2),
            "eth_dominance": _safe_float(btc_dom.get("eth_dominance"), 2),
            "total_market_cap_b": _safe_float((btc_dom.get("total_market_cap_usd") or 0) / 1e9, 1),
            "market_cap_change_24h": _safe_float(btc_dom.get("market_cap_change_24h_pct"), 2),
            "fear_greed_value": fng_value,
            "fear_greed_label": fng_class,
            "fear_greed_prev": fng.get("previous_value"),
            "funding_rate": funding_rate,
            "funding_label": funding_label,
            "dxy_value": dxy.get("value"),
            "dxy_change_1d": dxy.get("change_pct_1d"),
            "dxy_trend_5d": dxy.get("trend_5d"),
            "dxy_crypto_impact": dxy.get("crypto_impact"),
            # ── V4: Long/Short Ratio ──────────────────────────────
            "ls_ratio": ls_ratio.get("ratio"),
            "ls_long_pct": ls_ratio.get("long_pct"),
            "ls_short_pct": ls_ratio.get("short_pct"),
            "ls_interpretation": ls_ratio.get("interpretation", "N/A"),
            "rs_vs_btc": rs_vs_btc,
        },
        "news": {
            "high_impact_forex": high_impact_forex[:5],
            "crypto_news": [
                {
                    "title": n["title"],
                    "sentiment": n["sentiment"],
                    "source": n.get("source", ""),
                    "url": n.get("url", ""),
                }
                for n in crypto_news_list[:5]
            ],
        },
        # ── V4: Order Flow & Win Rate ─────────────────────────────
        "order_flow": order_flow,
    }

    # Compute win rate using local candle data (no extra API call)
    atr_for_wr = ctx.get("atr") or ctx["indicators"].get("atr") or 0
    rr_for_wr = 2.0
    if atr_for_wr and atr_for_wr > 0:
        win_rate_data = _quick_analytics.estimate_win_rate(
            df=entry_df,
            signal=ctx["signal"],
            atr=float(atr_for_wr),
            risk_reward=rr_for_wr,
            lookback=60,
            symbol=symbol,        # FIX #3: tambah symbol
            timeframe=entry_tf,   # FIX #3: tambah timeframe
        )
    else:
        win_rate_data = _quick_analytics._empty_wr()

    ctx["win_rate"] = win_rate_data

    # FIX #4 (KRITIS): Simpan flag sample data ke ctx agar:
    # 1. Frontend bisa menampilkan warning banner merah
    # 2. AI prompt bisa mendapatkan peringatan data tidak reliable
    ctx["is_sample_data"] = is_sample_data
    ctx["sample_data_tfs"] = sample_data_tfs
    if is_sample_data:
        logger.warning(f"[AI] SAMPLE DATA DETECTED for {symbol}/{entry_tf} — analysis reliability compromised!")

    # Store raw SMC object + entry_df for shared canonical level calculation
    # These are prefixed with _ to indicate they are internal/not serializable
    ctx["_smc_raw"] = smc      # SmartMoneyAnalysis object (has .order_blocks with .mitigated attr)
    ctx["_entry_df_raw"] = entry_df  # raw DataFrame
    
    # Store MTF result for prompt injection
    ctx["_mtf_raw"] = mtf_result

    return ctx


# ──────────────────────────────────────────────────────────────
# Prompt builder (V5 — Token-Efficient, High-Validity Quant Telemetry)
# ──────────────────────────────────────────────────────────────
def _build_prompt(ctx: dict, setup: dict, active_signal: Optional[dict] = None) -> tuple:
    """
    Build a high-density, token-efficient institutional prompt for DeepSeek-R1.
    Strips decorative ASCII bloat (~60% input token reduction) while injecting
    complete quantitative telemetry: EMA20/50/200, Volume Profile (POC/VAH/VAL),
    VWAP, ADX, Fibonacci + OTE, SMC OB/FVG, Liquidity Sweeps, Order Flow & Macro.
    """
    sym = ctx["symbol"]
    tf = ctx["timeframe"]
    price = ctx["price"]["current"]
    vol_chg = ctx["price"].get("volume_change_pct", 0)
    signal = ctx["signal"]
    conf = ctx["confluence"]
    ind = ctx["indicators"]
    smc = ctx["smc"]
    htf = ctx["htf_biases"]
    session = ctx.get("session", "UNKNOWN")
    ob_detail = ctx.get("smc_detail", {}).get("order_blocks", [])
    fvg_detail = ctx.get("smc_detail", {}).get("fvg_zones", [])
    liq_prices = ctx.get("smc_detail", {}).get("liquidity_prices", [])
    grade = _signal_grade(conf["score"], conf["max_score"])

    # Compact structure & SMC strings
    recent_struct = smc.get("recent_structure", [])
    struct_str = " -> ".join([f"{s['label']}@{s['price']}" for s in recent_struct[-6:]]) if recent_struct else "N/A"
    ob_str = "; ".join([f"{ob['type']}[{ob['low']}-{ob['high']}]" for ob in ob_detail[:4]]) if ob_detail else "None"
    fvg_str = "; ".join([f"{f['type']}[{f['low']}-{f['high']}]" for f in fvg_detail[:4]]) if fvg_detail else "None"
    liq_str = ", ".join([str(l) for l in liq_prices[:5]]) if liq_prices else "None"

    # Liquidity Sweep telemetry
    latest_sweep = smc.get("latest_sweep")
    if isinstance(latest_sweep, dict) and latest_sweep:
        sweep_str = (
            f"{latest_sweep.get('sweep_type')} @ {latest_sweep.get('sweep_price')} "
            f"(Pool {latest_sweep.get('pool_type')}={latest_sweep.get('pool_price')}, "
            f"Confirmed={latest_sweep.get('is_confirmed')}, BiasAfter={latest_sweep.get('direction_after')}, "
            f"Grade={latest_sweep.get('signal_grade')})"
        )
    else:
        sweep_str = "None"

    # Fibonacci & ICT OTE (0.618 - 0.786)
    fib_ret = ind.get("fib_retracements") or {}
    fib_ext = ind.get("fib_extensions") or {}
    ret_str = " | ".join([f"{k}:{v}" for k, v in sorted(fib_ret.items(), key=lambda x: float(x[0]))]) if fib_ret else "N/A"
    ext_str = " | ".join([f"{k}:{v}" for k, v in sorted(fib_ext.items(), key=lambda x: float(x[0]))]) if fib_ext else "N/A"
    ote_low = fib_ret.get("0.618") or fib_ret.get(0.618)
    ote_high = fib_ret.get("0.786") or fib_ret.get(0.786)
    ote_str = f"{ote_low} - {ote_high}" if (ote_low and ote_high) else "N/A"

    # Confluence checklist compact
    passed_checks = [k for k, v in conf.get("highlights", {}).items() if v]
    failed_checks = [k for k, v in conf.get("highlights", {}).items() if not v]

    # Macro, Order Flow & Win Rate
    macro = ctx.get("macro", {})
    news_data = ctx.get("news", {})
    of_data = ctx.get("order_flow", {})
    wr_data = ctx.get("win_rate", {})
    wr_str = (
        f"{wr_data.get('win_rate')}% ({wr_data.get('wins',0)}W/{wr_data.get('losses',0)}L, n={wr_data.get('total_trades',0)})"
        if wr_data.get("win_rate") is not None else "N/A"
    )

    # High-impact news (only include if present to save tokens)
    fx_news = news_data.get("high_impact_forex") or []
    crypto_news = news_data.get("crypto_news") or []
    news_lines = []
    for n in fx_news[:3]:
        news_lines.append(f"FX[{n.get('currency')}]: {n.get('title')} @{n.get('time','?')} (Fcst:{n.get('forecast','-')})")
    for n in crypto_news[:3]:
        news_lines.append(f"CRYPTO[{n.get('sentiment')}]: {n.get('title')}")
    news_str = " ; ".join(news_lines) if news_lines else "Clear (No High-Impact News)"

    # Setup & Active DB Signal
    if signal != "WAIT":
        setup_str = (
            f"Direction={signal} | EntryZone={setup.get('entry_low')}..{setup.get('entry_high')} | "
            f"SL={setup.get('stop_loss')} (Invalidation={setup.get('invalidation_level')}, ATR={setup.get('atr')}) | "
            f"TP1={setup.get('tp1')} (RR={setup.get('risk_reward')}:1, Prob={setup.get('tp_probability',{}).get('tp1')}%) | "
            f"TP2={setup.get('tp2')} | TP3={setup.get('tp3')}"
        )
    else:
        setup_str = f"WAIT (Confluence={conf['score']}/{conf['max_score']} [{conf['pct']}%] belum memenuhi syarat eksekusi langsung)"

    active_str = ""
    if active_signal:
        active_str = (
            f"\n[ACTIVE_DB_SIGNAL] Dir={active_signal.get('direction')} | "
            f"Entry={active_signal.get('entry_low')}..{active_signal.get('entry_high')} | "
            f"SL={active_signal.get('stop_loss')} | TP1={active_signal.get('tp1')} | Score={active_signal.get('score')}"
        )

    sample_warn = ""
    if ctx.get("is_sample_data"):
        sample_warn = f"\n⚠️ PERINGATAN: Data candle {sym} mengandung sample data pada TF {ctx.get('sample_data_tfs')}. Hindari rekomendasi posisi agresif.\n"

    system_msg = (
        "Kamu adalah Principal Quantitative & ICT/SMC Prop Trader.\n"
        "ATURAN MUTLAK BAHASA & EFISIENSI PENALARAN (THINKING):\n"
        "1. WAJIB gunakan 100% Bahasa Indonesia baik di dalam proses berpikir internal (reasoning_content) maupun pada laporan akhir. DILARANG menggunakan Bahasa Inggris di dalam reasoning_content.\n"
        "2. Di dalam internal reasoning (Chain-of-Thought), DILARANG KERAS menyalin/mengabsen ulang angka dari prompt. Cukup tulis maksimal 5 poin evaluasi singkat (maksimal 150 kata), lalu SEGERA tulis jawaban final.\n"
        "3. Pada laporan final, WAJIB konsisten dengan angka telemetri (sebutkan angka spesifik harga, EMA20/50/200, POC/VAH/VAL, Fib/OTE, OB/FVG, RSI, MACD, SL/TP).\n"
        "4. Jika sinyal engine BUY/SELL tetapi ada kontradiksi fatal (misal: ADX<18 ranging berat, counter-HTF tanpa Liquidity Sweep, atau harga tepat di resistance VAH/OB lawan), beri peringatan tegas."
    )

    if signal == "WAIT":
        plan_instruction = (
            "Karena sinyal saat ini **WAIT**, jabarkan secara spesifik:\n"
            "- **Skenario BUY Trigger:** Harga harus sweep/reclaim level berapa (sebutkan Fib/OB/VAL spesifik) + syarat konfirmasi RSI/MACD.\n"
            "- **Skenario SELL Trigger:** Harga harus reject/breakdown level berapa (sebutkan Fib/OB/VAH spesifik) + syarat invalidasi."
        )
    else:
        plan_instruction = (
            f"Validasi level eksekusi **{signal}** dari engine (atau beri penyesuaian presisi jika perlu):\n"
            f"- **Entry Zone:** {setup.get('entry_low')} – {setup.get('entry_high')} (jelaskan konfluensi Fib/OB/FVG/POC di zona ini)\n"
            f"- **Stop Loss & Invalidation:** SL {setup.get('stop_loss')} | Batal total di {setup.get('invalidation_level')}\n"
            f"- **Target Profit:** TP1 {setup.get('tp1')} (R:R {setup.get('risk_reward')}:1) | TP2 {setup.get('tp2')} | TP3 {setup.get('tp3')}\n"
            f"- **Position Sizing & Trigger:** Rekomendasi risiko (% ekuitas) sesuai Grade {grade} ({conf['pct']}%) dan konfirmasi candle entry."
        )

    user_msg = f"""Analisis telemetri kuantitatif real-time untuk **{sym} ({tf.upper()})**:{sample_warn}

[1. PRICE, REGIME & VOLUME PROFILE]
- Price: {price} | VolChg: {vol_chg:+.1f}% | Session: {session}
- Regime: {ind.get('market_regime')} | ADX(14): {ind.get('adx')} | ATR(14): {ctx.get('atr')} | BB_BW: {ind.get('bb_bandwidth')}%
- EMA Stack: {ind.get('ema_stack')} (EMA20={ind.get('ema20')}, EMA50={ind.get('ema50')}, EMA200={ind.get('ema200')})
- Volume Profile: POC={ind.get('poc')} | VAH={ind.get('va_high')} | VAL={ind.get('va_low')} | Pos={ind.get('vp_position')} | VWAP={ind.get('vwap')}

[2. MULTI-TIMEFRAME & CONFLUENCE ENGINE]
- Engine Signal: {signal} | Grade: {grade} | Score: {conf['score']}/{conf['max_score']} ({conf['pct']}%) [{conf['recommendation']}]
- HTF Bias: 1D={htf.get('1d')} | 4H={htf.get('4h')} | 1H={htf.get('1h')} | 15M={htf.get('15m')} | EntryTF({tf.upper()})={ctx.get('entry_bias')}
- MTF Aligned: {ctx.get('_mtf_raw', {}).get('aligned', False) if isinstance(ctx.get('_mtf_raw'), dict) else 'N/A'} | RS vs BTC: {macro.get('rs_vs_btc')}
- Confluence Passed: {', '.join(passed_checks) if passed_checks else 'None'}
- Confluence Missing: {', '.join(failed_checks) if failed_checks else 'None'}

[3. FIBONACCI, ICT OTE & SMART MONEY (SMC)]
- Fib Swing ({ind.get('fib_direction')}): Low={ind.get('fib_swing_low')} -> High={ind.get('fib_swing_high')} | Zone={ind.get('fib_price_zone')}
- Nearest Fib: {ind.get('fib_nearest_level')} (dist {ind.get('fib_nearest_dist_pct')}%, NearKey={ind.get('fib_is_near_key')}) | ICT OTE(0.618-0.786): {ote_str}
- Fib Retracements: {ret_str}
- Fib Extensions: {ext_str}
- SMC PD Zone: {smc.get('pd_zone')} (Equilibrium Mid={smc.get('pd_mid')}) | Recent Structure: {struct_str}
- Active OBs ({smc.get('unmitigated_ob_count')}): {ob_str}
- Unfilled FVGs ({smc.get('unfilled_fvg_count')}): {fvg_str}
- Liquidity Pools: {liq_str}
- Liquidity Sweep: {sweep_str}

[4. MOMENTUM, ORDER FLOW & MACRO]
- RSI(14): {ind.get('rsi')} (Div: {ind.get('rsi_divergence') or 'None'}) | StochRSI: K={ind.get('stoch_k')}/D={ind.get('stoch_d')}
- MACD(12,26,9): Line={ind.get('macd_line')}, Sig={ind.get('macd_signal')}, Hist={ind.get('macd_histogram')} (Div: {ind.get('macd_divergence') or 'None'})
- Candle Pattern: {ind.get('candle_pattern') or 'None'}
- Order Flow: Buy={of_data.get('buy_pct')}%/Sell={of_data.get('sell_pct')}% | Delta=${of_data.get('delta_usd',0):,.0f} | Whales={of_data.get('whale_buy_count',0)}B/{of_data.get('whale_sell_count',0)}S | HistWinRate={wr_str}
- Macro: BTC.D={macro.get('btc_dominance')}% | F&G={macro.get('fear_greed_value')}({macro.get('fear_greed_label')}) | Funding={macro.get('funding_rate')}({macro.get('funding_label')}) | L/S={macro.get('ls_ratio')}({macro.get('ls_interpretation')}) | DXY={macro.get('dxy_value')}({macro.get('dxy_crypto_impact')})
- News(24h): {news_str}

[5. ENGINE TRADE PLAN]{active_str}
- {setup_str}

Tulis laporan analisis dalam **5 bagian padat & tajam** menggunakan format heading persis berikut:

### 1. 🔍 Struktur, Rezim & Volume Profile
Evaluasi keselarasan HTF (1D/4H/1H/15M), posisi harga terhadap EMA20/50/200, kekuatan tren ADX, serta posisi harga terhadap Volume Profile (POC, VAH, VAL) dan VWAP (3-4 kalimat padat dengan angka spesifik).

### 2. 🎯 Konfluensi Kuantitatif (Fibonacci OTE, SMC & Momentum)
Bedah validitas sinyal **{signal}**: posisi harga terhadap Fibonacci / zona OTE (0.618-0.786), keberadaan Order Block / FVG / Liquidity Sweep terdekat, serta sinkronisasi momentum RSI, MACD, dan Order Flow/Whale.

### 3. 📐 Rencana Trading & Eksekusi Presisi
{plan_instruction}

### 4. ⚠️ Skenario Gagal & Titik Invalidasi (Devil's Advocate)
Sebutkan 2 risiko utama yang dapat menggagalkan tesis ini (termasuk risiko makro/funding/squeeze) dan sebutkan **3 kondisi/level harga spesifik** yang membatalkan setup secara mutlak.

### 5. 🔑 Kesimpulan Eksekutif
Satu paragraf ringkas (maksimal 3 kalimat): keputusan tegas (**{signal}** / Grade **{grade}**), level kunci yang wajib dipantau, dan eksekusi terbaik saat ini.
"""

    return system_msg, user_msg


# ──────────────────────────────────────────────────────────────
# SSE generator — V2 with richer events
# ──────────────────────────────────────────────────────────────
async def _stream_ai_analysis(
    symbol: str,
    timeframe: str,
    request: Request,
    force: bool = False,
    api_key: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    V2 SSE events:
      status       — pipeline progress
      market_data  — full computed market context (JSON) [NEW]
      context      — summary indicators snapshot (JSON)
      setup_data   — engine-calculated trade levels (JSON) [IMPROVED]
      reasoning    — AI thinking tokens (streaming)
      token        — AI answer tokens (streaming)
      done         — stream complete
      error        — error message
    """

    def sse(event: str, data: str) -> str:
        escaped = data.replace("\n", "\\n")
        return f"event: {event}\ndata: {escaped}\n\n"

    # ── 1. Cache check (Timeframe-aware TTL saves DeepSeek tokens) ──
    cached = None if force else _get_cached(symbol, timeframe)
    if cached and len((cached.get("answer_summary") or "").strip()) >= 200:
        yield sse("status", "cache_hit")
        yield sse("context", json.dumps(cached.get("context_snapshot", {})))
        yield sse("setup_data", json.dumps(cached["setup"]))
        if cached.get("reasoning_summary"):
            yield sse("reasoning", cached["reasoning_summary"])
        yield sse("token", cached.get("answer_summary", ""))
        yield sse("analyzed_at", json.dumps({"ts": cached.get("ts", time.time())}))
        yield sse("done", "cached")
        return

    # ── 2. Engine pipeline ──
    yield sse("status", "computing_indicators")
    try:
        ctx = await _build_market_context(symbol, timeframe)
    except Exception as e:
        logger.error(f"Market context error: {e}")
        yield sse("error", f"Failed to compute market context: {e}")
        return

    if "error" in ctx:
        yield sse("error", ctx["error"])
        return

    # ── 3. Engine-calculated setup levels (before AI) ──
    yield sse("status", "indicators_ready")

    context_snapshot = {
        "signal": ctx["signal"],
        "confluence_score": ctx["confluence"]["score"],
        "max_score": ctx["confluence"]["max_score"],
        "confluence_pct": ctx["confluence"]["pct"],
        "htf_biases": ctx["htf_biases"],
        "entry_bias": ctx["entry_bias"],
        "session": ctx.get("session"),
        "indicators": ctx["indicators"],
        "smc": ctx["smc"],
        "macro": ctx.get("macro", {}),
        "news": ctx.get("news", {}),
        "order_flow": ctx.get("order_flow", {}),
        # FIX #4: Include sample data flag
        "is_sample_data": ctx.get("is_sample_data", False),
        "sample_data_tfs": ctx.get("sample_data_tfs", []),
    }
    yield sse("context", json.dumps(context_snapshot))

    # Calculate precise levels from engines (shared canonical function)
    # smc_raw and entry_df_raw are stored in ctx by _build_market_context
    setup_levels = _calculate_setup_levels(
        ctx,
        smc_obj=ctx.get("_smc_raw"),
        entry_df=ctx.get("_entry_df_raw"),
    )

    # Merge full setup object
    conf_pct = ctx["confluence"]["pct"]
    if conf_pct >= 70:
        confidence = "HIGH"
    elif conf_pct >= 45:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # Signal grade for frontend badge
    signal_grade = _signal_grade(ctx["confluence"]["score"], ctx["confluence"]["max_score"])

    full_setup = {
        "symbol": ctx["symbol"],
        "timeframe": ctx["timeframe"],
        "signal": ctx["signal"],
        "confidence": confidence,
        "signal_grade": signal_grade,  # NEW: A+/A/B/C grade badge
        "confluence_score": ctx["confluence"]["score"],
        "max_score": ctx["confluence"]["max_score"],
        "confluence_pct": conf_pct,
        "signal_score_pct": conf_pct,
        "recommendation": ctx["confluence"]["recommendation"],
        "session": ctx.get("session"),
        "entry": setup_levels.get("entry_low"),
        "entry_low": setup_levels.get("entry_low"),
        "entry_high": setup_levels.get("entry_high"),
        "stop_loss": setup_levels.get("stop_loss"),
        "tp1": setup_levels.get("tp1"),
        "tp2": setup_levels.get("tp2"),
        "tp3": setup_levels.get("tp3"),
        "risk_reward": setup_levels.get("risk_reward"),
        "atr": setup_levels.get("atr"),
        "risk_per_unit": setup_levels.get("risk_per_unit"),
        "invalidation_level": setup_levels.get("invalidation_level"),
        "tp_probability": setup_levels.get("tp_probability", {"tp1": None, "tp2": None, "tp3": None}),
        "htf_biases": ctx["htf_biases"],
        "indicators": ctx["indicators"],
        "smc": ctx["smc"],
        "highlights": ctx["confluence"]["highlights"],
        # NEW: Win rate estimate from QuickAnalyticsEngine
        "win_rate": ctx.get("win_rate", {}),
        # FIX #4: Sample data flag for frontend warning banner
        "is_sample_data": ctx.get("is_sample_data", False),
        "sample_data_tfs": ctx.get("sample_data_tfs", []),
    }

    # Emit setup data IMMEDIATELY (before AI thinks)
    yield sse("setup_data", json.dumps(full_setup))

    # ── 4. Query active DB signal to inject into prompt for coherence ──
    active_signal_ctx = None
    try:
        from app.database import SessionLocal
        from app.models.trade_setup import TradeSetup
        from datetime import datetime, timedelta
        _db = SessionLocal()
        try:
            _cutoff = datetime.utcnow() - timedelta(hours=24)
            _active = (
                _db.query(TradeSetup)
                .filter(
                    TradeSetup.symbol == symbol.upper(),
                    TradeSetup.timeframe == timeframe,
                    TradeSetup.status == "ACTIVE",
                    TradeSetup.created_at >= _cutoff,
                )
                .order_by(TradeSetup.created_at.desc())
                .first()
            )
            if _active:
                active_signal_ctx = {
                    "direction": _active.direction,
                    "entry_low": _active.entry_low,
                    "entry_high": _active.entry_high,
                    "stop_loss": _active.stop_loss,
                    "tp1": _active.take_profit_1,
                    "tp2": _active.take_profit_2,
                    "score": _active.confluence_score,
                    "setup_type": _active.setup_type,
                    "created_at": str(_active.created_at),
                }
                logger.info(f"[AI] Found active DB signal for {symbol}/{timeframe}: {_active.direction}")
        finally:
            _db.close()
    except Exception as e:
        logger.warning(f"[AI] DB signal lookup failed: {e}")

    # ── 5. Stream DeepSeek-R1 (deepseek-reasoner) ──
    active_ds_key = _resolve_deepseek_key(api_key)
    if not active_ds_key:
        yield sse(
            "error",
            "DEEPSEEK_KEY_MISSING: API Key DeepSeek belum diatur. Klik ikon 🔑 di sudut kanan atas panel DeepSeek Agent untuk memasukkan API Key Anda.",
        )
        return

    yield sse("status", "ai_thinking")

    system_msg, user_msg = _build_prompt(ctx, setup_levels, active_signal=active_signal_ctx)
    full_reasoning = ""
    full_answer = ""

    t_start_ai = time.time()
    # IMPORTANT: In deepseek-reasoner, max_tokens is the COMBINED ceiling of reasoning_content + content.
    # Setting 6000 ensures reasoning_content never truncates or starves the final Indonesian report.
    target_max_tokens = 6000
    max_retries = 3
    for attempt in range(max_retries):
        try:
            client = _get_deepseek_client(active_ds_key)
            stream = await client.chat.completions.create(
                model=AI_MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=target_max_tokens,
                stream=True,
            )

            async for chunk in stream:
                if await request.is_disconnected():
                    logger.info(f"[DeepSeek-R1] Client disconnected — stopping stream for {symbol}/{timeframe}")
                    await stream.close()
                    return

                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    full_reasoning += reasoning
                    yield sse("reasoning", reasoning)

                if delta.content:
                    full_answer += delta.content
                    yield sse("token", delta.content)

            # Safety fallback: if deepseek-reasoner finished with empty/truncated content, complete with deepseek-chat
            if len(full_answer.strip()) < 150:
                logger.warning(f"[DeepSeek-R1] Answer too short ({len(full_answer)} chars); completing via deepseek-chat fallback")
                fb_stream = await client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                    max_tokens=2500,
                    temperature=0.3,
                    stream=True,
                )
                async for fb_chunk in fb_stream:
                    if not fb_chunk.choices:
                        continue
                    fb_delta = fb_chunk.choices[0].delta
                    if fb_delta.content:
                        full_answer += fb_delta.content
                        yield sse("token", fb_delta.content)

            break

        except Exception as e:
            logger.error(f"[DeepSeek-R1] API error on attempt {attempt + 1}: {e}")
            err_str = str(e)
            if "401" in err_str or "Authentication" in err_str or "invalid_api_key" in err_str.lower():
                yield sse("error", "API Key DeepSeek tidak valid (401 Unauthorized). Silakan periksa kembali API Key Anda melalui tombol 🔑.")
                return
            if "402" in err_str or "Insufficient Balance" in err_str:
                yield sse("error", "Saldo akun DeepSeek API tidak mencukupi (402 Insufficient Balance).")
                return
            if attempt == max_retries - 1:
                yield sse("error", f"DeepSeek-R1 error setelah {max_retries} percobaan: {err_str[:160]}")
                return
            await asyncio.sleep(2 ** (attempt + 1))
            
    t_end_ai = time.time()
    logger.info(f"[AI] AI generation for {symbol} took {t_end_ai - t_start_ai:.2f}s")

    # ── 5a. Shadow Tracking (False Negative from AI Filter) ──
    if "VERDICT: WAIT" in full_answer.upper() and ctx["signal"] in ["BUY", "SELL"] and ctx["confluence"]["score"] >= 60:
        try:
            from app.database import SessionLocal
            from app.models.shadow_setup import ShadowSetup
            _db_shadow = SessionLocal()
            try:
                # Extract simple reason string from the reasoning or answer (first 200 chars)
                reason_snippet = full_reasoning[-500:] if full_reasoning else full_answer[:500]
                shadow = ShadowSetup(
                    symbol=symbol.upper(),
                    direction=ctx["signal"],
                    entry_low=setup_levels.get("entry_low") or 0,
                    entry_high=setup_levels.get("entry_high") or 0,
                    stop_loss=setup_levels.get("stop_loss") or 0,
                    take_profit_1=setup_levels.get("tp1") or 0,
                    risk_reward=setup_levels.get("risk_reward") or 0,
                    confluence_score=ctx["confluence"]["score"],
                    timeframe=timeframe,
                    reason=f"AI rejected high-score {ctx['signal']}. Snippet: {reason_snippet}",
                )
                _db_shadow.add(shadow)
                _db_shadow.commit()
                logger.info(f"[AI] ShadowSetup logged for {symbol} (AI chose WAIT on score {ctx['confluence']['score']})")
            finally:
                _db_shadow.close()
        except Exception as e:
            logger.error(f"[AI] Failed to save ShadowSetup: {e}")

    # ── 5b. Cache full result + reasoning ONLY if answer is complete ──
    _now_ts = time.time()
    if len(full_answer.strip()) >= 200:
        _set_cache(symbol, timeframe, {
            "context_snapshot": context_snapshot,
            "setup": full_setup,
            "reasoning_summary": full_reasoning,
            "answer_summary": full_answer,
            "ts": _now_ts,
        })

    # ── 5c. Save AI Signal to DB & Trigger Telegram Alert ──
    if signal_grade in ["A+", "A"] and ctx["signal"] in ["BUY", "SELL"]:
        try:
            from app.database import SessionLocal
            from app.models.ai_signal_result import AISignalResult
            from app.services.telegram_bot import send_telegram_ai_signal
            import asyncio
            
            _db_ai = SessionLocal()
            try:
                ai_result = AISignalResult(
                    symbol=symbol.upper(),
                    timeframe=timeframe,
                    direction=ctx["signal"],
                    grade=signal_grade,
                    confluence_pct=conf_pct,
                    entry_low=setup_levels.get("entry_low") or 0,
                    entry_high=setup_levels.get("entry_high") or 0,
                    stop_loss=setup_levels.get("stop_loss") or 0,
                    tp1=setup_levels.get("tp1") or 0,
                    tp2=setup_levels.get("tp2"),
                    tp3=setup_levels.get("tp3"),
                    status="ACTIVE"
                )
                _db_ai.add(ai_result)
                _db_ai.commit()
                logger.info(f"[AI] Saved Grade {signal_grade} signal to ai_signal_results")
                
                # Send async telegram alert
                asyncio.create_task(send_telegram_ai_signal(full_setup))
            finally:
                _db_ai.close()
        except Exception as e:
            logger.error(f"[AI] Failed to save/alert AI Signal: {e}")

    yield sse("analyzed_at", json.dumps({"ts": _now_ts}))
    yield sse("done", "complete")


# ──────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────
@router.get("/deepseek-status")
async def get_deepseek_status():
    """Check whether a DeepSeek API key is configured on the backend."""
    key = _resolve_deepseek_key()
    return {
        "configured": bool(key),
        "masked_key": _mask_key(key),
        "model": AI_MODEL_NAME,
        "provider": "deepseek",
    }


@router.post("/deepseek-key", dependencies=[Depends(rate_limit("deepseek-key", 10))])
async def set_deepseek_key(req: DeepSeekKeyRequest):
    """Save DeepSeek API Key in runtime memory and backend/.env for immediate use."""
    global _RUNTIME_DEEPSEEK_KEY
    cleaned = (req.api_key or "").strip()
    if not cleaned or len(cleaned) < 10:
        raise HTTPException(status_code=400, detail="Format DeepSeek API Key tidak valid.")
    _RUNTIME_DEEPSEEK_KEY = cleaned
    os.environ["DEEPSEEK_API_KEY"] = cleaned
    _persist_deepseek_key_to_env(cleaned)
    _clear_cache()
    return {
        "status": "ok",
        "configured": True,
        "masked_key": _mask_key(cleaned),
        "model": AI_MODEL_NAME,
    }


@router.get("/analyze", dependencies=[Depends(rate_limit("ai-analyze", 20))])
async def analyze_chart(
    request: Request,
    symbol: str = Query("BTCUSDT", description="Trading pair, e.g. BTCUSDT"),
    timeframe: str = Query("1h", description="Timeframe: 1m, 5m, 15m, 1h, 4h, 1d"),
    force: bool = Query(False, description="Force re-analysis, bypass cache"),
    api_key: Optional[str] = Query(None, description="Optional DeepSeek API key override"),
):
    """
    Stream AI chart analysis via Server-Sent Events.

    V3: Full macro + news context included in analysis.
    Engine-calculated setup levels are emitted BEFORE the AI analysis.

    Events emitted:
      status      — pipeline progress
      context     — computed indicators + macro + news snapshot (JSON)
      setup_data  — engine trade levels (JSON) — emitted BEFORE AI
      reasoning   — AI thinking tokens (streaming)
      token       — AI analysis tokens (streaming)
      done        — stream complete
      error       — error message
    """
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Access-Control-Allow-Origin": "*",
    }
    header_key = request.headers.get("X-DeepSeek-Key") or api_key
    return StreamingResponse(
        _stream_ai_analysis(symbol.upper(), timeframe, request, force=force, api_key=header_key),
        media_type="text/event-stream",
        headers=headers,
    )


@router.delete("/cache", dependencies=[Depends(require_api_key)])
async def clear_ai_cache(
    symbol: str = Query("", description="Symbol to clear (empty = clear all)"),
    timeframe: str = Query("", description="Timeframe to clear (empty = all TFs for symbol)"),
):
    """Clear the in-memory AI analysis cache. Supports per-symbol clearing."""
    removed = _clear_cache(symbol, timeframe)
    return {"message": f"Cleared {removed} cache entries", "cache_size": len(_AI_CACHE)}


@router.get("/cache/status")
async def cache_status():
    """Show current cache status."""
    now = time.time()
    entries = []
    for key, entry in _AI_CACHE.items():
        age = round(now - entry["ts"])
        entries.append({"key": key, "age_seconds": age, "ttl_remaining": max(0, _AI_CACHE_TTL - age)})
    return {"cache_entries": entries, "ttl_seconds": _AI_CACHE_TTL}


# ──────────────────────────────────────────────────────────────
# Chat Interaktif Endpoint (V3)
# ──────────────────────────────────────────────────────────────
async def _stream_chat(req: ChatRequest) -> AsyncGenerator[str, None]:
    """SSE generator for interactive AI chat with market context."""

    def sse(event: str, data: str) -> str:
        escaped = data.replace("\n", "\\n")
        return f"event: {event}\ndata: {escaped}\n\n"

    settings = get_settings()

    # Build compact, high-validity system context from market context or cached analysis
    ctx = req.market_context or {}
    cached_entry = _get_cached(req.symbol, req.timeframe)
    if not ctx and cached_entry:
        ctx = cached_entry.get("context_snapshot", {})
    cached_setup = cached_entry.get("setup", {}) if cached_entry else {}

    macro = ctx.get("macro", {})
    indicators = ctx.get("indicators", {})
    smc = ctx.get("smc", {})
    signal = ctx.get("signal", cached_setup.get("signal", "UNKNOWN"))
    score = ctx.get("confluence_score") or (ctx.get("confluence", {}) if isinstance(ctx.get("confluence"), dict) else {}).get("score", 0)
    max_score = ctx.get("max_score") or (ctx.get("confluence", {}) if isinstance(ctx.get("confluence"), dict) else {}).get("max_score", MAX_SCORE)

    system_prompt = (
        f"Kamu adalah Principal Quant & SMC Trader yang mendampingi user pada chart {req.symbol.upper()} ({req.timeframe.upper()}).\n"
        f"TELEMETRI REAL-TIME:\n"
        f"- Signal: {signal} (Score {score}/{max_score}) | Session: {ctx.get('session', 'N/A')} | Regime: {indicators.get('market_regime', 'N/A')}\n"
        f"- HTF Bias: {ctx.get('htf_biases', {})} | EntryBias: {ctx.get('entry_bias', 'N/A')}\n"
        f"- Setup Levels: Entry={cached_setup.get('entry_low')}..{cached_setup.get('entry_high')} | SL={cached_setup.get('stop_loss')} | TP1={cached_setup.get('tp1')} | TP2={cached_setup.get('tp2')} | RR={cached_setup.get('risk_reward')}\n"
        f"- EMA/VP: {indicators.get('ema_stack', 'N/A')} (EMA20={indicators.get('ema20')}, EMA50={indicators.get('ema50')}, EMA200={indicators.get('ema200')}) | POC={indicators.get('poc')} | VAH={indicators.get('va_high')} | VAL={indicators.get('va_low')}\n"
        f"- Fib & SMC: NearestFib={indicators.get('fib_nearest_level')} ({indicators.get('fib_price_zone')}) | PD={smc.get('pd_zone')} | OBs={smc.get('unmitigated_ob_count', 0)} | FVGs={smc.get('unfilled_fvg_count', 0)} | Sweep={smc.get('bias_from_sweep')}\n"
        f"- Momentum & Macro: RSI={indicators.get('rsi')} | MACD_Hist={indicators.get('macd_histogram')} | ADX={indicators.get('adx')} | BTC.D={macro.get('btc_dominance')}% | F&G={macro.get('fear_greed_value')} | Funding={macro.get('funding_rate')}\n"
        f"ATURAN: Jawab langsung ke inti pertanyaan dengan Bahasa Indonesia tajam, mengacu pada angka di atas, maksimal 2-3 paragraf singkat agar hemat token."
    )

    active_ds_key = _resolve_deepseek_key(req.api_key)
    if not active_ds_key:
        yield sse("token", "⚠️ API Key DeepSeek belum diatur. Silakan klik tombol 🔑 di bagian atas panel untuk memasukkan API Key DeepSeek Anda.")
        yield sse("done", "complete")
        return

    # Build messages array with strict user/assistant alternation required by deepseek-reasoner
    messages = [{"role": "system", "content": system_prompt}]
    sanitized_history: list[dict] = []
    for msg in req.history[-6:]:
        role = "user" if msg.role == "user" else "assistant"
        content = (msg.content or "").strip()
        if not content or content.startswith("⚠️"):
            continue
        if not sanitized_history and role != "user":
            continue
        if sanitized_history and sanitized_history[-1]["role"] == role:
            sanitized_history[-1]["content"] += "\n" + content
        else:
            sanitized_history.append({"role": role, "content": content})

    # Ensure last history item before new user question is "assistant"
    if sanitized_history and sanitized_history[-1]["role"] == "user":
        sanitized_history.pop()

    messages.extend(sanitized_history)
    messages.append({"role": "user", "content": req.question})

    yield sse("status", "thinking")

    t_start_chat = time.time()
    max_retries = 3
    for attempt in range(max_retries):
        try:
            client = _get_deepseek_client(active_ds_key)
            stream = await client.chat.completions.create(
                model=AI_MODEL_NAME,
                messages=messages,
                max_tokens=3500,
                stream=True,
            )

            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    yield sse("token", delta.content)

            break

        except Exception as e:
            logger.error(f"[DeepSeek-R1] Chat error on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                yield sse("error", f"DeepSeek-R1 error: {str(e)[:200]}")
                return
            await asyncio.sleep(2 ** (attempt + 1))
            
    t_end_chat = time.time()
    logger.info(f"[AI] Chat generation took {t_end_chat - t_start_chat:.2f}s")

    yield sse("done", "complete")


@router.post("/chat", dependencies=[Depends(require_api_key), Depends(rate_limit("ai-chat", 30))])
async def chat_with_ai(req: ChatRequest):
    """
    Interactive chat endpoint — continue conversation after /analyze.
    
    Request body:
      symbol, timeframe — trading pair and timeframe
      question — trader's question (in any language, AI answers in Indonesian)
      history — previous chat messages (max 10)
      market_context — context snapshot from the /analyze response
    
    Returns SSE stream with events: status, token, done, error
    """
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Access-Control-Allow-Origin": "*",
    }
    return StreamingResponse(
        _stream_chat(req),
        media_type="text/event-stream",
        headers=headers,
    )
