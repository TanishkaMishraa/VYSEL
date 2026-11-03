"""Outbound email. `console` logs the message (development); `smtp` sends it.

Called from the Celery task `vysel.send_email`, so requests never wait on SMTP.
"""

import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings

log = logging.getLogger("vysel.email")


def send(to: str, subject: str, text: str) -> None:
    settings = get_settings()
    if settings.email_backend == "console":
        # Development: the link appears in the worker log. Never enable in production.
        log.info("EMAIL (console backend)\nTo: %s\nSubject: %s\n\n%s", to, subject, text)
        return

    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.email_from, to, subject
    msg.set_content(text)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)


def password_reset(to: str, name: str, link: str, ttl_minutes: int) -> tuple[str, str]:
    subject = "Reset your VYSEL password"
    text = (
        f"Hi {name},\n\n"
        f"Someone asked to reset the password for your VYSEL account. If it was you, open this link:\n\n{link}\n\n"
        f"It works once and expires in {ttl_minutes} minutes. If you didn't ask for this, ignore this email; "
        "your password stays the same.\n\n— VYSEL"
    )
    return subject, text
