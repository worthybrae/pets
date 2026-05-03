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
    rarity: str = "common"  # common, uncommon, rare, legendary, mythic
    stats: dict = {}  # {curiosity, creativity, social, focus, energy, resilience, humor} each 1-10
    backstory: str = ""  # AI-generated backstory
    initial_curiosity: str = ""  # User's initial curiosity description
    voxels: list = []  # [{x,y,z,r,g,b}, ...] pet body
    soul: str = ""  # Full personality document
    world_voxels: list = []  # [{x,y,z,r,g,b}, ...] starter world
