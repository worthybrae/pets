from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from uuid import UUID
import json

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections for real-time pet updates."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, pet_id: str):
        await websocket.accept()
        if pet_id not in self.active_connections:
            self.active_connections[pet_id] = []
        self.active_connections[pet_id].append(websocket)

    def disconnect(self, websocket: WebSocket, pet_id: str):
        if pet_id in self.active_connections:
            self.active_connections[pet_id].remove(websocket)
            if not self.active_connections[pet_id]:
                del self.active_connections[pet_id]

    async def broadcast(self, pet_id: str, message: dict):
        if pet_id in self.active_connections:
            for connection in self.active_connections[pet_id]:
                await connection.send_json(message)


manager = ConnectionManager()


@router.websocket("/pets/{pet_id}/ws")
async def websocket_endpoint(websocket: WebSocket, pet_id: UUID):
    """WebSocket for real-time pet updates."""
    pet_id_str = str(pet_id)
    await manager.connect(websocket, pet_id_str)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            # Echo back for now (stub)
            await websocket.send_json(
                {"type": "ack", "message": f"Received: {message}"}
            )
    except WebSocketDisconnect:
        manager.disconnect(websocket, pet_id_str)
