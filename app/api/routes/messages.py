from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.connection_manager import manager
from app.api.deps import get_current_user, require_team_member
from app.db.session import get_db
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageOut, MessageUpdate
from app.services import message_service

router = APIRouter(tags=["Messages"])


def _change_message(
    db: Session,
    message_id: int,
    current_user: User,
    update: Optional[MessageUpdate] = None,
) -> tuple[Message, List[int], str]:
    try:
        if update is None:
            message = message_service.delete_message(db, message_id, current_user.id)
            event_type = "message_deleted"
        else:
            message = message_service.update_message(db, message_id, current_user.id, update)
            event_type = "message_updated"
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    recipients = message_service.get_message_recipient_ids(db, message)
    return message, recipients, event_type


@router.get("/teams/{team_id}/messages", response_model=List[MessageOut])
def team_messages(
    team_id: int,
    before_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_team_member),
):
    return message_service.get_team_messages(db, team_id, before_id, limit)


@router.get("/messages/conversations", response_model=List[MessageOut])
def my_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return message_service.get_conversations(db, current_user.id)


@router.get("/messages/direct/{user_id}", response_model=List[MessageOut])
def direct_messages(
    user_id: int,
    before_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You can't open a conversation with yourself")
    try:
        return message_service.get_direct_messages(db, current_user.id, user_id, before_id, limit)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/messages/{message_id}", response_model=MessageOut)
async def edit_message(
    message_id: int,
    update: MessageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    message, recipients, event_type = await run_in_threadpool(
        _change_message, db, message_id, current_user, update
    )
    await manager.send_to_users(
        recipients,
        {"type": event_type, "data": MessageOut.model_validate(message).model_dump(mode="json")},
    )
    return message


@router.delete("/messages/{message_id}", response_model=MessageOut)
async def remove_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    message, recipients, event_type = await run_in_threadpool(
        _change_message, db, message_id, current_user
    )
    await manager.send_to_users(
        recipients,
        {"type": event_type, "data": MessageOut.model_validate(message).model_dump(mode="json")},
    )
    return message