from typing import List
from fastapi import WebSocket


class ConnectionManager:
    """Менеджер активных WebSocket-соединений для real-time оповещений."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

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

    @property
    def count(self) -> int:
        return len(self.active_connections)


notifier = ConnectionManager()
