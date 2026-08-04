"""
AI Chart Analysis Router — NVIDIA Nemotron SSE Streaming (V3 — Ultimate)
=========================================================================
Architecture:
  MarketDataEngine → Technical Indicators → Confluence Engine → Signal Engine
  + NewsCalendarEngine (berita Forex) + CryptoNewsEngine (berita kripto)
  + MarketIntelEngine (BTC.D) + SentimentEngine (F&G, Funding Rate) + DXY
  → Full Market Summary → NVIDIA Nemotron → SSE stream

V3 Upgrades:
  - Integrasi berita kripto real-time dari CryptoPanic
  - Analisis DXY (US Dollar Index) dari Yahoo Finance
  - BTC Dominance, Fear & Greed, Funding Rate, Open Interest masuk ke prompt
  - Endpoint baru: POST /api/v1/ai/chat (chat interaktif lanjutan)
  - Macro context dikirim ke frontend sebagai event terpisah
"""

import asyncio
import json
import logging
import time
import re
from typing import AsyncGenerator, Optional, List

from fastapi import APIRouter, Request, Query, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import get_settings
from app.engines.market_data import MarketDataEngine
from app.engines.market_structure import MarketStructureAnalyzer
from app.engines.smart_money import SmartMoneyConceptsEngine
from app.engines.confluence import ConfluenceEngine
from app.engines.news_calendar import NewsCalendarEngine
from app.engines.market_intel import MarketIntelEngine
from app.engines.sentiment import SentimentEngine
from app.engines.crypto_news import CryptoNewsEngine
from app.utils.indicators import (
    calculate_rsi, calculate_ema, calculate_macd,
    calculate_bollinger_bands, calculate_stoch_rsi,
    calculate_vwap, calculate_adx, detect_candle_pattern,
    calculate_volume_profile, detect_divergence,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["AI Analysis"])

# ──────────────────────────────────────────────────────────────
# In-Memory Cache (90s TTL)
# ──────────────────────────────────────────────────────────────
_AI_CACHE: dict[str, dict] = {}
_AI_CACHE_TTL = 90  # seconds


def _cache_key(symbol: str, timeframe: str) -> str:
    return f"{symbol.upper()}:{timeframe}"


def _get_cached(symbol: str, timeframe: str) -> Optional[dict]:
    key = _cache_key(symbol, timeframe)
    entry = _AI_CACHE.get(key)
    if entry and (time.time() - entry["ts"]) < _AI_CACHE_TTL:
        return entry["data"]
    return None


def _set_cache(symbol: str, timeframe: str, data: dict):
    key = _cache_key(symbol, timeframe)
    _AI_CACHE[key] = {"data": data, "ts": time.time()}


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


def _detect_session() -> str:
    """Return current trading session name based on UTC hour."""
    from datetime import datetime, timezone
    utc_hour = datetime.now(timezone.utc).hour
    if 8 <= utc_hour < 12:
        return "LONDON"
    elif 12 <= utc_hour < 16:
        return "LONDON/NEW_YORK (OVERLAP)"
    elif 16 <= utc_hour < 21:
        return "NEW_YORK"
    elif 0 <= utc_hour < 8:
        return "ASIA"
    return "OFF-HOURS"


