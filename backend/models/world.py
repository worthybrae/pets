from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Any


class WorldChunk(BaseModel):
    """A chunk of the voxel world owned by a pet."""

    id: UUID
    pet_id: UUID
    chunk_x: int
    chunk_y: int
    chunk_z: int
    voxel_data: dict[str, Any]  # JSONB voxel data
    updated_at: datetime


class WorldSnapshot(BaseModel):
    """A diff snapshot of world changes."""

    id: UUID
    pet_id: UUID
    diff_data: dict[str, Any]
    created_at: datetime
