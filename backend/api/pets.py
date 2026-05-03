from fastapi import APIRouter, HTTPException
from uuid import UUID, uuid4
from datetime import date, datetime

from backend.models.pet import Pet, PetCreate
from backend.models.world import WorldChunk
from backend.models.memory import DigestedNote
from backend.models.artifact import Artifact
from backend.models.agenda import Agenda
from backend.models.social import SocialGraphEntry

router = APIRouter()


@router.post("/pets", response_model=Pet)
async def create_pet(pet: PetCreate):
    """Create a new pet."""
    return Pet(
        id=uuid4(),
        owner_id=uuid4(),
        name=pet.name,
        seed_curiosity=pet.seed_curiosity,
        food_balance=100.0,
        status="idle",
        position_x=0.0,
        position_y=0.0,
        position_z=0.0,
        created_at=datetime.utcnow(),
    )


@router.get("/pets/{pet_id}", response_model=Pet)
async def get_pet(pet_id: UUID):
    """Get pet info."""
    # Stub: return placeholder
    return Pet(
        id=pet_id,
        owner_id=uuid4(),
        name="Placeholder Pet",
        seed_curiosity="Loves exploring dark caves",
        food_balance=100.0,
        status="idle",
        position_x=0.0,
        position_y=0.0,
        position_z=0.0,
        created_at=datetime.utcnow(),
    )


@router.get("/pets/{pet_id}/world", response_model=list[WorldChunk])
async def get_world(pet_id: UUID):
    """Get world chunks for a pet."""
    return []


@router.post("/pets/{pet_id}/chat")
async def chat(pet_id: UUID, message: dict):
    """Send a chat message to a pet."""
    return {
        "pet_id": str(pet_id),
        "response": "Hello! I'm still waking up... (stub response)",
        "food_cost": 1.0,
    }


@router.get("/pets/{pet_id}/memories", response_model=list[DigestedNote])
async def get_memories(pet_id: UUID, query: str = ""):
    """Search pet memories."""
    return []


@router.get("/pets/{pet_id}/artifacts", response_model=list[Artifact])
async def get_artifacts(pet_id: UUID):
    """List artifacts created by a pet."""
    return []


@router.get("/pets/{pet_id}/agenda", response_model=Agenda | None)
async def get_agenda(pet_id: UUID):
    """Get today's agenda for a pet."""
    return Agenda(
        id=uuid4(),
        pet_id=pet_id,
        date=date.today(),
        plan={"tasks": []},
        current_task=None,
        food_allocated=50.0,
        food_spent=0.0,
    )


@router.get("/pets/{pet_id}/neighbors", response_model=list[SocialGraphEntry])
async def get_neighbors(pet_id: UUID):
    """Get nearby pets in the social graph."""
    return []
