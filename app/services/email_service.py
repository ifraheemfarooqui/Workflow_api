import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings


def send_email(message: EmailMessage) -> None:
    context = ssl.create_default_context()
    if settings.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=10,
            context=context,
        ) as server:
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(message)
        return

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
        if settings.SMTP_USE_TLS:
            server.starttls(context=context)
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(message)