# ──────────────────────────────────────────────────────────────
# Engine-based setup level calculator (NO AI fallback needed)
# ──────────────────────────────────────────────────────────────
def _calculate_setup_levels(ctx: dict) -> dict:
    """
    Calculate precise entry, SL, and TP levels using:
    - ATR for stop distance
    - Nearest OB zone for entry
    - Liquidity levels for TP targets
    - R:R ratio enforced at minimum 1.5
    """
    signal = ctx["signal"]
    price = ctx["price"]["current"]
    atr = ctx.get("atr", 0)
    smc = ctx.get("smc_detail", {})

    if signal == "WAIT":
        return {
            "entry_low": None, "entry_high": None,
            "stop_loss": None, "tp1": None, "tp2": None, "tp3": None,
            "risk_reward": None, "atr": atr,
        }

    # Default SL distance: 1.5× ATR (institutional stop placement)
    sl_dist = max(atr * 1.5, price * 0.003)  # min 0.3% away

    # Try to use OB zone as tighter entry
    entry_low = price
    entry_high = price

    obs = smc.get("order_blocks", [])
    if signal == "BUY" and obs:
        bullish_obs = [ob for ob in obs if ob.get("type") == "BULLISH"]
        if bullish_obs:
            # Nearest bullish OB below current price
            valid = [ob for ob in bullish_obs if ob["high"] < price]
            if valid:
                nearest = max(valid, key=lambda o: o["high"])
                entry_low = nearest["low"]
                entry_high = nearest["high"]
                # Tighter SL: just below OB
                sl_dist = price - nearest["low"] + atr * 0.3
    elif signal == "SELL" and obs:
        bearish_obs = [ob for ob in obs if ob.get("type") == "BEARISH"]
        if bearish_obs:
            valid = [ob for ob in bearish_obs if ob["low"] > price]
            if valid:
                nearest = min(valid, key=lambda o: o["low"])
                entry_low = nearest["low"]
                entry_high = nearest["high"]
                sl_dist = nearest["high"] - price + atr * 0.3

    # SL placement
    if signal == "BUY":
        sl = round(price - sl_dist, 6)
    else:
        sl = round(price + sl_dist, 6)

    risk = abs(price - sl)
    if risk <= 0:
        risk = atr * 0.5 or price * 0.002

    # TP levels: 1.8R, 3.0R, 5.0R (using liquidity levels if available)
    liq_levels = smc.get("liquidity_prices", [])

    if signal == "BUY":
        tp1_default = round(price + risk * 1.8, 6)
        tp2_default = round(price + risk * 3.0, 6)
        tp3_default = round(price + risk * 5.0, 6)
        # Snap TP to nearest liquidity above current price
        above_liq = [l for l in liq_levels if l > price]
        if len(above_liq) >= 1:
            above_liq.sort()
            tp1 = above_liq[0] if abs(above_liq[0] - tp1_default) / price < 0.03 else tp1_default
            tp2 = above_liq[1] if len(above_liq) >= 2 else tp2_default
            tp3 = above_liq[2] if len(above_liq) >= 3 else tp3_default
        else:
            tp1, tp2, tp3 = tp1_default, tp2_default, tp3_default
    else:  # SELL
        tp1_default = round(price - risk * 1.8, 6)
        tp2_default = round(price - risk * 3.0, 6)
        tp3_default = round(price - risk * 5.0, 6)
        below_liq = [l for l in liq_levels if l < price]
        if len(below_liq) >= 1:
            below_liq.sort(reverse=True)
            tp1 = below_liq[0] if abs(below_liq[0] - tp1_default) / price < 0.03 else tp1_default
            tp2 = below_liq[1] if len(below_liq) >= 2 else tp2_default
            tp3 = below_liq[2] if len(below_liq) >= 3 else tp3_default
        else:
            tp1, tp2, tp3 = tp1_default, tp2_default, tp3_default

    rr1 = round(abs(tp1 - price) / risk, 2) if risk > 0 else None

    return {
        "entry_low": _safe_float(entry_low),
        "entry_high": _safe_float(entry_high),
        "stop_loss": _safe_float(sl),
        "tp1": _safe_float(tp1),
        "tp2": _safe_float(tp2),
        "tp3": _safe_float(tp3),
        "risk_reward": rr1,
        "atr": _safe_float(atr),
        "risk_per_unit": _safe_float(risk),
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
    HTF_TIMEFRAMES = ["1d", "4h", "1h", "15m"]
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
    ) = await asyncio.gather(
        *[_data_engine.get_candles(symbol.upper(), tf, 200) for tf in HTF_TIMEFRAMES],
        _news_engine.get_events(),
        _crypto_news_engine.get_crypto_news(symbol, limit=5),
        _intel_engine.get_btc_dominance(),
        _sentiment_engine.get_fear_and_greed(),
        _sentiment_engine.get_funding_rates([symbol]),
        _crypto_news_engine.get_dxy(),
        return_exceptions=True,
    )
    results = candle_results

    candles_by_tf: dict = {}
    for i, df in enumerate(results):
        if not isinstance(df, Exception) and not df.empty:
            candles_by_tf[HTF_TIMEFRAMES[i]] = df

    entry_df = candles_by_tf.get(entry_tf) if entry_tf in candles_by_tf else candles_by_tf.get("1h")
    if entry_df is None or entry_df.empty:
        return {"error": "No candle data available"}

    # 1b. Process macro data (graceful fallback if any failed)
    forex_news_list = forex_news_raw if isinstance(forex_news_raw, list) else []
    crypto_news_list = crypto_news_raw if isinstance(crypto_news_raw, list) else []
    btc_dom = btc_dom_raw if isinstance(btc_dom_raw, dict) else {}
    fng = fng_raw if isinstance(fng_raw, dict) else {}
    funding_list = funding_raw if isinstance(funding_raw, list) else []
    dxy = dxy_raw if isinstance(dxy_raw, dict) else {}
    funding_data = funding_list[0] if funding_list else {}

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

    # 3. SMC analysis on entry TF
    try:
        smc = await asyncio.to_thread(_smc_engine.analyze, entry_df, symbol, entry_tf)
    except Exception as e:
        logger.warning(f"SMC error: {e}")
        smc = None

    # 4. Confluence scoring
    try:
        conf = await asyncio.to_thread(
            _confluence_engine.score,
            candles_by_tf, symbol, entry_tf,
            None, None, None, None,
        )
        confluence_score = conf.total_score
        max_score = conf.max_score
        conf_details = conf.details
        recommendation = conf.recommendation
    except Exception as e:
        logger.warning(f"Confluence scoring failed: {e}")
        confluence_score = 0
        max_score = 33
        conf_details = {}
        recommendation = "NEUTRAL"

    # 5. Technical indicators
    try:
        rsi_val = calculate_rsi(entry_df)
        ema20 = calculate_ema(entry_df, 20)
        ema50 = calculate_ema(entry_df, 50)
        ema200 = calculate_ema(entry_df, 200)
        macd_line, signal_line, macd_hist = calculate_macd(entry_df)
        bb_upper, bb_mid, bb_lower, bb_bw = calculate_bollinger_bands(entry_df)
        stoch_k, stoch_d = calculate_stoch_rsi(entry_df)
        vwap_data = calculate_vwap(entry_df)
        adx_val = calculate_adx(entry_df)
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
        rsi_val = ema20 = ema50 = ema200 = macd_hist = macd_line = signal_line = None
        bb_upper = bb_mid = bb_lower = bb_bw = stoch_k = stoch_d = adx_val = atr_val = None
        vwap_data = {}

    # 5b. Divergence detection
    try:
        rsi_div = detect_divergence(entry_df, "rsi")
        macd_div = detect_divergence(entry_df, "macd")
    except Exception:
        rsi_div = macd_div = None

    # 5c. Candle pattern
    try:
        candle_pattern = detect_candle_pattern(entry_df)
    except Exception:
        candle_pattern = None

    # 5d. Volume profile
    try:
        vp = calculate_volume_profile(entry_df)
        poc = _safe_float(vp.get("poc")) if vp else None
        va_high = _safe_float(vp.get("va_high")) if vp else None
        va_low = _safe_float(vp.get("va_low")) if vp else None
    except Exception:
        poc = va_high = va_low = None

    # 6. Price data
    last = entry_df.iloc[-1]
    prev = entry_df.iloc[-2] if len(entry_df) > 1 else last
    last_close = float(last["close"])
    last_high = float(last["high"])
    last_low = float(last["low"])
    last_volume = float(last["volume"])
    prev_volume = float(prev["volume"])
    volume_change_pct = round((last_volume - prev_volume) / prev_volume * 100, 1) if prev_volume > 0 else 0

    # ATR fallback
    if atr_val is None:
        atr_val = (last_high - last_low) * 2

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

    # Confluence highlights (force bool for JSON serialization)
    confluence_highlights = {
        "htf_bias_aligned": bool(conf_details.get("htf_bias", {}).get("aligned", False)),
        "liquidity_swept": bool(conf_details.get("liquidity", {}).get("swept", False)),
        "in_order_block": bool(conf_details.get("order_block", {}).get("in_zone", False)),
        "fvg_present": bool(conf_details.get("fvg", {}).get("present", False)),
        "bos_choch_confirmed": bool(conf_details.get("structure", {}).get("confirmed", False)),
        "rsi_aligned": bool(conf_details.get("rsi", {}).get("aligned", False)),
        "ema_aligned": bool(conf_details.get("ema", {}).get("aligned", False)),
        "macd_aligned": bool(conf_details.get("macd", {}).get("aligned", False)),
        "stoch_rsi_aligned": bool(conf_details.get("stoch_rsi", {}).get("aligned", False)),
        "volume_confirmed": bool(conf_details.get("volume", {}).get("confirmed", False)),
        "vwap_aligned": bool(conf_details.get("vwap", {}).get("aligned", False)),
        "premium_discount_correct": bool(conf_details.get("premium_discount", {}).get("correct", False)),
        "session_quality": bool(conf_details.get("session_quality", {}).get("active", False)),
        "support_resistance_aligned": bool(conf_details.get("support_resistance_aligned", {}).get("aligned", False)),
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
            "rsi": _safe_float(rsi_val, 1),
            "ema20": _safe_float(ema20),
            "ema50": _safe_float(ema50),
            "ema200": _safe_float(ema200),
            "macd_line": _safe_float(macd_line, 6),
            "macd_signal": _safe_float(signal_line, 6),
            "macd_histogram": _safe_float(macd_hist, 6),
            "bb_upper": _safe_float(bb_upper),
            "bb_mid": _safe_float(bb_mid),
            "bb_lower": _safe_float(bb_lower),
            "bb_bandwidth": _safe_float(bb_bw, 4),
            "stoch_k": _safe_float(stoch_k, 1),
            "stoch_d": _safe_float(stoch_d, 1),
            "adx": _safe_float(adx_val, 1),
            "atr": _safe_float(atr_val),
            "vwap": _safe_float(vwap_data.get("vwap")) if vwap_data else None,
            "vwap_position": vwap_data.get("position") if vwap_data else None,
            "rsi_divergence": str(rsi_div) if rsi_div else None,
            "macd_divergence": str(macd_div) if macd_div else None,
            "candle_pattern": candle_pattern.get("pattern") if isinstance(candle_pattern, dict) and candle_pattern.get("pattern") else None,
            "volume_profile_poc": poc,
            "va_high": va_high,
            "va_low": va_low,
        },
        "smc": {
            "unmitigated_ob_count": len(unmitigated_obs),
            "unfilled_fvg_count": len(unfilled_fvgs),
            "liquidity_levels_count": len(liq_levels),
            "recent_structure": recent_labels,
            "pd_mid": pd_mid,
            "pd_zone": pd_zone,
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
        },
        "news": {
            "high_impact_forex": high_impact_forex[:5],
            "crypto_news": [
                {
                    "title": n["title"],
                    "sentiment": n["sentiment"],
                    "source": n.get("source", ""),
                }
                for n in crypto_news_list[:5]
            ],
        },
    }

    return ctx


