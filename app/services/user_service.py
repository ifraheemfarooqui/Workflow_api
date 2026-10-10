from sqlalchemy import func, or_
from sqlalchemy.orm import Session, aliased
from app.models.team_membership import TeamMembership
from app.models.user import User
from app.schemas.user import UserCreate
from app.core import security
from app.services import invite_service

def create_user(db: Session, user: UserCreate):
    hashed = security.hash_password(user.password)
    db_user = User(name=user.name, email=user.email, hashed_password=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    if user.invite_token:
        try:
            invite_service.accept_invite(db, user.invite_token, db_user)
        except (ValueError, PermissionError):
            pass  # invalid/expired/mismatched invite shouldn't block registration

    return db_user

def create_users_bulk(db: Session, users: list[UserCreate]):
    created = []
    skipped = []

    for user in users:
        existing = db.query(User).filter(User.email == user.email).first()
        if existing:
            skipped.append(user.email)
            continue

        hashed = security.hash_password(user.password)
        db_user = User(name=user.name, email=user.email, hashed_password=hashed)
        db.add(db_user)
        created.append(db_user)

    db.commit()
    for u in created:
        db.refresh(u)

    return created, skipped

def get_user(db:Session, user_id:int):
    return db.query(User).filter(User.id==user_id, User.is_deleted.is_(False)).first()
def get_users(db:Session, skip:int=0,limit:int=10):
    return db.query(User).offset(skip).limit(limit).all()

def get_team_contacts(db: Session, current_user_id: int, skip: int = 0, limit: int = 100, search: str | None = None):
    own_membership = aliased(TeamMembership)
    contact_membership = aliased(TeamMembership)
    query = (
        db.query(User)
        .join(contact_membership, contact_membership.user_id == User.id)
        .join(own_membership, own_membership.team_id == contact_membership.team_id)
        .filter(own_membership.user_id == current_user_id, User.id != current_user_id, User.is_deleted.is_(False))
        .distinct()
    )
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(User.name.ilike(pattern), User.email.ilike(pattern)))
    return query.order_by(User.name, User.id).offset(skip).limit(limit).all()

def is_team_contact(db: Session, first_user_id: int, second_user_id: int) -> bool:
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

def get_user_by_email(db:Session,email:str):
    return db.query(User).filter(User.email == email, User.is_deleted.is_(False)).first()

def update_user_profile(db: Session, user: User, name: str, email: str):
    user.name = name
    user.email = email
    db.commit()
    db.refresh(user)
    return user

def update_password(db: Session, user: User, password: str):
    from app.models.password_reset_token import PasswordResetToken

    user.hashed_password = security.hash_password(password)
    user.token_version += 1
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({"used_at": func.now()}, synchronize_session=False)
    db.commit()
    db.refresh(user)
    return user
