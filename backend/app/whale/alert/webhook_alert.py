"""
Webhook Alert Channel
======================
Sends alert payloads as HTTP POST to a configured URL.
Compatible with Discord webhooks, Slack, Make.com, Zapier, n8n, etc.

Config via environment variables:
  WHALE_WEBHOOK_URL      : Target webhook URL (required)
  WHALE_WEBHOOK_SECRET   : Optional HMAC-SHA256 secret for signature header
  WHALE_WEBHOOK_FORMAT   : "json" | "discord" | "slack" (default: "json")
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime

import httpx

from .base_alert import BaseAlertChannel, AlertPayload

logger = logging.getLogger(__name__)


def _discord_embed(payload: AlertPayload) -> dict:
    """Format as Discord webhook embed."""
    colour_map = {"info": 0x3498db, "warning": 0xf39c12, "critical": 0xe74c3c}
    return {
        "embeds": [{
            "title": payload.title,
            "description": payload.message,
            "color": colour_map.get(payload.severity.value, 0x95a5a6),
            "fields": [
                {"name": "Symbol", "value": f"**{payload.symbol}**", "inline": True},
                {"name": "Chain", "value": payload.chain_id, "inline": True},
                {"name": "Score", "value": f"{payload.score:.1f}/100 ({payload.grade})" if payload.score else "N/A", "inline": True},
                {"name": "Flags", "value": ", ".join(payload.flags) or "None", "inline": False},
                {"name": "Disclaimer", "value": payload.disclaimer, "inline": False},
            ],
            "footer": {"text": f"Whale Tracker Pro • {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"},
        }]
    }


def _slack_payload(payload: AlertPayload) -> dict:
    """Format as Slack webhook message."""
    return {
        "text": payload.title,
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": payload.title}},
            {"type": "section", "text": {"type": "mrkdwn", "text": payload.message}},
            {"type": "context", "elements": [
                {"type": "mrkdwn", "text": f"*{payload.symbol}* | Score: {payload.score:.1f} | Grade {payload.grade}"}
            ]},
        ]
    }


class WebhookAlert(BaseAlertChannel):

    def __init__(
        self,
        url: str | None = None,
        secret: str | None = None,
        format: str = "json",
    ):
        self._url = url or os.getenv("WHALE_WEBHOOK_URL", "")
        self._secret = secret or os.getenv("WHALE_WEBHOOK_SECRET", "")
        self._format = format or os.getenv("WHALE_WEBHOOK_FORMAT", "json")

    @property
    def channel_name(self) -> str:
        return "webhook"

    def is_configured(self) -> bool:
        return bool(self._url)

    async def send(self, payload: AlertPayload) -> bool:
        if not self.is_configured():
            logger.debug("[WebhookAlert] Not configured, skipping.")
            return False

        # Build body according to format
        if self._format == "discord":
            body = _discord_embed(payload)
        elif self._format == "slack":
            body = _slack_payload(payload)
        else:
            body = payload.to_dict()

        body_bytes = json.dumps(body, ensure_ascii=False).encode()

        headers = {"Content-Type": "application/json"}
        if self._secret:
            sig = hmac.new(self._secret.encode(), body_bytes, hashlib.sha256).hexdigest()
            headers["X-Whale-Signature"] = f"sha256={sig}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    self._url,
                    content=body_bytes,
                    headers=headers,
                )
                if resp.status_code < 300:
                    logger.info(f"[WebhookAlert] Sent {payload.event_type} for {payload.symbol}")
                    return True
                else:
                    logger.warning(f"[WebhookAlert] HTTP {resp.status_code}: {resp.text[:200]}")
                    return False
        except Exception as e:
            logger.error(f"[WebhookAlert] Failed to send: {e}")
            return False
