"""
Alert Service
==============
Sends notifications via Telegram, Email, and WebSocket.
"""

import logging
from typing import Optional
from app.config import get_settings
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)


class AlertService:
    """Sends trade setup alerts through configured channels."""

    def __init__(self):
        self.settings = get_settings()

    async def send_alert(
        self, message: str, channel: str = "WEB", setup_data: dict = None
    ) -> bool:
        """Send alert through the specified channel."""
        try:
            if channel == "TELEGRAM":
                return await self._send_telegram(message)
            elif channel == "EMAIL":
                return await self._send_email(message)
            elif channel == "WEB":
                return await self._send_web(message, setup_data)
            return False
        except Exception as e:
            logger.error(f"Alert send failed ({channel}): {e}")
            return False

    async def send_setup_alert(self, setup: dict) -> list:
        """Format and send a trade setup alert to all channels."""
        message = self._format_setup_message(setup)
        results = []

        # Always send web notification
        success = await self._send_web(message, setup)
        results.append({"channel": "WEB", "success": success})

        # Send Telegram if configured
        if self.settings.TELEGRAM_BOT_TOKEN and self.settings.TELEGRAM_CHAT_ID:
            success = await self._send_telegram(message)
            results.append({"channel": "TELEGRAM", "success": success})

        return results

    def _format_setup_message(self, setup: dict) -> str:
        """Format a trade setup into alert message."""
        return (
            f"🔔 NEW TRADE SETUP\n\n"
            f"Pair: {setup.get('symbol', 'N/A')}\n"
            f"Direction: {setup.get('direction', 'N/A')}\n"
            f"Entry: {setup.get('entry_low', 'N/A')} – {setup.get('entry_high', 'N/A')}\n"
            f"Stop Loss: {setup.get('stop_loss', 'N/A')}\n"
            f"Take Profit: {setup.get('take_profit_1', 'N/A')}\n"
            f"R:R: 1:{setup.get('risk_reward', 'N/A')}\n"
            f"Setup: {setup.get('setup_type', 'N/A')}\n"
            f"Score: {setup.get('confluence_score', 0)}/24"
        )

    async def _send_telegram(self, message: str) -> bool:
        """Send via Telegram Bot API."""
        try:
            import httpx
            url = f"https://api.telegram.org/bot{self.settings.TELEGRAM_BOT_TOKEN}/sendMessage"
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json={
                    "chat_id": self.settings.TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "HTML",
                })
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram error: {e}")
            return False

    async def _send_email(self, message: str) -> bool:
        """Send via SMTP when SMTP_USER and SMTP_PASSWORD are configured."""
        if not self.settings.SMTP_USER or not self.settings.SMTP_PASSWORD:
            logger.warning("Email alert skipped: SMTP not configured")
            return False
        try:
            import aiosmtplib
            from email.message import EmailMessage

            msg = EmailMessage()
            msg["From"] = self.settings.SMTP_USER
            msg["To"] = self.settings.SMTP_USER
            msg["Subject"] = "Trading Intelligence Alert"
            msg.set_content(message)

            await aiosmtplib.send(
                msg,
                hostname=self.settings.SMTP_HOST,
                port=self.settings.SMTP_PORT,
                username=self.settings.SMTP_USER,
                password=self.settings.SMTP_PASSWORD,
                start_tls=True,
            )
            return True
        except Exception as e:
            logger.error(f"Email error: {e}")
            return False

    async def _send_web(self, message: str, data: dict = None) -> bool:
        """Send via WebSocket to connected dashboards."""
        try:
            payload = {
                "type": "alert",
                "message": message,
                "data": data,
            }
            await ws_manager.broadcast(payload)
            return True
        except Exception as e:
            logger.error(f"Web alert error: {e}")
            return False


# Global instance
alert_service = AlertService()
