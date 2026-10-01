"""
Email Alert Channel
====================
Sends alert emails via SMTP (reuses existing SMTP config from app settings).
Uses aiosmtplib (already in requirements.txt).

Reads from environment (same vars as the main alert_service.py):
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
  WHALE_ALERT_EMAIL_TO : recipient address (comma-separated for multiple)
"""
from __future__ import annotations

import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

try:
    import aiosmtplib
    _HAS_SMTP = True
except ImportError:
    _HAS_SMTP = False

from .base_alert import BaseAlertChannel, AlertPayload

logger = logging.getLogger(__name__)

SEVERITY_EMOJI = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}


def _html_body(payload: AlertPayload) -> str:
    emoji = SEVERITY_EMOJI.get(payload.severity.value, "🔔")
    score_bar = ""
    if payload.score is not None:
        pct = int(payload.score)
        colour = "#e74c3c" if pct < 40 else "#f39c12" if pct < 70 else "#2ecc71"
        score_bar = f"""
        <div style="background:#1a1a2e;border-radius:8px;padding:12px;margin:16px 0;">
          <div style="color:#888;font-size:12px;margin-bottom:4px;">WHALE SCORE</div>
          <div style="font-size:36px;font-weight:700;color:{colour}">{payload.score:.1f}</div>
          <div style="font-size:14px;color:#aaa">Grade {payload.grade} / 100</div>
          <div style="background:#2a2a3e;border-radius:4px;height:8px;margin-top:8px;">
            <div style="background:{colour};width:{pct}%;height:8px;border-radius:4px;"></div>
          </div>
        </div>
        """

    flags_html = ""
    if payload.flags:
        flags_html = "<br>".join(
            f'<span style="background:#2d1b1b;color:#e74c3c;padding:2px 8px;border-radius:4px;font-size:12px;">⚑ {f}</span>'
            for f in payload.flags
        )
        flags_html = f"<div style='margin:12px 0'>{flags_html}</div>"

    return f"""
    <html><body style="background:#0a0a1a;color:#e0e0e0;font-family:Inter,sans-serif;padding:32px;max-width:600px;margin:0 auto">
      <div style="border-left:4px solid #00d4ff;padding-left:16px;margin-bottom:24px">
        <h2 style="color:#00d4ff;margin:0">{emoji} {payload.title}</h2>
        <p style="color:#888;margin:4px 0">{payload.chain_id.upper()} • {payload.triggered_at.strftime('%Y-%m-%d %H:%M UTC')}</p>
      </div>
      {score_bar}
      <div style="background:#111128;border-radius:8px;padding:16px;margin-bottom:16px">
        <h3 style="color:#fff;margin-top:0">{payload.symbol}</h3>
        <p style="line-height:1.6">{payload.message}</p>
      </div>
      {flags_html}
      <p style="color:#555;font-size:11px;border-top:1px solid #222;padding-top:16px;margin-top:24px">
        {payload.disclaimer}<br>
        Whale Tracker Pro — {datetime.utcnow().strftime('%Y')}
      </p>
    </body></html>
    """


class EmailAlert(BaseAlertChannel):

    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        to_addresses: list[str] | None = None,
    ):
        from app.config import get_settings
        cfg = get_settings()
        self._host = smtp_host or cfg.SMTP_HOST
        self._port = smtp_port or cfg.SMTP_PORT
        self._user = smtp_user or cfg.SMTP_USER
        self._password = smtp_password or cfg.SMTP_PASSWORD
        to_env = os.getenv("WHALE_ALERT_EMAIL_TO", "")
        self._to = to_addresses or ([t.strip() for t in to_env.split(",") if t.strip()])

    @property
    def channel_name(self) -> str:
        return "email"

    def is_configured(self) -> bool:
        return bool(self._host and self._user and self._password and self._to)

    async def send(self, payload: AlertPayload) -> bool:
        if not _HAS_SMTP:
            logger.warning("[EmailAlert] aiosmtplib not installed.")
            return False
        if not self.is_configured():
            logger.debug("[EmailAlert] Not configured, skipping.")
            return False

        emoji = SEVERITY_EMOJI.get(payload.severity.value, "🔔")
        subject = f"{emoji} Whale Alert: {payload.symbol} — {payload.title}"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._user
        msg["To"] = ", ".join(self._to)
        msg.attach(MIMEText(payload.to_text(), "plain", "utf-8"))
        msg.attach(MIMEText(_html_body(payload), "html", "utf-8"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=self._host,
                port=self._port,
                username=self._user,
                password=self._password,
                start_tls=True,
            )
            logger.info(f"[EmailAlert] Sent {payload.event_type} for {payload.symbol} to {self._to}")
            return True
        except Exception as e:
            logger.error(f"[EmailAlert] Failed: {e}")
            return False
