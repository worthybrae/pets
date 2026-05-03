from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class Artifact(BaseModel):
    """An artifact created by a pet and placed in the world."""

    id: UUID
    pet_id: UUID
    type: str  # e.g., "poem", "painting", "sculpture", "music"
    title: str
    description: str
    s3_key: str | None = None
    world_x: float
    world_y: float
    world_z: float
    created_at: datetime
