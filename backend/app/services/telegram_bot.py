"""
Telegram Bot Service
====================
Provides an async function to send formatted trading signals to Telegram.
"""

import httpx
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

async def send_telegram_signal(setup_schema, timeframe: str) -> bool:
    """
    Sends a formatted trading signal to the configured Telegram chat.
    Returns True on success, False otherwise.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    # Emoji based on direction
    direction_icon = "🟢 LONG" if setup_schema.direction == "BUY" else "🔴 SHORT"
    
    # Format message in HTML
    message = (
        f"⚡ <b>NEW SIGNAL: {setup_schema.symbol}</b> ⚡\n\n"
        f"<b>Direction:</b> {direction_icon}\n"
        f"<b>Timeframe:</b> {timeframe}\n"
        f"<b>Confluence Score:</b> {setup_schema.confluence_score}/10\n"
        f"<b>Setup Type:</b> {setup_schema.setup_type}\n\n"
        f"🎯 <b>ENTRY ZONE:</b>\n"
        f"{setup_schema.entry_low} - {setup_schema.entry_high}\n\n"
        f"🛑 <b>STOP LOSS:</b> {setup_schema.stop_loss}\n\n"
        f"💰 <b>TAKE PROFIT:</b>\n"
        f"TP1: {setup_schema.take_profit_1}\n"
        f"TP2: {setup_schema.take_profit_2}\n"
        f"TP3: {setup_schema.take_profit_3}\n\n"
        f"⚖️ <b>R:R Ratio:</b> 1:{round(setup_schema.risk_reward, 2)}\n\n"
        f"📝 <b>Analysis:</b>\n<i>{setup_schema.explanation}</i>\n\n"
        f"<i>Provided by Trading Intelligence Platform</i>"
    )

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"📤 Sent Telegram signal for {setup_schema.symbol} [{timeframe}]")
            return True
    except Exception as e:
        logger.error(f"❌ Failed to send Telegram signal: {e}")
        return False
