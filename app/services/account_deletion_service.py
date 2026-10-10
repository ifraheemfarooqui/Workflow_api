import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.models.account_deletion_code import AccountDeletionCode
from app.models.comment import Comment
from app.models.invite import Invite
from app.models.message import Message
from app.models.password_reset_token import PasswordResetToken
from app.models.task import Task
from app.models.team_membership import TeamMembership
from app.models.user import User


def ensure_can_delete_account(db: Session, user_id: int) -> None:
    manager_memberships = db.query(TeamMembership).filter(
        TeamMembership.user_id == user_id,
        TeamMembership.role_in_team == "manager",
    ).all()
    for membership in manager_memberships:
        other_manager = db.query(TeamMembership.id).filter(
            TeamMembership.team_id == membership.team_id,
            TeamMembership.role_in_team == "manager",
            TeamMembership.user_id != user_id,
        ).first()
        if other_manager is None:
            team_name = membership.team.name
            raise ValueError(
                f"Transfer manager access for team '{team_name}' before deleting your account."
            )


def issue_deletion_code(db: Session, user: User) -> str | None:
    now = datetime.now(timezone.utc)
    latest = (
        db.query(AccountDeletionCode)
        .filter(AccountDeletionCode.user_id == user.id)
        .order_by(AccountDeletionCode.created_at.desc())
        .first()
    )
    if latest is not None:
        created_at = latest.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if (now - created_at).total_seconds() < settings.ACCOUNT_DELETION_CODE_COOLDOWN_SECONDS:
            return None

    db.query(AccountDeletionCode).filter(
        AccountDeletionCode.user_id == user.id,
        AccountDeletionCode.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)

    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(AccountDeletionCode(
        user_id=user.id,
        code_hash=security.hash_account_deletion_code(code, user.id),
        expires_at=now + timedelta(minutes=settings.ACCOUNT_DELETION_CODE_EXPIRE_MINUTES),
    ))
    db.commit()
    return code


def revoke_deletion_code(db: Session, user_id: int, code: str) -> None:
    code_hash = security.hash_account_deletion_code(code, user_id)
    record = db.query(AccountDeletionCode).filter(
        AccountDeletionCode.user_id == user_id,
        AccountDeletionCode.code_hash == code_hash,
        AccountDeletionCode.used_at.is_(None),
    ).first()
    if record is not None:
        db.delete(record)
        db.commit()


def confirm_account_deletion(db: Session, user: User, code: str) -> None:
    record = (
        db.query(AccountDeletionCode)
        .filter(
            AccountDeletionCode.user_id == user.id,
            AccountDeletionCode.used_at.is_(None),
        )
        .order_by(AccountDeletionCode.created_at.desc())
        .with_for_update()
        .first()
    )
    now = datetime.now(timezone.utc)
    if record is None:
        raise ValueError("The confirmation code is invalid or has expired.")

    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        record.used_at = now
        db.commit()
        raise ValueError("The confirmation code is invalid or has expired.")

    if record.attempts >= settings.ACCOUNT_DELETION_CODE_MAX_ATTEMPTS:
        record.used_at = now
        db.commit()
        raise ValueError("Too many incorrect attempts. Request a new confirmation code.")

    provided_hash = security.hash_account_deletion_code(code, user.id)
    if not hmac.compare_digest(record.code_hash, provided_hash):
        record.attempts += 1
        if record.attempts >= settings.ACCOUNT_DELETION_CODE_MAX_ATTEMPTS:
            record.used_at = now
        db.commit()
        raise ValueError("The confirmation code is incorrect.")

    ensure_can_delete_account(db, user.id)

    db.query(Task).filter(Task.assigned_to == user.id).update(
        {"assigned_to": None},
        synchronize_session=False,
    )
    db.query(Comment).filter(Comment.user_id == user.id).update(
        {"user_id": None},
        synchronize_session=False,
    )
    db.query(Message).filter(Message.sender_id == user.id).update(
        {"sender_id": None},
        synchronize_session=False,
    )
    db.query(Invite).filter(
        or_(
            Invite.invited_by == user.id,
            func.lower(Invite.email) == user.email.lower(),
        )
    ).delete(synchronize_session=False)
    db.query(TeamMembership).filter(TeamMembership.user_id == user.id).delete(
        synchronize_session=False,
    )
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete(
        synchronize_session=False,
    )
    db.query(AccountDeletionCode).filter(AccountDeletionCode.user_id == user.id).delete(
        synchronize_session=False,
    )

    user.name = "Deleted user"
    user.email = f"deleted-{user.id}@deleted.invalid"
    user.hashed_password = security.hash_password(secrets.token_urlsafe(48))
    user.is_deleted = True
    user.token_version += 1
    db.commit()
