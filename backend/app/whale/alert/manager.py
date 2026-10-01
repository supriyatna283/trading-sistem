"""
Alert Manager
=============
Checks scoring results against thresholds and triggers alerts.
Records triggered alerts in the DB to avoid spamming.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from .base_alert import AlertPayload, AlertSeverity
from .webhook_alert import WebhookAlert
from .email_alert import EmailAlert
from ..scoring.engine import ScoreResult
from ..scoring.config import ScoringConfig

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages alert evaluation and dispatching."""

    def __init__(self, config: ScoringConfig):
        self.config = config
        self.channels = [
            WebhookAlert(),
            EmailAlert(),
        ]

    async def evaluate_and_alert(
        self,
        db: "Session",
        coin_id: int,
        result: ScoreResult,
    ) -> None:
        """
        Check if the score result exceeds thresholds or has critical flags.
        If so, trigger alerts and log to DB.
        """
        alerts_to_send: list[AlertPayload] = []

        # 1. Score Threshold Alerts
        if result.score >= self.config.alert_critical_threshold:
            alerts_to_send.append(
                AlertPayload(
                    event_type="critical_score",
                    severity=AlertSeverity.CRITICAL,
                    symbol=result.symbol,
                    chain_id=result.chain_id,
                    title="CRITICAL: Whale Accumulation Terdeteksi",
                    message=f"Skor sangat tinggi ({result.score:.1f}). Kemungkinan pergerakan besar.",
                    score=result.score,
                    grade=result.grade,
                    flags=result.flags,
                )
            )
        elif result.score >= self.config.alert_threshold:
            alerts_to_send.append(
                AlertPayload(
                    event_type="high_score",
                    severity=AlertSeverity.WARNING,
                    symbol=result.symbol,
                    chain_id=result.chain_id,
                    title="WARNING: Whale Activity Meningkat",
                    message=f"Skor melewati batas peringatan ({result.score:.1f}). Pantau ketat.",
                    score=result.score,
                    grade=result.grade,
                    flags=result.flags,
                )
            )

        # 2. Flag-based Alerts (e.g. extreme concentration)
        if "extreme_concentration" in result.flags:
            alerts_to_send.append(
                AlertPayload(
                    event_type="risk_flag",
                    severity=AlertSeverity.WARNING,
                    symbol=result.symbol,
                    chain_id=result.chain_id,
                    title="RISK: Konsentrasi Holder Ekstrem",
                    message="Peringatan: Sebagian besar supply dikuasai segelintir dompet. Risiko manipulasi sangat tinggi.",
                    score=result.score,
                    grade=result.grade,
                    flags=result.flags,
                )
            )
            
        if "very_new_token_high_risk" in result.flags:
             alerts_to_send.append(
                AlertPayload(
                    event_type="risk_flag",
                    severity=AlertSeverity.CRITICAL,
                    symbol=result.symbol,
                    chain_id=result.chain_id,
                    title="RISK: Token Sangat Baru",
                    message="Peringatan: Token baru saja deploy (< 3 hari). Risiko rugpull sangat tinggi.",
                    score=result.score,
                    grade=result.grade,
                    flags=result.flags,
                )
            )

        # Dispatch alerts (ensure we don't spam the same alert repeatedly)
        from app.models.whale import AlertEvent
        from datetime import datetime, timedelta, timezone

        for payload in alerts_to_send:
            # Simple anti-spam: don't send same event_type for same coin within 4 hours
            recent_alert = (
                db.query(AlertEvent)
                .filter(
                    AlertEvent.coin_id == coin_id,
                    AlertEvent.event_type == payload.event_type,
                    AlertEvent.sent_at >= datetime.now(timezone.utc) - timedelta(hours=4),
                    AlertEvent.is_sent == True,
                )
                .first()
            )

            if recent_alert:
                logger.debug(f"[AlertManager] Skipping {payload.event_type} for {payload.symbol} (already sent recently)")
                continue

            # Log attempt to DB
            event = AlertEvent(
                coin_id=coin_id,
                event_type=payload.event_type,
                severity=payload.severity.value,
                title=payload.title,
                message=payload.message,
                payload=payload.to_dict(),
                channel="multiple",
                is_sent=False,
            )
            db.add(event)
            db.commit()
            db.refresh(event)

            # Send via all configured channels
            sent_count = 0
            for channel in self.channels:
                if channel.is_configured():
                    success = await channel.send(payload)
                    if success:
                        sent_count += 1
                        
            if sent_count > 0:
                event.is_sent = True
                db.commit()
