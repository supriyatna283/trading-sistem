"""Alert system for Whale Tracker."""
from .base_alert import BaseAlertChannel, AlertPayload, AlertSeverity
from .webhook_alert import WebhookAlert
from .email_alert import EmailAlert

__all__ = ["BaseAlertChannel", "AlertPayload", "AlertSeverity", "WebhookAlert", "EmailAlert"]
