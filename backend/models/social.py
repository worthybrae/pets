from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class SocialGraphEntry(BaseModel):
    """An edge in the pet social graph."""

    id: UUID
    pet_id: UUID
    neighbor_id: UUID
    distance: float
    created_at: datetime


class VisitLog(BaseModel):
    """A record of one pet visiting another."""

    id: UUID
    visitor_id: UUID
    host_id: UUID
    started_at: datetime
    ended_at: datetime | None = None
