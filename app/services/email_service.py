from email.message import EmailMessage

import httpx

from app.core.config import settings


class EmailDeliveryError(OSError):
    """Subclasses OSError so the existing except (OSError, SMTPException) blocks still catch it."""


def send_email(message: EmailMessage) -> None:
    try:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={
                "from": message["From"],
                "to": [message["To"]],
                "subject": message["Subject"],
                "text": message.get_content(),
            },
            timeout=10,
        )
    except httpx.HTTPError as error:
        raise EmailDeliveryError("Email provider unreachable") from error

    if response.status_code >= 400:
        raise EmailDeliveryError(f"Email provider returned {response.status_code}")