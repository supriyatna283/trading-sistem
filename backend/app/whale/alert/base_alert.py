"""
Alert Base & Payload
====================
Abstract base class for all alert channels.
Supported channels: webhook, email (not Telegram per requirements).
"""
from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


class AlertSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AlertPayload:
    """Standardised alert payload sent across all channels."""
    event_type: str                    # "score_threshold" | "big_accumulation" | "smart_wallet_open"
    severity: AlertSeverity
    symbol: str
    chain_id: str
    title: str
    message: str
    score: Optional[float] = None
    grade: Optional[str] = None
    flags: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)
    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    disclaimer: str = "⚠️ Bukan jaminan pergerakan harga. Gunakan bersama analisis struktur harga."

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "severity": self.severity.value,
            "symbol": self.symbol,
            "chain_id": self.chain_id,
            "title": self.title,
            "message": self.message,
            "score": self.score,
            "grade": self.grade,
            "flags": self.flags,
            "extra": self.extra,
            "triggered_at": self.triggered_at.isoformat(),
            "disclaimer": self.disclaimer,
        }

    def to_text(self) -> str:
        """Human-readable text format for email / webhook body."""
        lines = [
            f"[{self.severity.value.upper()}] {self.title}",
            f"Symbol: {self.symbol} ({self.chain_id})",
        ]
        if self.score is not None:
            lines.append(f"Whale Score: {self.score:.1f}/100 (Grade {self.grade})")
        lines.append(f"Event: {self.event_type}")
        lines.append(self.message)
        if self.flags:
            lines.append(f"Flags: {', '.join(self.flags)}")
        lines.append(f"Waktu: {self.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append(f"\n{self.disclaimer}")
        return "\n".join(lines)


class BaseAlertChannel(ABC):
    """All alert channels must implement this interface."""

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Identifier for this channel, e.g. 'webhook', 'email'."""

    @abstractmethod
    async def send(self, payload: AlertPayload) -> bool:
        """
        Send the alert. Returns True on success, False on failure.
        Should NOT raise — handle exceptions internally and log them.
        """

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if this channel has the required configuration."""
