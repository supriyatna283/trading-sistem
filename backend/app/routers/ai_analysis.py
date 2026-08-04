"""
AI Chart Analysis Router — NVIDIA Nemotron SSE Streaming
=========================================================
Architecture (as approved):
  MarketDataEngine → Technical Indicators → Confluence Engine → Signal Engine
  → Market Summary (no raw candles sent to AI) → NVIDIA Nemotron → SSE stream

The engine determines BUY / SELL / WAIT.
The AI explains WHY using the computed market context.

Features:
  - SSE streaming with token-by-token reasoning
  - In-memory cache (60s TTL per symbol+timeframe)
  - Disconnect detection: stops NVIDIA stream if client disconnects
  - WAIT signal when confluence score is too low
  - Structured final JSON in the stream (event: setup_data)
"""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.engines.market_data import MarketDataEngine
from app.engines.market_structure import MarketStructureAnalyzer
from app.engines.smart_money import SmartMoneyConceptsEngine
from app.engines.confluence import ConfluenceEngine
from app.utils.indicators import (
    calculate_rsi, calculate_ema, calculate_macd,
    calculate_bollinger_bands, calculate_stoch_rsi,
    calculate_vwap, calculate_adx,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["AI Analysis"])

# ──────────────────────────────────────────────────────────────
# In-Memory Cache (60s TTL — avoids redundant AI calls)
# ──────────────────────────────────────────────────────────────
_AI_CACHE: dict[str, dict] = {}
_AI_CACHE_TTL = 60  # seconds


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


