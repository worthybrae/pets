from pydantic import BaseModel
from uuid import UUID
from datetime import date
from typing import Any


class Agenda(BaseModel):
    """A pet's daily agenda / plan."""

    id: UUID
    pet_id: UUID
    date: date
    plan: dict[str, Any]  # JSONB plan structure
    current_task: str | None
    food_allocated: float
    food_spent: float
