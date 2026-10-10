from typing import List, Optional

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session, aliased

from app.models.message import Message
from app.models.team_membership import TeamMembership
from app.models.user import User
from app.schemas.message import MessageCreate, MessageUpdate

DELETED_MESSAGE_CONTENT = "This message was deleted"


# ---------- helpers ----------

def is_team_member(db: Session, team_id: int, user_id: int) -> bool:
    return (
        db.query(TeamMembership.id)
        .filter(TeamMembership.team_id == team_id, TeamMembership.user_id == user_id)
        .first()
        is not None
    )


def get_team_member_ids(db: Session, team_id: int) -> List[int]:
    rows = db.query(TeamMembership.user_id).filter(TeamMembership.team_id == team_id).all()
    return [row[0] for row in rows]


def share_team(db: Session, first_user_id: int, second_user_id: int) -> bool:
    first_membership = aliased(TeamMembership)
    second_membership = aliased(TeamMembership)
    return (
        db.query(first_membership.id)
        .join(second_membership, second_membership.team_id == first_membership.team_id)
        .filter(
            first_membership.user_id == first_user_id,
            second_membership.user_id == second_user_id,
        )
        .first()
        is not None
    )


# ---------- sending ----------

def create_message(db: Session, sender_id: int, data: MessageCreate) -> Message:
    """
    Validates and saves a message. The sender always comes from the
    authenticated user, never from the client payload.
    Raises PermissionError / ValueError like the other services.
    """
    if data.team_id is not None:
        if not is_team_member(db, data.team_id, sender_id):
            raise PermissionError("You must be a member of this team to send messages")
    else:
        if data.recipient_id == sender_id:
            raise ValueError("You can't message yourself")
        recipient_exists = db.query(User.id).filter(User.id == data.recipient_id).first()
        if not recipient_exists:
            raise ValueError("User not found")
        if not share_team(db, sender_id, data.recipient_id):
            raise PermissionError("You can only message people who share a team with you")

    db_message = Message(
        sender_id=sender_id,
        team_id=data.team_id,
        recipient_id=data.recipient_id,
        content=data.content,
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message


def _get_owned_message(db: Session, message_id: int, sender_id: int) -> Message:
    message = db.query(Message).filter(Message.id == message_id).first()
    if message is None:
        raise LookupError("Message not found")
    if message.sender_id != sender_id:
        raise PermissionError("You can only change your own messages")
    if message.team_id is not None and not is_team_member(db, message.team_id, sender_id):
        raise PermissionError("You must be a member of this team to change its messages")
    if message.deleted_at is not None:
        raise ValueError("This message has already been deleted")
    return message


def update_message(
    db: Session, message_id: int, sender_id: int, data: MessageUpdate
) -> Message:
    message = _get_owned_message(db, message_id, sender_id)
    message.content = data.content
    message.edited_at = func.now()
    db.commit()
    db.refresh(message)
    return message


def delete_message(db: Session, message_id: int, sender_id: int) -> Message:
    message = _get_owned_message(db, message_id, sender_id)
    message.content = DELETED_MESSAGE_CONTENT
    message.deleted_at = func.now()
    db.commit()
    db.refresh(message)
    return message


def get_message_recipient_ids(db: Session, message: Message) -> List[int]:
    if message.team_id is not None:
        return get_team_member_ids(db, message.team_id)
    return [message.sender_id, message.recipient_id]


# ---------- history ----------

def get_team_messages(
    db: Session, team_id: int, before_id: Optional[int], limit: int
) -> List[Message]:
    """Newest first. Pass the smallest id you already have as before_id to load older ones."""
    query = db.query(Message).filter(Message.team_id == team_id)
    if before_id is not None:
        query = query.filter(Message.id < before_id)
    return query.order_by(Message.id.desc()).limit(limit).all()


def get_direct_messages(
    db: Session,
    current_user_id: int,
    other_user_id: int,
    before_id: Optional[int],
    limit: int,
) -> List[Message]:
    """Conversation between the current user and one other user, newest first."""
    other_exists = db.query(User.id).filter(User.id == other_user_id).first()
    if not other_exists:
        raise ValueError("User not found")
    if not share_team(db, current_user_id, other_user_id):
        raise PermissionError("You can only message people who share a team with you")

    # both directions: A -> B  OR  B -> A
    # (team messages have recipient_id NULL, so they never match here)
    query = db.query(Message).filter(
        or_(
            and_(
                Message.sender_id == current_user_id,
                Message.recipient_id == other_user_id,
            ),
            and_(
                Message.sender_id == other_user_id,
                Message.recipient_id == current_user_id,
            ),
        )
    )
    if before_id is not None:
        query = query.filter(Message.id < before_id)
    return query.order_by(Message.id.desc()).limit(limit).all()


def get_conversations(db: Session, current_user_id: int) -> List[Message]:
    """
    Inbox: the latest message of each DM conversation the user is part of,
    newest conversation first. The other person in each conversation is
    whichever of sender_id / recipient_id isn't the current user.
    """
    partner_id = case(
        (Message.sender_id == current_user_id, Message.recipient_id),
        else_=Message.sender_id,
    )
    own_membership = aliased(TeamMembership)
    contact_membership = aliased(TeamMembership)
    contact_ids = (
        db.query(contact_membership.user_id)
        .join(own_membership, own_membership.team_id == contact_membership.team_id)
        .filter(own_membership.user_id == current_user_id)
        .distinct()
    )

    latest = (
        db.query(func.max(Message.id).label("last_id"))
        .filter(
            Message.team_id.is_(None),
            partner_id.in_(contact_ids),
            or_(
                Message.sender_id == current_user_id,
                Message.recipient_id == current_user_id,
            ),
        )
        .group_by(partner_id)
        .subquery()
    )

    return (
        db.query(Message)
        .join(latest, Message.id == latest.c.last_id)
        .order_by(Message.id.desc())
        .all()
    )