from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

from .models import PredictionEvent
from .settings import Settings


class EmailNotifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return bool(self.settings.smtp_host and self.settings.smtp_to and self.settings.smtp_from)

    async def send(self, event: PredictionEvent) -> bool:
        if not self.enabled:
            return False
        return await asyncio.to_thread(self._send_sync, event)

    def _send_sync(self, event: PredictionEvent) -> bool:
        message = EmailMessage()
        message["Subject"] = f"[Employee Monitor] {event.type} at {event.camera}"
        message["From"] = self.settings.smtp_from
        message["To"] = self.settings.smtp_to
        message.set_content(
            "\n".join(
                [
                    f"Violation: {event.type}",
                    f"Camera: {event.camera}",
                    f"Confidence: {event.confidence}%",
                    f"Severity: {event.severity}",
                    f"Time: {event.timestamp.isoformat()}",
                    f"Analysis: {event.analysis or '-'}",
                ]
            )
        )

        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as smtp:
            if self.settings.smtp_tls:
                smtp.starttls()
            if self.settings.smtp_username:
                smtp.login(self.settings.smtp_username, self.settings.smtp_password)
            smtp.send_message(message)
        return True

