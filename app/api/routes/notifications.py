from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import NotificationOut
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", response_model=list[NotificationOut])
def list_notifications(
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return notification_service.list_notifications(db, current_user.id, limit)


@router.patch("/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = notification_service.mark_read(db, notification_id, current_user.id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@router.post("/read-all", status_code=204)
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification_service.mark_all_read(db, current_user.id)
