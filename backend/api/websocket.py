"""WebSocket endpoint for real-time pet updates and chat."""

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.services.events import EventBroadcaster, set_broadcaster
from backend.services.brain import PetBrain
from backend.services.food import check_food, initialize_food
from backend.services.lock import PetLock

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections per pet."""

    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, pet_id: str, websocket: WebSocket) -> None:
        """Accept and register a connection for a pet."""
        await websocket.accept()
        if pet_id not in self.connections:
            self.connections[pet_id] = []
        self.connections[pet_id].append(websocket)
        logger.info(
            f"WebSocket connected for pet {pet_id}. "
            f"Total connections: {len(self.connections[pet_id])}"
        )

    async def disconnect(self, pet_id: str, websocket: WebSocket) -> None:
        """Remove a connection."""
        if pet_id in self.connections:
            try:
                self.connections[pet_id].remove(websocket)
            except ValueError:
                pass
            if not self.connections[pet_id]:
                del self.connections[pet_id]
        logger.info(f"WebSocket disconnected for pet {pet_id}.")

    async def broadcast(self, pet_id: str, message: dict) -> None:
        """Send a message to all connections watching a pet."""
        if pet_id not in self.connections:
            return
        disconnected: list[WebSocket] = []
        for connection in self.connections[pet_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket for pet {pet_id}: {e}")
                disconnected.append(connection)
        # Clean up dead connections
        for conn in disconnected:
            try:
                self.connections[pet_id].remove(conn)
            except ValueError:
                pass
        if pet_id in self.connections and not self.connections[pet_id]:
            del self.connections[pet_id]

    def get_connection_count(self, pet_id: str) -> int:
        """Get the number of active connections for a pet."""
        return len(self.connections.get(pet_id, []))


# Global manager and broadcaster instances
manager = ConnectionManager()
broadcaster = EventBroadcaster(manager)

# Register the broadcaster globally so other services can use it
set_broadcaster(broadcaster)


# Shared lock instance
_lock = PetLock()


@router.websocket("/pets/{pet_id}/ws")
async def pet_websocket(websocket: WebSocket, pet_id: str):
    """
    WebSocket for real-time updates.

    Client connects and receives:
    - Chat messages (from pet's autonomous thoughts or responses)
    - Voxel changes (place/remove)
    - Pet movement
    - Status updates
    - Food balance updates

    Client can send:
    - {"type": "chat", "message": "..."} — Chat message to the pet
    - {"type": "ping"} — Keepalive ping
    """
    pet_id_str = str(pet_id)
    await manager.connect(pet_id_str, websocket)

    # Send initial connection confirmation
    await websocket.send_json({
        "type": "connected",
        "pet_id": pet_id_str,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                })
                continue

            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "chat":
                user_message = data.get("message", "").strip()
                if not user_message:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Empty chat message",
                    })
                    continue

                # Broadcast the user's message to all watchers
                await broadcaster.chat_message(pet_id_str, "user", user_message)

                # Process chat through the pet brain
                await _process_chat(pet_id_str, user_message)

            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        await manager.disconnect(pet_id_str, websocket)
    except Exception as e:
        logger.error(f"WebSocket error for pet {pet_id_str}: {e}")
        await manager.disconnect(pet_id_str, websocket)


async def _process_chat(pet_id: str, user_message: str) -> None:
    """Process a chat message through the pet brain and broadcast the response."""
    # Acquire chat lock
    acquired = await _lock.acquire(pet_id, mode="chat", timeout=300)
    if not acquired:
        await broadcaster.chat_message(
            pet_id, "system", "Pet is busy right now. Try again in a moment."
        )
        return

    try:
        # Get food balance
        food_balance = await check_food(pet_id)
        if food_balance <= 0:
            await broadcaster.chat_message(
                pet_id, "system", "Pet has no food and cannot respond."
            )
            return

        # Build minimal pet state for the brain
        pet_state = {
            "name": "Pet",  # Will be populated from DB in production
            "seed_curiosity": "the unknown",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "food_balance": food_balance,
            "position": {"x": 0, "y": 0, "z": 0},
            "memories": [],
            "digested_notes": [],
            "agenda": [],
        }

        # Run the brain
        brain = PetBrain(pet_id, pet_state)
        result = await brain.think(
            trigger="user_chat",
            context={"user_message": user_message},
        )

        # Broadcast pet's response
        if result.response_to_user:
            await broadcaster.chat_message(pet_id, "pet", result.response_to_user)

        # Broadcast food update
        remaining_food = await check_food(pet_id)
        await broadcaster.food_updated(pet_id, remaining_food)

        # If there was an error, let the user know
        if result.error:
            await broadcaster.chat_message(
                pet_id, "system", f"Error: {result.error}"
            )

    except Exception as e:
        logger.error(f"Chat processing error for pet {pet_id}: {e}")
        await broadcaster.chat_message(
            pet_id, "system", "Something went wrong processing your message."
        )
    finally:
        await _lock.release(pet_id, mode="chat")
