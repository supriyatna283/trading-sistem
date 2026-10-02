"""
WhatsApp Alert Service
======================
Generic WhatsApp sender — compatible with:
  • Fonnte (fonnte.com) — Indonesian WA gateway
  • WaBlas (wablas.com)
  • Twilio WhatsApp API
  • WAHA self-hosted
  • Any HTTP-based WA gateway

Configuration via environment variables:
  WA_PROVIDER   = fonnte | wablas | twilio | custom
  WA_API_KEY    = your API token / auth token
  WA_FROM       = sender phone / twilio number (e.g. +628xxx or whatsapp:+14155...)
  WA_API_URL    = override endpoint (for custom/WAHA)
"""

import os
import httpx
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WAMessage:
    to: str           # destination phone, e.g. "628123456789"
    text: str         # message body (supports WA markdown)
    media_url: Optional[str] = None  # optional image attachment


class WhatsAppService:

    # ─── Provider endpoint configs ────────────────────────────────────────────
    PROVIDERS = {
        "fonnte": {
            "url": "https://api.fonnte.com/send",
            "method": "POST",
            "headers_fn": lambda key: {"Authorization": key},
            "body_fn": lambda msg, key: {
                "target": msg.to,
                "message": msg.text,
                **({"url": msg.media_url} if msg.media_url else {}),
            },
        },
        "wablas": {
            "url": "https://solo.wablas.com/api/send-message",
            "method": "POST",
            "headers_fn": lambda key: {"Authorization": key},
            "body_fn": lambda msg, key: {
                "phone": msg.to,
                "message": msg.text,
            },
        },
        "twilio": {
            "url": "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            "method": "POST",
            "headers_fn": lambda key: {},  # uses Basic Auth
            "body_fn": lambda msg, key: {
                "To": f"whatsapp:+{msg.to}",
                "From": os.getenv("WA_FROM", ""),
                "Body": msg.text,
            },
        },
        "waha": {
            # WAHA self-hosted — default port 3000
            "url": "{base}/api/sendText",
            "method": "POST",
            "headers_fn": lambda key: {"X-Api-Key": key} if key else {},
            "body_fn": lambda msg, key: {
                "chatId": f"{msg.to}@c.us",
                "text": msg.text,
                "session": "default",
            },
        },
        "custom": {
            # For user's own provider — configure WA_API_URL
            "url": "{base}/send",
            "method": "POST",
            "headers_fn": lambda key: {"Authorization": f"Bearer {key}"},
            "body_fn": lambda msg, key: {
                "to": msg.to,
                "message": msg.text,
            },
        },
    }

    def __init__(self):
        self.provider   = os.getenv("WA_PROVIDER", "fonnte").lower()
        self.api_key    = os.getenv("WA_API_KEY", "")
        self.api_url    = os.getenv("WA_API_URL", "")
        self.account_sid = os.getenv("WA_TWILIO_SID", "")
        self.enabled    = bool(self.api_key or self.api_url)

        if not self.enabled:
            logger.warning("WhatsApp not configured — set WA_PROVIDER, WA_API_KEY env vars")

    async def send(self, msg: WAMessage) -> dict:
        """Send a WhatsApp message. Returns {ok: bool, detail: str}."""
        if not self.enabled:
            logger.info(f"[WA-MOCK] To:{msg.to}\n{msg.text[:80]}...")
            return {"ok": False, "detail": "WA not configured — mock mode"}

        cfg = self.PROVIDERS.get(self.provider, self.PROVIDERS["custom"])

        # Build URL
        base = self.api_url or cfg.get("url", "")
        url  = base.replace("{base}", self.api_url).replace("{sid}", self.account_sid)

        headers = cfg["headers_fn"](self.api_key)
        body    = cfg["body_fn"](msg, self.api_key)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if self.provider == "twilio":
                    resp = await client.post(
                        url, data=body,
                        auth=(self.account_sid, self.api_key),
                    )
                else:
                    resp = await client.post(url, json=body, headers=headers)

            ok = resp.status_code in (200, 201)
            logger.info(f"WA send {'OK' if ok else 'FAIL'} [{resp.status_code}] to {msg.to}")
            return {"ok": ok, "status": resp.status_code, "detail": resp.text[:200]}

        except Exception as e:
            logger.error(f"WA send error: {e}")
            return {"ok": False, "detail": str(e)}

    async def send_bulk(self, messages: list[WAMessage]) -> list[dict]:
        """Send to multiple recipients."""
        import asyncio
        results = []
        for msg in messages:
            r = await self.send(msg)
            results.append(r)
            await asyncio.sleep(1.5)  # Rate limit — 1.5s between messages
        return results
