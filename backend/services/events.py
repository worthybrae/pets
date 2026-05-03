"""Event broadcasting service for real-time updates via WebSocket."""

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class EventBroadcaster:
    """
    Central event bus for broadcasting real-time updates.
    Other services call these methods to push updates to all connected clients.
    """

    def __init__(self, connection_manager: Any):
        self.manager = connection_manager

    async def voxel_placed(self, pet_id: str, voxels: list[dict]) -> None:
        """Broadcast voxel placement to all watchers."""
        await self.manager.broadcast(pet_id, {
            "type": "voxel_update",
            "action": "place",
            "voxels": voxels,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def voxel_removed(self, pet_id: str, positions: list[dict]) -> None:
        """Broadcast voxel removal to all watchers."""
        await self.manager.broadcast(pet_id, {
            "type": "voxel_update",
            "action": "remove",
            "voxels": positions,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def pet_moved(self, pet_id: str, position: dict) -> None:
        """Broadcast pet movement to all watchers."""
        await self.manager.broadcast(pet_id, {
            "type": "pet_moved",
            "position": position,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def chat_message(self, pet_id: str, sender: str, message: str) -> None:
        """Broadcast a chat message to all watchers."""
        await self.manager.broadcast(pet_id, {
            "type": "chat",
            "sender": sender,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def artifact_placed(self, pet_id: str, artifact: dict) -> None:
        """Broadcast artifact placement to all watchers."""
        await self.manager.broadcast(pet_id, {
            "type": "artifact_placed",
            "artifact": artifact,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def food_updated(self, pet_id: str, balance: float) -> None:
        """Broadcast food balance update to all watchers."""
        await self.manager.broadcast(pet_id, {
            "type": "food_update",
            "balance": balance,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def status_changed(self, pet_id: str, status: str) -> None:
        """Broadcast status change to all watchers."""
        await self.manager.broadcast(pet_id, {
            "type": "status_change",
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


# Global broadcaster instance — initialized when the WebSocket manager is ready.
_broadcaster: EventBroadcaster | None = None


def get_broadcaster() -> EventBroadcaster | None:
    """Get the global EventBroadcaster instance."""
    return _broadcaster


def set_broadcaster(broadcaster: EventBroadcaster) -> None:
    """Set the global EventBroadcaster instance."""
    global _broadcaster
    _broadcaster = broadcaster
