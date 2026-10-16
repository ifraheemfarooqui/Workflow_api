import logging
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.services.email_service import send_email
from app.models.account_deletion_code import AccountDeletionCode
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User

logger = logging.getLogger(__name__)


def ensure_email_configured() -> None:
    if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
        raise RuntimeError("Password recovery email is not configured. Set SMTP_HOST and SMTP_FROM_EMAIL.")
    if bool(settings.SMTP_USERNAME) != bool(settings.SMTP_PASSWORD):
        raise RuntimeError("Configure both SMTP_USERNAME and SMTP_PASSWORD, or leave both empty.")
    if settings.SMTP_USE_SSL and settings.SMTP_USE_TLS:
        raise RuntimeError("Set only one of SMTP_USE_SSL or SMTP_USE_TLS.")


def issue_reset_token(db: Session, user: User) -> str | None:
    now = datetime.now(timezone.utc)
    latest = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == user.id)
        .order_by(PasswordResetToken.created_at.desc())
        .first()
    )
    if latest is not None:
        last_created = latest.created_at
        if last_created.tzinfo is None:
            last_created = last_created.replace(tzinfo=timezone.utc)
        if (now - last_created).total_seconds() < settings.PASSWORD_RESET_REQUEST_COOLDOWN_SECONDS:
            return None

    raw_token = security.generate_password_reset_token()
    db.add(PasswordResetToken(
        user_id=user.id,
        token_hash=security.hash_reset_token(raw_token),
        expires_at=now + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
    ))
    db.commit()
    return raw_token


def revoke_reset_token(db: Session, token: str) -> None:
    reset_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == security.hash_reset_token(token),
        PasswordResetToken.used_at.is_(None),
    ).first()
    if reset_record is not None:
        db.delete(reset_record)
        db.commit()


def reset_password(db: Session, token: str, new_password: str) -> int:
    reset_record = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == security.hash_reset_token(token))
        .with_for_update()
        .first()
    )
    now = datetime.now(timezone.utc)
    if reset_record is None or reset_record.used_at is not None:
        raise ValueError("This password reset link is invalid or has already been used.")

    expires_at = reset_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        reset_record.used_at = now
        db.commit()
        raise ValueError("This password reset link has expired. Request a new one.")

    user = db.query(User).filter(User.id == reset_record.user_id).first()
    if user is None:
        reset_record.used_at = now
        db.commit()
        raise ValueError("This password reset link is invalid or has already been used.")

    user.hashed_password = security.hash_password(new_password)
    user.token_version += 1
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)
    db.commit()
    return user.id


def send_password_reset_email(email: str, token: str) -> None:
    ensure_email_configured()
    reset_url = (
        f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?"
        f"{urlencode({'token': token})}"
    )
    message = EmailMessage()
    message["Subject"] = "Reset your WorkFlow password"
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = email
    message.set_content(
        "We received a request to reset your WorkFlow password.\n\n"
        f"Use this link within {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes:\n"
        f"{reset_url}\n\n"
        "If you did not request a reset, you can ignore this email."
    )

    send_email(message)


def send_account_deletion_code(email: str, code: str) -> None:
    ensure_email_configured()
    message = EmailMessage()
    message["Subject"] = "Confirm your WorkFlow account deletion"
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = email
    message.set_content(
        "A request was made to delete your WorkFlow account.\n\n"
        f"Your confirmation code is: {code}\n\n"
        f"This code expires in {settings.ACCOUNT_DELETION_CODE_EXPIRE_MINUTES} minutes "
        "and can only be used once. If you did not request this, ignore this email."
    )

    send_email(message)
