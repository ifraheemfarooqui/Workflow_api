from collections import defaultdict
from typing import Iterable
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Keeps track of who is online: user_id -> set of open WebSockets.
    It's a set because one user can have several tabs/devices connected.

    In-memory only, so it works with a SINGLE Uvicorn worker. With multiple
    workers each one would have its own phonebook (you'd need Redis pub/sub).
    """

    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)

    def connect(self, user_id: int, websocket: WebSocket) -> None:
        # the endpoint calls websocket.accept() before this
        self._connections[user_id].add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        sockets = self._connections.get(user_id)
        if not sockets:
            return
        sockets.discard(websocket)
        if not sockets:
            del self._connections[user_id]

    async def close_user_connections(self, user_id: int) -> None:
        for websocket in list(self._connections.get(user_id, ())):
            try:
                await websocket.close(code=1008, reason="Session expired")
            except RuntimeError:
                logger.debug("WebSocket was already closed")
            finally:
                self.disconnect(user_id, websocket)

    async def send_to_user(self, user_id: int, payload: dict) -> None:
        # copy to a list: disconnect() may modify the set while we loop
        for websocket in list(self._connections.get(user_id, ())):
            try:
                await websocket.send_json(payload)
            except Exception:
                # dead connection, drop it so it doesn't pile up
                self.disconnect(user_id, websocket)

    async def send_to_users(self, user_ids: Iterable[int], payload: dict) -> None:
        for user_id in set(user_ids):
            await self.send_to_user(user_id, payload)


manager = ConnectionManager()