# ──────────────────────────────────────────────────────────────
# Prompt builder (V2 — Expert, 15-section)
# ──────────────────────────────────────────────────────────────
def _build_prompt(ctx: dict, setup: dict) -> str:
    """Build a comprehensive expert prompt from the full market context."""
    sym = ctx["symbol"]
    tf = ctx["timeframe"]
    price = ctx["price"]["current"]
    signal = ctx["signal"]
    conf = ctx["confluence"]
    ind = ctx["indicators"]
    smc = ctx["smc"]
    htf = ctx["htf_biases"]
    highlights = conf["highlights"]
    recent_struct = smc.get("recent_structure", [])
    session = ctx.get("session", "UNKNOWN")
    ob_detail = ctx.get("smc_detail", {}).get("order_blocks", [])
    fvg_detail = ctx.get("smc_detail", {}).get("fvg_zones", [])
    liq_prices = ctx.get("smc_detail", {}).get("liquidity_prices", [])

    # Format structure
    struct_str = " → ".join([f"{s['label']}@{s['price']}" for s in recent_struct]) if recent_struct else "N/A"

    # Format confluence checklist
    hi_lines = []
    for k, v in highlights.items():
        emoji = "✅" if v else "❌"
        label = k.replace("_", " ").title()
        hi_lines.append(f"  {emoji} {label}")
    hi_str = "\n".join(hi_lines)

    # Format OBs
    ob_str = "\n".join([
        f"  • {ob['type']} OB: {ob['low']} – {ob['high']}"
        for ob in ob_detail
    ]) if ob_detail else "  No active Order Blocks"

    # Format FVGs
    fvg_str = "\n".join([
        f"  • {f['type']} FVG: {f['low']} – {f['high']}"
        for f in fvg_detail
    ]) if fvg_detail else "  No unfilled FVGs"

    # Format liquidity
    liq_str = ", ".join([str(l) for l in liq_prices[:5]]) if liq_prices else "N/A"

    # Format macro data
    macro = ctx.get("macro", {})
    news_data = ctx.get("news", {})
    btc_d = macro.get("btc_dominance")
    fng_val = macro.get("fear_greed_value")
    fng_lbl = macro.get("fear_greed_label", "N/A")
    fng_prev = macro.get("fear_greed_prev")
    fund_rate = macro.get("funding_rate", 0)
    fund_lbl = macro.get("funding_label", "N/A")
    dxy_val = macro.get("dxy_value")
    dxy_chg = macro.get("dxy_change_1d")
    dxy_impact = macro.get("dxy_crypto_impact", "N/A")
    total_mcap = macro.get("total_market_cap_b")
    mcap_chg = macro.get("market_cap_change_24h")

    fng_trend = ""
    if fng_prev and fng_val:
        diff = fng_val - fng_prev
        fng_trend = f" ({'↑' if diff > 0 else '↓'}{abs(diff)} dari kemarin)"

    # Format forex news
    if news_data.get("high_impact_forex"):
        fx_lines = "\n".join([
            f"  ⚠️ [{n['currency']}] {n['title']} | {n.get('time','?')} | Forecast: {n.get('forecast','N/A')} | Prev: {n.get('previous','N/A')}"
            for n in news_data["high_impact_forex"]
        ])
    else:
        fx_lines = "  Tidak ada berita High Impact Forex dalam 24 jam ke depan"

    # Format crypto news
    if news_data.get("crypto_news"):
        crypto_lines = "\n".join([
            f"  {'🟢' if n['sentiment']=='POSITIF' else '🔴' if n['sentiment']=='NEGATIF' else '⚪'} [{n['sentiment']}] {n['title']} — {n.get('source','')}"
            for n in news_data["crypto_news"]
        ])
    else:
        crypto_lines = "  Data berita kripto tidak tersedia"

    # Format setup levels
    if signal != "WAIT":
        setup_block = f"""  • Entry Zone: {setup.get('entry_low')} – {setup.get('entry_high')}
  • Stop Loss:  {setup.get('stop_loss')} (risk: {setup.get('risk_per_unit')} / ATR: {setup.get('atr')})
  • TP1:        {setup.get('tp1')} (R:R {setup.get('risk_reward')}:1)
  • TP2:        {setup.get('tp2')}
  • TP3:        {setup.get('tp3')}"""
    else:
        setup_block = "  Signal is WAIT — no trade setup generated."

    # HTF alignment summary
    aligned_count = sum(1 for b in htf.values() if
        (b == "BULLISH" and signal == "BUY") or
        (b == "BEARISH" and signal == "SELL"))
    total_htf = len([b for b in htf.values() if b != "UNKNOWN"])

    # Indicator summary
    rsi_label = (
        "Overbought" if (ind.get("rsi") or 50) > 70 else
        "Oversold" if (ind.get("rsi") or 50) < 30 else
        "Neutral"
    )
    ema_trend = (
        "Bullish (above EMA200)" if price > (ind.get("ema200") or price) else
        "Bearish (below EMA200)"
    )
    macd_mom = "Bullish" if (ind.get("macd_histogram") or 0) > 0 else "Bearish"

    vol_chg = ctx["price"].get("volume_change_pct", 0)
    vol_label = f"{'+' if vol_chg >= 0 else ''}{vol_chg}% vs previous candle"

    prompt = f"""You are a senior institutional trading analyst specializing in Smart Money Concepts (SMC/ICT), multi-timeframe analysis, and quantitative technical analysis. Your role is to provide a professional, actionable trade analysis — not to replace the signal engine, but to explain, contextualize, and add depth to it.

═══════════════════════════════════════════
MARKET SNAPSHOT — {sym} / {tf.upper()}
═══════════════════════════════════════════
Current Price:     {price}
Session:           {session}
Engine Signal:     {signal}
Confluence Score:  {conf['score']}/{conf['max_score']} ({conf['pct']}%) — {conf['recommendation']}
HTF Alignment:     {aligned_count}/{total_htf} timeframes aligned with {signal}

─── MULTI-TIMEFRAME BIAS ───────────────────
  Daily (1D):  {htf.get('1d', 'N/A')}
  4-Hour (4H): {htf.get('4h', 'N/A')}
  1-Hour (1H): {htf.get('1h', 'N/A')}
  15-Min (15M):{htf.get('15m', 'N/A')}

─── MARKET STRUCTURE ───────────────────────
  Market Bias:      {ctx['entry_bias']}
  Structure Labels: {struct_str}
  Premium/Discount: Price in {smc.get('pd_zone', 'N/A')} zone (mid: {smc.get('pd_mid', 'N/A')})

─── SMART MONEY CONCEPTS (SMC/ICT) ─────────
  Active Order Blocks ({smc['unmitigated_ob_count']}):
{ob_str}

  Unfilled Fair Value Gaps ({smc['unfilled_fvg_count']}):
{fvg_str}

  Key Liquidity Levels: {liq_str}
  Total Liquidity Points: {smc['liquidity_levels_count']}

─── TECHNICAL INDICATORS ───────────────────
  RSI(14):      {ind.get('rsi', 'N/A')} → {rsi_label}
  EMA Trend:    {ema_trend}
  EMA20/50/200: {ind.get('ema20', 'N/A')} / {ind.get('ema50', 'N/A')} / {ind.get('ema200', 'N/A')}
  MACD:         Histogram {ind.get('macd_histogram', 'N/A')} → {macd_mom} momentum
  Bollinger BB: Upper={ind.get('bb_upper','N/A')} | Mid={ind.get('bb_mid','N/A')} | Lower={ind.get('bb_lower','N/A')} | BW={ind.get('bb_bandwidth','N/A')}
  Stoch RSI:    K={ind.get('stoch_k','N/A')} D={ind.get('stoch_d','N/A')}
  ADX:          {ind.get('adx', 'N/A')} ({'Strong trend' if (ind.get('adx') or 0) > 25 else 'Weak/ranging'})
  ATR:          {ind.get('atr', 'N/A')}
  VWAP:         {ind.get('vwap','N/A')} (Price is {ind.get('vwap_position','N/A')} VWAP)

─── VOLUME ANALYSIS ────────────────────────
  Current Volume: {ctx['price']['volume']} ({vol_label})
  Volume Confirmation: {'✅ YES' if highlights.get('volume_confirmed') else '❌ NO'}
  Vol Profile POC: {ind.get('volume_profile_poc', 'N/A')} | VA: {ind.get('va_low','N/A')} – {ind.get('va_high','N/A')}

─── DIVERGENCE & PATTERNS ──────────────────
  RSI Divergence:  {ind.get('rsi_divergence', 'None detected')}
  MACD Divergence: {ind.get('macd_divergence', 'None detected')}
  Candle Pattern:  {ind.get('candle_pattern', 'None detected')}

─── ANALISIS MAKRO & CROSS-ASSET ───────────
  BTC Dominance:   {btc_d}% {"(tinggi, altcoin tertekan)" if btc_d and btc_d > 52 else "(rendah, altcoin season)" if btc_d and btc_d < 45 else ""}
  Total Market Cap:{total_mcap}B USD ({f"+{mcap_chg}%" if mcap_chg and mcap_chg > 0 else f"{mcap_chg}%" if mcap_chg else "N/A"} 24h)
  DXY:             {f"{dxy_val} ({'+' if dxy_chg and dxy_chg > 0 else ''}{dxy_chg}% 1d, tren 5d: {macro.get('dxy_trend_5d','N/A')})" if dxy_val else "N/A"}
  DXY Impact:      {dxy_impact}
  Fear & Greed:    {fng_val}/100 — {fng_lbl}{fng_trend}
  Funding Rate:    {fund_rate:+.6f} → {fund_lbl}

─── BERITA HIGH IMPACT FOREX (24 JAM) ──────
{fx_lines}

─── BERITA KRIPTO TERKINI ──────────────────
{crypto_lines}

─── CONFLUENCE CHECKLIST ───────────────────
{hi_str}

─── ENGINE-CALCULATED SETUP LEVELS ─────────
{setup_block}

═══════════════════════════════════════════
TASK: WRITE YOUR ANALYSIS
═══════════════════════════════════════════

Using ALL the data above as your foundation, provide an expert-level trading analysis IN INDONESIAN (Bahasa Indonesia). Be specific, precise, and reference actual price levels and indicator values.

---

### 1. 📊 Narasi Pasar
In 3–4 sentences, describe the current market structure in Indonesian. Reference the SMC sequence (liquidity sweep → displacement → OB formation → BOS/CHOCH). Use specific price levels from the data above.

### 2. 🎯 Justifikasi Sinyal
Explain the **{signal}** signal in depth in Indonesian. Which 3–4 confluence factors carry the most weight? How do they reinforce each other? What is the institutional narrative behind this setup?

### 3. 📐 Setup Trading
Confirm or refine the engine-calculated levels. Be explicit in Indonesian:
- **Bias:** {signal}
- **Area Entry:** [price range — be specific]
- **Stop Loss:** [level] — [reason: below OB / below swing low / beyond invalidation level]
- **TP1:** [level] — [reason: liquidity target / FVG fill / resistance]
- **TP2:** [level] — [reason]
- **TP3:** [level] — [reason: major liquidity / HTF target]
- **R:R Ratio:** [ratio]
- **Manajemen Risiko:** [how much risk given {conf['pct']}% confidence]

### 4. ⚠️ Risiko & Pembatalan
List 3 concrete price levels or events that would INVALIDATE this setup in Indonesian:
1. [specific level + reason]
2. [specific level + reason]  
3. [specific level + reason]

### 5. ⏰ Waktu & Eksekusi
- **Waktu terbaik:** Based on the {session} session and current structure
- **Konfirmasi:** What should traders see before entering? (candle close, volume, retest?)
- **Kadaluarsa Setup:** When does this setup become invalid?

### 6. 🔑 Kesimpulan
One powerful sentence summarizing the setup in Indonesian: signal, conviction level, and key condition to watch.

---
END_OF_ANALYSIS"""

    return prompt