# ──────────────────────────────────────────────────────────────
# Market context builder — runs full engine pipeline
# ──────────────────────────────────────────────────────────────
async def _build_market_context(symbol: str, timeframe: str) -> dict:
    """
    Runs the full engine pipeline and returns a structured market summary.
    Raw candles are NOT sent to the AI — only computed results.
    """
    # 1. Fetch multi-timeframe candles
    HTF_TIMEFRAMES = ["1d", "4h", "1h", "15m"]
    entry_tf = timeframe if timeframe in HTF_TIMEFRAMES else "1h"

    tasks = [_data_engine.get_candles(symbol.upper(), tf, 200) for tf in HTF_TIMEFRAMES]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    candles_by_tf: dict = {}
    for i, df in enumerate(results):
        if not isinstance(df, Exception) and not df.empty:
            candles_by_tf[HTF_TIMEFRAMES[i]] = df

    entry_df = candles_by_tf.get(entry_tf) or candles_by_tf.get("1h")
    if entry_df is None or entry_df.empty:
        return {"error": "No candle data available"}

    # 2. Market structure analysis (all HTFs)
    structure_by_tf: dict = {}
    for tf, df in candles_by_tf.items():
        try:
            structure_by_tf[tf] = _structure_engine.analyze(df, symbol, tf)
        except Exception:
            pass

    entry_structure = structure_by_tf.get(entry_tf) or structure_by_tf.get("1h")

    # 3. SMC analysis on entry TF
    try:
        smc = _smc_engine.analyze(entry_df, symbol, entry_tf)
    except Exception:
        smc = None

    # 4. Confluence scoring
    try:
        conf = _confluence_engine.score(
            candles_by_tf, symbol, entry_tf,
            sentiment_data=None,
            news_events=None,
            mtf_result=None,
            market_intel_data=None,
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
        rsi = calculate_rsi(entry_df)
        ema20 = calculate_ema(entry_df, 20)
        ema50 = calculate_ema(entry_df, 50)
        ema200 = calculate_ema(entry_df, 200)
        macd_line, signal_line, macd_hist = calculate_macd(entry_df)
        bb_upper, bb_mid, bb_lower, bb_bw = calculate_bollinger_bands(entry_df)
        stoch_k, stoch_d = calculate_stoch_rsi(entry_df)
        vwap_data = calculate_vwap(entry_df)
        adx_val = calculate_adx(entry_df)
    except Exception:
        rsi = ema20 = ema50 = ema200 = macd_hist = None
        bb_upper = bb_lower = stoch_k = stoch_d = adx_val = None
        vwap_data = {}

    # 6. Current price
    last_close = float(entry_df.iloc[-1]["close"])
    last_high = float(entry_df.iloc[-1]["high"])
    last_low = float(entry_df.iloc[-1]["low"])
    last_volume = float(entry_df.iloc[-1]["volume"])

    # 7. Determine signal direction
    if recommendation in ("STRONG_BUY", "BUY"):
        signal = "BUY"
    elif recommendation in ("STRONG_SELL", "SELL"):
        signal = "SELL"
    else:
        signal = "WAIT"

    # 8. SMC summary
    ob_count = len([ob for ob in (smc.order_blocks if smc else []) if not ob.mitigated])
    fvg_count = len([f for f in (smc.fvgs if smc else []) if not f.filled])
    liq_levels = len(smc.liquidity_levels) if smc else 0

    # Recent structure labels (last 5)
    recent_labels = []
    if entry_structure:
        recent_labels = [
            {"label": l.label, "price": round(l.price, 6)}
            for l in entry_structure.structure_labels[-5:]
        ]

    # HTF biases
    htf_biases = {
        tf: (structure_by_tf[tf].bias if tf in structure_by_tf else "UNKNOWN")
        for tf in ["1d", "4h", "1h", "15m"]
    }

    # Confluence score details (human-readable subset)
    confluence_highlights = {
        "htf_bias_aligned": conf_details.get("htf_bias", {}).get("aligned", False),
        "liquidity_swept": conf_details.get("liquidity", {}).get("swept", False),
        "in_order_block": conf_details.get("order_block", {}).get("in_zone", False),
        "fvg_present": conf_details.get("fvg", {}).get("present", False),
        "bos_choch_confirmed": conf_details.get("structure", {}).get("confirmed", False),
        "rsi_aligned": conf_details.get("rsi", {}).get("aligned", False),
        "ema_aligned": conf_details.get("ema", {}).get("aligned", False),
        "macd_aligned": conf_details.get("macd", {}).get("aligned", False),
        "stoch_rsi_aligned": conf_details.get("stoch_rsi", {}).get("aligned", False),
        "volume_confirmed": conf_details.get("volume", {}).get("confirmed", False),
        "vwap_aligned": conf_details.get("vwap", {}).get("aligned", False),
    }

    def _fmt(v, decimals=4):
        if v is None:
            return None
        return round(float(v), decimals)

    return {
        "symbol": symbol.upper(),
        "timeframe": entry_tf,
        "price": {
            "current": _fmt(last_close),
            "high": _fmt(last_high),
            "low": _fmt(last_low),
            "volume": _fmt(last_volume, 2),
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
            "rsi": _fmt(rsi, 1),
            "ema20": _fmt(ema20),
            "ema50": _fmt(ema50),
            "ema200": _fmt(ema200),
            "macd_histogram": _fmt(macd_hist, 6),
            "bb_upper": _fmt(bb_upper),
            "bb_lower": _fmt(bb_lower),
            "stoch_k": _fmt(stoch_k, 1),
            "stoch_d": _fmt(stoch_d, 1),
            "adx": _fmt(adx_val, 1),
            "vwap": _fmt(vwap_data.get("vwap")) if vwap_data else None,
            "vwap_position": vwap_data.get("position") if vwap_data else None,
        },
        "smc": {
            "unmitigated_ob_count": ob_count,
            "unfilled_fvg_count": fvg_count,
            "liquidity_levels": liq_levels,
            "recent_structure": recent_labels,
        },
    }


# ──────────────────────────────────────────────────────────────
# Prompt builder
# ──────────────────────────────────────────────────────────────
def _build_prompt(ctx: dict) -> str:
    """Build a rich, token-efficient prompt from the market context dict."""
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

    # Format highlights
    hi_lines = []
    for k, v in highlights.items():
        emoji = "✅" if v else "❌"
        hi_lines.append(f"  {emoji} {k.replace('_', ' ').title()}: {v}")
    hi_str = "\n".join(hi_lines)

    struct_str = " → ".join(
        [f"{s['label']}@{s['price']}" for s in recent_struct]
    ) if recent_struct else "N/A"

    prompt = f"""You are an expert crypto trading analyst specializing in Smart Money Concepts (SMC/ICT), multi-timeframe analysis, and technical analysis.

## Market Context — {sym} / {tf.upper()}

**Current Price:** {price}
**Engine Signal:** {signal}  
**Confluence Score:** {conf['score']}/{conf['max_score']} ({conf['pct']}%) — {conf['recommendation']}

### HTF Bias (Multi-Timeframe)
- 1D: {htf.get('1d', 'N/A')}
- 4H: {htf.get('4h', 'N/A')}
- 1H: {htf.get('1h', 'N/A')}
- 15m: {htf.get('15m', 'N/A')}

### Technical Indicators
- RSI(14): {ind.get('rsi', 'N/A')}
- EMA20: {ind.get('ema20', 'N/A')} | EMA50: {ind.get('ema50', 'N/A')} | EMA200: {ind.get('ema200', 'N/A')}
- MACD Histogram: {ind.get('macd_histogram', 'N/A')}
- Bollinger Bands: Upper={ind.get('bb_upper','N/A')} | Lower={ind.get('bb_lower','N/A')}
- Stoch RSI: K={ind.get('stoch_k','N/A')} D={ind.get('stoch_d','N/A')}
- ADX: {ind.get('adx', 'N/A')}
- VWAP: {ind.get('vwap','N/A')} (Price is {ind.get('vwap_position','N/A')} VWAP)

### Smart Money Concepts (SMC/ICT)
- Unmitigated Order Blocks: {smc['unmitigated_ob_count']}
- Unfilled Fair Value Gaps: {smc['unfilled_fvg_count']}
- Liquidity Levels: {smc['liquidity_levels']}
- Recent Market Structure: {struct_str}

### Confluence Checklist
{hi_str}

---

## Your Task

Based on the engine signal **{signal}** and the market context above, provide a concise trading analysis. 

Structure your response as follows:

### 1. Market Narrative
Explain the current market structure in 2–3 sentences. Reference specific SMC concepts (OB, FVG, BOS, CHOCH, liquidity sweep) if applicable.

### 2. Signal Justification
Explain why the engine generated **{signal}** — which confluence factors are most significant?

### 3. Trade Setup
Provide specific price levels:
- **Bias:** {signal}
- **Entry Zone:** [price range]
- **Stop Loss:** [price level + reasoning]  
- **TP1:** [price level]
- **TP2:** [price level]  
- **TP3:** [price level]
- **R:R Ratio:** [calculated ratio]
- **Confidence:** [LOW / MEDIUM / HIGH — based on confluence score {conf['pct']}%]

### 4. Key Risks
List 2–3 scenarios that would invalidate this setup.

### 5. Final Summary
One sentence conclusion.

---
END_OF_ANALYSIS
"""
    return prompt


# ──────────────────────────────────────────────────────────────
# SSE generator — streams NVIDIA Nemotron tokens
# ──────────────────────────────────────────────────────────────
async def _stream_ai_analysis(
    symbol: str,
    timeframe: str,
    request: Request,
) -> AsyncGenerator[str, None]:
    """
    Yields SSE events:
      - event: status     → progress updates
      - event: reasoning  → AI thinking tokens (realtime)
      - event: token      → AI final answer tokens (realtime)
      - event: setup_data → final structured JSON setup
      - event: done       → stream complete
      - event: error      → error message
    """

    def sse(event: str, data: str) -> str:
        # Escape newlines in data field
        escaped = data.replace("\n", "\\n")
        return f"event: {event}\ndata: {escaped}\n\n"

    # ── 1. Check cache ──
    cached = _get_cached(symbol, timeframe)
    if cached:
        yield sse("status", "cache_hit")
        yield sse("token", cached.get("reasoning_summary", ""))
        yield sse("setup_data", json.dumps(cached["setup"]))
        yield sse("done", "cached")
        return

    # ── 2. Build market context (engine pipeline) ──
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

    # ── 3. Emit engine result immediately ──
    yield sse("status", "indicators_ready")
    yield sse("context", json.dumps({
        "signal": ctx["signal"],
        "confluence_score": ctx["confluence"]["score"],
        "max_score": ctx["confluence"]["max_score"],
        "confluence_pct": ctx["confluence"]["pct"],
        "htf_biases": ctx["htf_biases"],
        "entry_bias": ctx["entry_bias"],
        "indicators": ctx["indicators"],
        "smc": ctx["smc"],
    }))

    # ── 4. Call NVIDIA Nemotron ──
    yield sse("status", "ai_thinking")
    settings = get_settings()
    api_key = settings.NVIDIA_API_KEY

    prompt = _build_prompt(ctx)

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key,
        )

        full_reasoning = ""
        full_answer = ""

        stream = await client.chat.completions.create(
            model="nvidia/nemotron-3-ultra-550b-a55b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            top_p=0.9,
            max_tokens=4096,
            extra_body={
                "chat_template_kwargs": {"enable_thinking": True},
                "reasoning_budget": 4096,
            },
            stream=True,
        )

        async for chunk in stream:
            # Check if client disconnected
            if await request.is_disconnected():
                logger.info(f"Client disconnected, stopping AI stream for {symbol}/{timeframe}")
                await stream.close()
                return

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # Reasoning tokens (thinking phase)
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                full_reasoning += reasoning
                yield sse("reasoning", reasoning)

            # Answer tokens
            if delta.content:
                full_answer += delta.content
                yield sse("token", delta.content)

    except Exception as e:
        logger.error(f"NVIDIA API error: {e}")
        yield sse("error", f"AI service error: {str(e)[:200]}")
        return

    # ── 5. Parse structured setup from the AI answer ──
    setup = _parse_setup(ctx, full_answer)

    # ── 6. Cache the result ──
    _set_cache(symbol, timeframe, {
        "reasoning_summary": full_answer[-500:] if full_answer else "",
        "setup": setup,
    })

    # ── 7. Emit final structured setup ──
    yield sse("setup_data", json.dumps(setup))
    yield sse("done", "complete")


