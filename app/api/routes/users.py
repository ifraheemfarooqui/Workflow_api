import smtplib

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.core.connection_manager import manager
from app.core import security
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    AccountDeletionConfirmation,
    AccountDeletionRequest,
    BulkUserCreate,
    UserCreate,
    UserOut,
    UserProfileUpdate,
)
from app.services import account_deletion_service, password_reset_service, user_service

router = APIRouter(prefix="/users", tags=["Users"])

class BulkUserResponse(BaseModel):
    created: list[UserOut]
    skipped_emails: list[str]

@router.post("/",response_model=UserOut)
def register_user(user: UserCreate, db:Session = Depends(get_db)):
    return user_service.create_user(db,user)

@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=UserOut)
def update_current_user(
    profile: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    name = profile.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name must not be blank")
    existing_user = user_service.get_user_by_email(db, profile.email)
    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(status_code=409, detail="Email is already registered")
    try:
        return user_service.update_user_profile(db, current_user, name, profile.email)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email is already registered")

@router.post("/me/deletion/request", status_code=202)
def request_account_deletion(
    payload: AccountDeletionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not security.verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    try:
        account_deletion_service.ensure_can_delete_account(db, current_user.id)
        password_reset_service.ensure_email_configured()
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error))

    code = account_deletion_service.issue_deletion_code(db, current_user)
    if code is not None:
        try:
            password_reset_service.send_account_deletion_code(current_user.email, code)
        except (OSError, smtplib.SMTPException) as error:
            password_reset_service.logger.error(
                "Could not send account deletion verification email (%s)", type(error).__name__
            )
            account_deletion_service.revoke_deletion_code(db, current_user.id, code)
            raise HTTPException(
                status_code=503,
                detail="Account deletion verification email could not be sent right now.",
            ) from None
    return {"message": "If eligible, a confirmation code has been sent to your account email."}

@router.post("/me/deletion/confirm")
async def confirm_account_deletion(
    payload: AccountDeletionConfirmation,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        account_deletion_service.confirm_account_deletion(db, current_user, payload.code)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    await manager.close_user_connections(current_user.id)
    return {"message": "Account deleted. You have been signed out."}

@router.get("/{user_id}", response_model=UserOut)
def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_user = user_service.get_user(db,user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    if db_user.id != current_user.id and not user_service.is_team_contact(db, current_user.id, db_user.id):
        raise HTTPException(status_code=403, detail="You can only view teammates")
    return db_user

@router.post("/bulk", response_model=BulkUserResponse)
def register_users_bulk(payload: BulkUserCreate, db: Session = Depends(get_db)):
    created, skipped = user_service.create_users_bulk(db, payload.users)
    return BulkUserResponse(created=created, skipped_emails=skipped)

@router.get("/", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    search: str | None = Query(None, min_length=1, max_length=100),
    current_user: User = Depends(get_current_user)
):
    return user_service.get_team_contacts(db, current_user.id, skip, limit, search)