# ──────────────────────────────────────────────────────────────
# SSE generator — V2 with richer events
# ──────────────────────────────────────────────────────────────
async def _stream_ai_analysis(
    symbol: str,
    timeframe: str,
    request: Request,
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

    # ── 1. Cache check ──
    cached = _get_cached(symbol, timeframe)
    if cached:
        yield sse("status", "cache_hit")
        yield sse("context", json.dumps(cached.get("context_snapshot", {})))
        yield sse("setup_data", json.dumps(cached["setup"]))
        yield sse("token", cached.get("answer_summary", ""))
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
    }
    yield sse("context", json.dumps(context_snapshot))

    # Calculate precise levels from engines
    setup_levels = _calculate_setup_levels(ctx)

    # Merge full setup object
    conf_pct = ctx["confluence"]["pct"]
    if conf_pct >= 70:
        confidence = "HIGH"
    elif conf_pct >= 45:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    full_setup = {
        "symbol": ctx["symbol"],
        "timeframe": ctx["timeframe"],
        "signal": ctx["signal"],
        "confidence": confidence,
        "confluence_score": ctx["confluence"]["score"],
        "max_score": ctx["confluence"]["max_score"],
        "confluence_pct": conf_pct,
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
        "htf_biases": ctx["htf_biases"],
        "indicators": ctx["indicators"],
        "smc": ctx["smc"],
        "highlights": ctx["confluence"]["highlights"],
    }

    # Emit setup data IMMEDIATELY (before AI thinks)
    yield sse("setup_data", json.dumps(full_setup))

    # ── 4. Stream NVIDIA Nemotron ──
    yield sse("status", "ai_thinking")

    settings = get_settings()
    prompt = _build_prompt(ctx, setup_levels)
    full_reasoning = ""
    full_answer = ""

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=settings.NVIDIA_API_KEY,
        )

        stream = await client.chat.completions.create(
            model="nvidia/nemotron-3-ultra-550b-a55b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            top_p=0.85,
            max_tokens=6144,
            extra_body={
                "chat_template_kwargs": {"enable_thinking": True},
                "reasoning_budget": 8192,
            },
            stream=True,
        )

        async for chunk in stream:
            if await request.is_disconnected():
                logger.info(f"Client disconnected — stopping stream for {symbol}/{timeframe}")
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

    except Exception as e:
        logger.error(f"NVIDIA API error: {e}")
        yield sse("error", f"AI service error: {str(e)[:300]}")
        return

    # ── 5. Cache result ──
    _set_cache(symbol, timeframe, {
        "context_snapshot": context_snapshot,
        "setup": full_setup,
        "answer_summary": full_answer[-1000:] if full_answer else "",
    })

    yield sse("done", "complete")


