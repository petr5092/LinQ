import asyncio
from typing import List, Optional
from fastapi import WebSocket


class ConnectionManager:
    """Менеджер активных WebSocket-соединений для real-time оповещений."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Широковещательная рассылка сообщения всем подключенным диспетчерам."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)

    def broadcast_sync(self, message: dict) -> None:
        """Синхронный вызов рассылки из фонового потока (CV-воркера или Telegram)."""
        loop = self._loop
        if loop and loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self.broadcast(message), loop)
                return
            except RuntimeError:
                pass

        try:
            cur_loop = asyncio.get_running_loop()
            if cur_loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast(message), cur_loop)
        except RuntimeError:
            pass

    @property
    def count(self) -> int:
        return len(self.active_connections)


notifier = ConnectionManager()
