from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class RawEvent(BaseModel):
    """Tier 1: Raw events (chat messages, observations, actions)."""

    id: UUID
    pet_id: UUID
    event_type: str
    content: str
    embedding: list[float] | None = None
    created_at: datetime


class DigestedNote(BaseModel):
    """Tier 2: Digested notes (summarized from raw events)."""

    id: UUID
    pet_id: UUID
    topic: str
    content: str
    embedding: list[float] | None = None
    created_at: datetime


class KnowledgeBase(BaseModel):
    """Tier 3: Long-term knowledge (stable facts and preferences)."""

    id: UUID
    pet_id: UUID
    key: str
    content: str
    embedding: list[float] | None = None
    updated_at: datetime
