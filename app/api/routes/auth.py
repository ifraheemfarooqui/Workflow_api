import smtplib

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.core.connection_manager import manager
from app.db.session import get_db
from app.core import security
from app.models.user import User
from app.schemas.token import Token
from app.schemas.user import PasswordChange, PasswordReset, PasswordResetRequest
from app.services import password_reset_service, user_service

router = APIRouter(prefix="/auth",tags=["Auth"])

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = user_service.get_user_by_email(db, form_data.username)

    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = security.create_access_token(data={"sub": str(user.id), "ver": user.token_version})
    return Token(access_token=access_token, token_type="bearer")


@router.post("/change-password")
async def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not security.verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    if len(payload.new_password.encode("utf-8")) > 72:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must be at most 72 bytes")
    if security.verify_password(payload.new_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose a password you have not used before")
    user_service.update_password(db, current_user, payload.new_password)
    await manager.close_user_connections(current_user.id)
    return {"message": "Password updated. Please sign in again."}


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    try:
        password_reset_service.ensure_email_configured()
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))

    user = user_service.get_user_by_email(db, payload.email)
    if user is not None:
        token = password_reset_service.issue_reset_token(db, user)
        if token is not None:
            try:
                password_reset_service.send_password_reset_email(user.email, token)
            except (OSError, smtplib.SMTPException) as error:
                password_reset_service.logger.error(
                    "Could not send password recovery email (%s)", type(error).__name__
                )
                password_reset_service.revoke_reset_token(db, token)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Password recovery email could not be sent right now.",
                ) from None

    return {"message": "If an account exists for that email, password reset instructions have been sent."}


@router.post("/reset-password")
async def reset_password(payload: PasswordReset, db: Session = Depends(get_db)):
    if len(payload.new_password.encode("utf-8")) > 72:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must be at most 72 bytes")
    try:
        user_id = password_reset_service.reset_password(db, payload.token, payload.new_password)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    await manager.close_user_connections(user_id)
    return {"message": "Password reset. Please sign in with your new password."}