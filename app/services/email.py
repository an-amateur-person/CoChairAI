"""Email delivery for meeting invitations, backed by configurable SMTP settings."""

import smtplib
from email.message import EmailMessage

from app.config import get_settings


class EmailDeliveryError(RuntimeError):
    """Raised when an email cannot be delivered."""


def send_email(to_addresses: list[str], subject: str, body: str) -> None:
    """Send a plain-text email to the given recipients using configured SMTP settings."""
    settings = get_settings()
    if not settings.smtp_host:
        raise EmailDeliveryError("SMTP host is not configured. Set CCHAIR_SMTP_HOST to enable email delivery.")
    if not to_addresses:
        raise EmailDeliveryError("No recipient email addresses were provided.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_address or settings.smtp_username or "noreply@cochairai.local"
    message["To"] = ", ".join(to_addresses)
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
            if settings.smtp_use_tls:
                client.starttls()
            if settings.smtp_username and settings.smtp_password:
                client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(message)
    except (smtplib.SMTPException, OSError) as error:
        raise EmailDeliveryError(f"Failed to send email: {error}") from error
