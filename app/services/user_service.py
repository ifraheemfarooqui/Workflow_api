from sqlalchemy.orm import Session
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
    return db.query(User).filter(User.id==user_id).first()
def get_users(db:Session, skip:int=0,limit:int=10):
    return db.query(User).offset(skip).limit(limit).all()

def get_user_by_email(db:Session,email:str):
    return db.query(User).filter(User.email == email).first()
