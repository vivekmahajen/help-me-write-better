"""Outbound email transports (password-reset links, etc.).

Injectable like the other external integrations (OAuth, Stripe, scan vendors) so
the whole auth path is testable offline. The default :class:`ConsoleMailer`
records and prints messages without touching the network; configure SMTP via
environment for real delivery.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage


@dataclass
class Email:
    to: str
    subject: str
    body: str


class ConsoleMailer:
    """No-network transport: appends to ``sent`` and prints. Default for dev/test."""

    def __init__(self) -> None:
        self.sent: list[Email] = []

    def send(self, email: Email) -> None:
        self.sent.append(email)
        print(f"[mail] to={email.to} subject={email.subject!r}\n{email.body}")


@dataclass
class SMTPMailer:
    """Real delivery over SMTP (stdlib ``smtplib``)."""

    host: str
    port: int = 587
    username: str | None = None
    password: str | None = None
    sender: str = "no-reply@localhost"
    use_tls: bool = True

    def send(self, email: Email) -> None:  # pragma: no cover - needs a live SMTP server
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = email.to
        msg["Subject"] = email.subject
        msg.set_content(email.body)
        with smtplib.SMTP(self.host, self.port) as smtp:
            if self.use_tls:
                smtp.starttls(context=ssl.create_default_context())
            if self.username:
                smtp.login(self.username, self.password or "")
            smtp.send_message(msg)


def mailer_from_env():
    """An :class:`SMTPMailer` when ``WB_SMTP_HOST`` is set, else a console mailer."""
    host = os.environ.get("WB_SMTP_HOST")
    if not host:
        return ConsoleMailer()
    return SMTPMailer(
        host=host,
        port=int(os.environ.get("WB_SMTP_PORT", "587")),
        username=os.environ.get("WB_SMTP_USER"),
        password=os.environ.get("WB_SMTP_PASSWORD"),
        sender=os.environ.get("WB_MAIL_FROM", "no-reply@localhost"),
        use_tls=os.environ.get("WB_SMTP_TLS", "1").strip().lower() in ("1", "true", "yes", "on"),
    )
