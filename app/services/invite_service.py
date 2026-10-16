import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.invite import Invite
from app.models.team import Team
from app.models.team_membership import TeamMembership
from app.models.user import User
from app.schemas.invite import InviteCreate
from app.core import security
from app.core.config import settings
from app.services import password_reset_service
from app.services.email_service import send_email
from app.services import notification_service

logger = logging.getLogger(__name__)


class ExistingTeamMemberError(ValueError):
    pass


def send_team_invite_email(email: str, team_name: str, token: str) -> None:
    invite_url = (
        f"{settings.FRONTEND_URL.rstrip('/')}/login?"
        f"{urlencode({'invite': token})}"
    )
    message = EmailMessage()
    message["Subject"] = f"You're invited to join {team_name} on WorkFlow"
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = email
    message.set_content(
        f"You've been invited to join {team_name} on WorkFlow.\n\n"
        "Sign in with this email address, or create an account, to accept the invitation:\n"
        f"{invite_url}\n\n"
        "If you weren't expecting this invitation, you can ignore this email."
    )
    send_email(message)


def create_invite(db: Session, team_id: int, invite: InviteCreate, invited_by: int):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise ValueError("Team not found")
    password_reset_service.ensure_email_configured()

    user = db.query(User).filter(func.lower(User.email) == invite.email.lower()).first()
    if user and db.query(TeamMembership.id).filter_by(
        team_id=team_id,
        user_id=user.id,
    ).first():
        raise ExistingTeamMemberError("This user is already a member of the team")

    token = security.generate_invite_token()
    db_invite = Invite(
        team_id=team_id,
        invited_by=invited_by,
        email=invite.email,
        token=token,
        status="pending",
    )
    db.add(db_invite)
    db.commit()
    db.refresh(db_invite)
    try:
        send_team_invite_email(invite.email, team.name, token)
    except (OSError, smtplib.SMTPException) as error:
        db_invite.status = "revoked"
        db.commit()
        logger.error("Could not send team invitation email (%s)", type(error).__name__)
        raise RuntimeError("Team invitation email could not be sent right now.") from None
    return db_invite


def get_invite_by_token(db: Session, token: str):
    return db.query(Invite).filter(Invite.token == token).first()


def list_team_invites(db: Session, team_id: int):
    return db.query(Invite).filter(Invite.team_id == team_id).all()


def list_pending_invites(db: Session, email: str):
    return (
        db.query(Invite)
        .filter(
            func.lower(Invite.email) == email.lower(),
            Invite.status == "pending",
        )
        .order_by(Invite.created_at.desc(), Invite.id.desc())
        .all()
    )


def accept_invite(db: Session, token: str, current_user: User):
    invite = get_invite_by_token(db, token)
    if not invite:
        raise ValueError("Invite not found")
    if invite.status != "pending":
        raise ValueError("Invite is no longer valid")
    if invite.email.lower() != current_user.email.lower():
        raise PermissionError("This invite was not sent to your account")

    existing = db.query(TeamMembership).filter_by(team_id=invite.team_id, user_id=current_user.id).first()
    if not existing:
        membership = TeamMembership(team_id=invite.team_id, user_id=current_user.id, role_in_team="member")
        db.add(membership)
        db.flush()
        team = db.query(Team).filter(Team.id == invite.team_id).first()
        notification_service.notify_team(
            db,
            invite.team_id,
            current_user.id,
            "member_joined",
            "New team member",
            f"{current_user.name} joined “{team.name if team else 'the team'}”.",
        )

    invite.status = "accepted"
    db.commit()
    return invite