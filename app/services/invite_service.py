from sqlalchemy.orm import Session
from app.models.invite import Invite
from app.models.team import Team
from app.models.team_membership import TeamMembership
from app.models.user import User
from app.schemas.invite import InviteCreate
from app.core.security import generate_invite_token


def create_invite(db: Session, team_id: int, invite: InviteCreate, invited_by: int):
    if not db.query(Team).filter(Team.id == team_id).first():
        raise ValueError("Team not found")

    token = generate_invite_token()
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
    return db_invite


def get_invite_by_token(db: Session, token: str):
    return db.query(Invite).filter(Invite.token == token).first()


def list_team_invites(db: Session, team_id: int):
    return db.query(Invite).filter(Invite.team_id == team_id).all()


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

    invite.status = "accepted"
    db.commit()
    return invite