def _parse_setup(ctx: dict, ai_text: str) -> dict:
    """
    Extract structured setup from AI text.
    Falls back to engine-computed values if AI text can't be parsed.
    """
    import re

    signal = ctx["signal"]
    price = ctx["price"]["current"]
    conf_pct = ctx["confluence"]["pct"]

    # Confidence mapping
    if conf_pct >= 70:
        confidence = "HIGH"
    elif conf_pct >= 45:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # Try to extract price levels from AI text using regex
    def extract_price(pattern: str) -> Optional[float]:
        m = re.search(pattern, ai_text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except Exception:
                pass
        return None

    entry = extract_price(r"entry[^:]*:\s*\$?([\d,]+\.?\d*)")
    sl = extract_price(r"stop[^:]*:\s*\$?([\d,]+\.?\d*)")
    tp1 = extract_price(r"tp1[^:]*:\s*\$?([\d,]+\.?\d*)")
    tp2 = extract_price(r"tp2[^:]*:\s*\$?([\d,]+\.?\d*)")
    tp3 = extract_price(r"tp3[^:]*:\s*\$?([\d,]+\.?\d*)")
    rr = extract_price(r"r[:\s]*r[^:]*:\s*([\d.]+)")

    # Compute fallback levels from ATR if AI didn't provide them
    if entry is None:
        entry = price

    if sl is None or tp1 is None:
        atr_approx = (ctx["price"]["high"] - ctx["price"]["low"]) * 2
        if signal == "BUY":
            sl = sl or round(price - atr_approx, 6)
            tp1 = tp1 or round(price + atr_approx * 1.5, 6)
            tp2 = tp2 or round(price + atr_approx * 2.5, 6)
            tp3 = tp3 or round(price + atr_approx * 4.0, 6)
        elif signal == "SELL":
            sl = sl or round(price + atr_approx, 6)
            tp1 = tp1 or round(price - atr_approx * 1.5, 6)
            tp2 = tp2 or round(price - atr_approx * 2.5, 6)
            tp3 = tp3 or round(price - atr_approx * 4.0, 6)
        else:
            sl = tp1 = tp2 = tp3 = None

    # R:R
    if rr is None and sl and tp1 and entry:
        risk = abs(entry - sl)
        reward = abs(tp1 - entry)
        rr = round(reward / risk, 2) if risk > 0 else None

    return {
        "symbol": ctx["symbol"],
        "timeframe": ctx["timeframe"],
        "signal": signal,
        "confidence": confidence,
        "confluence_score": ctx["confluence"]["score"],
        "max_score": ctx["confluence"]["max_score"],
        "confluence_pct": conf_pct,
        "entry": entry,
        "stop_loss": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "risk_reward": rr,
        "htf_biases": ctx["htf_biases"],
        "indicators": ctx["indicators"],
    }


# ──────────────────────────────────────────────────────────────
# Endpoint
# ──────────────────────────────────────────────────────────────
@router.get("/analyze")
async def analyze_chart(
    request: Request,
    symbol: str = Query("BTCUSDT", description="Trading pair, e.g. BTCUSDT"),
    timeframe: str = Query("1h", description="Timeframe: 1m, 5m, 15m, 1h, 4h, 1d"),
):
    """
    Stream AI chart analysis via Server-Sent Events.
    
    The engine (ConfluenceEngine + SMC + MarketStructure) determines the signal.
    NVIDIA Nemotron explains the reasoning in realtime via SSE.
    
    Events emitted:
      status     — pipeline progress
      context    — computed market indicators (JSON)
      reasoning  — AI thinking tokens (streaming)
      token      — AI answer tokens (streaming)
      setup_data — final parsed setup (JSON)
      done       — stream complete
      error      — error message
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
    """Clear the AI analysis cache (for testing)."""
    _AI_CACHE.clear()
    return {"message": "AI cache cleared"}
