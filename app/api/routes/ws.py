import logging
import time
from collections import deque
from typing import Optional

import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.core import security
from app.core.connection_manager import manager
from app.db.session import SessionLocal
from app.models.user import User
from app.schemas.message import MessageCreate, MessageOut
from app.services import message_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])

# max messages per connection in a sliding window
RATE_LIMIT_MESSAGES = 10
RATE_LIMIT_WINDOW_SECONDS = 10


# ---------- sync helpers (run in a thread so they don't block the event loop) ----------

def _authenticate(token: Optional[str]) -> Optional[int]:
    """Returns the user id for a valid token, else None."""
    if not token:
        return None
    try:
        payload = security.decode_access_token(token)
        user_id = int(payload.get("sub"))
    except (jwt.PyJWTError, TypeError, ValueError):
        return None

    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
    if user is not None and (user.is_deleted or payload.get("ver", 0) != user.token_version):
        return None
    return user_id if user is not None else None


def _process_message(sender_id: int, raw: dict) -> tuple[dict, list[int]]:
    """
    Validate -> save -> work out who should receive it.
    Returns (payload to send, list of user ids to send it to).
    """
    data = MessageCreate.model_validate(raw)

    # short-lived session per message: we never hold a DB connection
    # for the whole life of a WebSocket
    with SessionLocal() as db:
        message = message_service.create_message(db, sender_id, data)

        if message.team_id is not None:
            # everyone in the team, which includes the sender (their echo/ack)
            recipients = message_service.get_team_member_ids(db, message.team_id)
        else:
            # the two people in the DM (sender's other tabs get it too)
            recipients = [message.sender_id, message.recipient_id]

        payload = {
            "type": "message",
            "data": MessageOut.model_validate(message).model_dump(mode="json"),
        }

    return payload, recipients


# ---------- endpoint ----------

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket, token: Optional[str] = Query(default=None)
):
    user_id = await run_in_threadpool(_authenticate, token)
    if user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    manager.connect(user_id, websocket)

    sent_at: deque[float] = deque()

    try:
        while True:
            # simple sliding-window rate limit — applied to every frame,
            # including invalid ones, so bad JSON can't bypass it
            now = time.monotonic()
            while sent_at and now - sent_at[0] > RATE_LIMIT_WINDOW_SECONDS:
                sent_at.popleft()
            if len(sent_at) >= RATE_LIMIT_MESSAGES:
                await websocket.send_json({"type": "error", "detail": "You're sending messages too fast"})
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                break
            sent_at.append(now)

            try:
                raw = await websocket.receive_json()
            except (ValueError, KeyError):
                # not valid JSON (or a binary frame)
                await websocket.send_json({"type": "error", "detail": "Messages must be valid JSON"})
                continue

            if await run_in_threadpool(_authenticate, token) != user_id:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                break

            try:
                payload, recipients = await run_in_threadpool(_process_message, user_id, raw)
            except ValidationError as e:  # must come before ValueError (it's a subclass)
                errors = e.errors()
                detail = errors[0]["msg"] if errors else "Invalid message"
                await websocket.send_json({"type": "error", "detail": detail})
            except (ValueError, PermissionError) as e:
                await websocket.send_json({"type": "error", "detail": str(e)})
            except SQLAlchemyError as error:
                logger.error("Database error while saving chat message (%s)", type(error).__name__)
                await websocket.send_json({"type": "error", "detail": "Could not send message"})
            else:
                await manager.send_to_users(recipients, payload)

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(user_id, websocket)