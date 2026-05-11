"""
Telegram Bot Service — V5
=========================
Sends professionally formatted trading signals to Telegram.
Supports quality-tier labels, V5 score system (x/24), and timestamps.
"""

import httpx
import logging
from datetime import datetime, timezone
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Quality tier thresholds (out of 24) ──
QUALITY_TIERS = [
    (20, "🥇 PREMIUM", "⚡⚡⚡"),
    (16, "🥈 HIGH",    "⚡⚡"),
    (12, "🥉 VALID",   "⚡"),
]


def _get_quality_tier(score: float) -> tuple[str, str]:
    """Return (tier_label, signal_strength) based on confluence score."""
    for threshold, label, strength in QUALITY_TIERS:
        if score >= threshold:
            return label, strength
    return "⚪ LOW", ""


def _fmt_price(p) -> str:
    """Format price for display."""
    if p is None or p == 0:
        return "–"
    return f"{p:,.2f}" if p > 10 else f"{p:.6f}"


async def send_telegram_signal(setup_schema, timeframe: str) -> bool:
    """
    Sends a formatted trading signal to the configured Telegram chat.
    Returns True on success, False otherwise.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID
    proxy_url = settings.TELEGRAM_PROXY_URL

    if not proxy_url and (not token or not chat_id):
        logger.warning("⚠️ No TELEGRAM_PROXY_URL or TELEGRAM_BOT_TOKEN/CHAT_ID configured. Skipping alert.")
        return False

    # Safe getters with defaults
    direction = getattr(setup_schema, "direction", "N/A")
    symbol = getattr(setup_schema, "symbol", "N/A")
    score = getattr(setup_schema, "confluence_score", 0) or 0
    setup_type = getattr(setup_schema, "setup_type", "N/A")
    entry_low = getattr(setup_schema, "entry_low", 0)
    entry_high = getattr(setup_schema, "entry_high", 0)
    stop_loss = getattr(setup_schema, "stop_loss", 0)
    tp1 = getattr(setup_schema, "take_profit_1", 0)
    tp2 = getattr(setup_schema, "take_profit_2", None)
    tp3 = getattr(setup_schema, "take_profit_3", None)
    rr = getattr(setup_schema, "risk_reward", 0) or 0
    explanation = getattr(setup_schema, "explanation", "") or ""

    # Direction styling
    direction_icon = "🟢 LONG" if direction == "BUY" else "🔴 SHORT"

    # Quality tier
    tier_label, strength = _get_quality_tier(float(score))

    # Timestamp
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # TP lines
    tp_lines = f"  TP1: <code>{_fmt_price(tp1)}</code>"
    if tp2:
        tp_lines += f"\n  TP2: <code>{_fmt_price(tp2)}</code>"
    if tp3:
        tp_lines += f"\n  TP3: <code>{_fmt_price(tp3)}</code>"

    # Score bar visualization (filled blocks out of 24)
    filled = int(round(float(score) / 24 * 10))
    score_bar = "█" * filled + "░" * (10 - filled)

    message = (
        f"{strength} <b>SIGNAL: {symbol}</b>\n"
        f"{'━' * 24}\n\n"
        f"📊 <b>{direction_icon}</b> │ {tier_label}\n"
        f"⏱ <b>TF:</b> {timeframe} │ <b>Type:</b> {setup_type}\n"
        f"📈 <b>Score:</b> {score}/24 [{score_bar}]\n\n"
        f"{'─' * 24}\n"
        f"🎯 <b>ENTRY</b>\n"
        f"  <code>{_fmt_price(entry_low)} – {_fmt_price(entry_high)}</code>\n\n"
        f"🛑 <b>STOP LOSS</b>\n"
        f"  <code>{_fmt_price(stop_loss)}</code>\n\n"
        f"💰 <b>TARGETS</b>\n"
        f"{tp_lines}\n\n"
        f"⚖️ <b>R:R:</b> 1:{round(float(rr), 2)}\n"
        f"{'─' * 24}\n\n"
        f"📝 <i>{explanation[:280]}</i>\n\n"
        f"🕐 {now_utc}\n"
        f"<i>Trading Intelligence V5</i>"
    )

    return await _send_message(message, symbol, timeframe)


async def send_telegram_risk_alert(alert_type: str, message_text: str) -> bool:
    """Send a risk management alert to Telegram (circuit breaker, daily loss, etc)."""
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID
    proxy_url = settings.TELEGRAM_PROXY_URL

    if not proxy_url and (not token or not chat_id):
        return False

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    message = (
        f"🚨 <b>RISK ALERT: {alert_type}</b>\n"
        f"{'━' * 24}\n\n"
        f"{message_text}\n\n"
        f"🕐 {now_utc}\n"
        f"<i>Trading Intelligence V5 — Risk Management</i>"
    )

    return await _send_message(message, "RISK", alert_type)


async def _send_message(message: str, context_label: str, context_detail: str) -> bool:
    """Internal: send a message to Telegram via Vercel proxy or direct API."""
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    # Priority 1: Vercel Proxy (bypasses HuggingFace outbound block)
    use_proxy = bool(settings.TELEGRAM_PROXY_URL)

    if use_proxy:
        url = settings.TELEGRAM_PROXY_URL
        headers = {
            "Content-Type": "application/json",
            "x-proxy-secret": settings.TELEGRAM_PROXY_SECRET,
        }
        payload = {
            "text": message,
            "parse_mode": "HTML",
        }
        label = "Proxy"
    else:
        # Priority 2: Direct Telegram API (works locally or non-HF environments)
        if not token:
            logger.warning("⚠️ No TELEGRAM_PROXY_URL or TELEGRAM_BOT_TOKEN configured. Skipping alert.")
            return False
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        headers = {"Content-Type": "application/json"}
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        label = "Direct"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                logger.error(
                    f"❌ Telegram {label} Error [{response.status_code}]: {response.text}"
                )
                return False
            logger.info(f"📤 Telegram sent via {label}: {context_label} [{context_detail}]")
            return True
    except httpx.TimeoutException:
        logger.error(f"❌ Telegram timeout for {context_label}")
        return False
    except httpx.ConnectError as e:
        logger.error(f"❌ Telegram connection error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Telegram failed: {type(e).__name__}: {e}", exc_info=True)
        return False