# ──────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────
@router.get("/analyze")
async def analyze_chart(
    request: Request,
    symbol: str = Query("BTCUSDT", description="Trading pair, e.g. BTCUSDT"),
    timeframe: str = Query("1h", description="Timeframe: 1m, 5m, 15m, 1h, 4h, 1d"),
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
    return StreamingResponse(
        _stream_ai_analysis(symbol.upper(), timeframe, request),
        media_type="text/event-stream",
        headers=headers,
    )


@router.delete("/cache")
async def clear_ai_cache():
    """Clear the in-memory AI analysis cache."""
    _AI_CACHE.clear()
    return {"message": "AI cache cleared", "cache_size": 0}


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

    # Build system context from market context
    ctx = req.market_context or {}
    macro = ctx.get("macro", {})
    indicators = ctx.get("indicators", {})
    smc = ctx.get("smc", {})
    signal = ctx.get("signal", "UNKNOWN")
    score = ctx.get("confluence_score", 0)
    max_score = ctx.get("max_score", 33)

    system_prompt = f"""Kamu adalah AI Analyst trading kripto senior yang sedang dalam sesi tanya jawab dengan seorang trader.

Kamu baru saja selesai menganalisis {req.symbol.upper()} / {req.timeframe.upper()} dan memberikan rekomendasi {signal} dengan skor konfluensi {score}/{max_score}.

KONTEKS PASAR SAAT INI:
- Sinyal: {signal}
- HTF Bias: {ctx.get('htf_biases', {})}
- RSI: {indicators.get('rsi', 'N/A')} | MACD: {indicators.get('macd_histogram', 'N/A')} | ADX: {indicators.get('adx', 'N/A')}
- Order Blocks aktif: {smc.get('unmitigated_ob_count', 0)} | FVG: {smc.get('unfilled_fvg_count', 0)}
- BTC Dominance: {macro.get('btc_dominance', 'N/A')}%
- Fear & Greed: {macro.get('fear_greed_value', 'N/A')}/100 ({macro.get('fear_greed_label', 'N/A')})
- Funding Rate: {macro.get('funding_rate', 'N/A')} ({macro.get('funding_label', 'N/A')})
- Session: {ctx.get('session', 'N/A')}

Jawab pertanyaan trader dengan BAHASA INDONESIA yang jelas, ringkas, dan profesional. Fokus pada pertanyaannya saja. Maksimal 3-4 paragraf."""

    # Build messages array (max 10 turns of history)
    messages = [{"role": "system", "content": system_prompt}]
    for msg in req.history[-10:]:  # max 10 messages history
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": req.question})

    yield sse("status", "thinking")

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=settings.NVIDIA_API_KEY,
        )

        stream = await client.chat.completions.create(
            model="nvidia/nemotron-3-ultra-550b-a55b",
            messages=messages,
            temperature=0.6,
            top_p=0.9,
            max_tokens=1024,
            extra_body={
                "chat_template_kwargs": {"enable_thinking": True},
                "reasoning_budget": 1024,
            },
            stream=True,
        )

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            # Skip reasoning tokens for chat (too verbose)
            if delta.content:
                yield sse("token", delta.content)

    except Exception as e:
        logger.error(f"Chat AI error: {e}")
        yield sse("error", f"AI error: {str(e)[:200]}")
        return

    yield sse("done", "complete")


@router.post("/chat")
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
