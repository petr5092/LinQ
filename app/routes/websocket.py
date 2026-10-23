import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.notifier import notifier

router = APIRouter(tags=["WebSocket Realtime"])
logger = logging.getLogger("websocket")


@router.websocket("/ws/events")
async def websocket_events_endpoint(websocket: WebSocket):
    """
    WebSocket канал для получения оперативных оповещений об инцидентах в реальном времени.
    Диспетчерский веб-интерфейс подключается к ws://<host>:<port>/ws/events
    """
    await notifier.connect(websocket)
    try:
        # Отправляем подтверждение успешного рукопожатия
        await websocket.send_json({
            "event": "CONNECTED",
            "message": "Подключено к шине оповещений LinQ Safety Guard",
            "active_clients": notifier.count
        })

        while True:
            # Ожидаем входящие сообщения (например, ping-pong или подтверждения)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        notifier.disconnect(websocket)
    except Exception as e:
        logger.error(f"Ошибка в WebSocket соединении: {e}")
        notifier.disconnect(websocket)
