from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class PetCreate(BaseModel):
    name: str
    seed_curiosity: str


class Pet(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    seed_curiosity: str
    food_balance: float
    status: str  # idle, exploring, building, chatting, sleeping
    position_x: float
    position_y: float
    position_z: float
    created_at: datetime
