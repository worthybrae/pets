import asyncio
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from uuid import UUID, uuid4
from datetime import date, datetime

from backend.models.pet import Pet
from backend.models.world import WorldChunk
from backend.models.memory import DigestedNote
from backend.models.artifact import Artifact
from backend.models.agenda import Agenda
from backend.models.social import SocialGraphEntry
from backend.services.creation import create_pet as create_pet_service
from backend.services.brain import PetBrain, BrainResult
from backend.services.food import check_food, initialize_food, deduct_food
from backend.services.lock import PetLock
from backend.services.scheduler import PetScheduler
from backend.services.agenda import get_current_agenda, generate_daily_agenda
from backend.services.world import WorldService, load_pet_body, save_pet_body
from backend.services.db import insert_row, query_rows

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory pet store (will be replaced with DB)
_pets: dict[str, Pet] = {}

# Shared instances (initialized on first use)
_lock = PetLock()
_scheduler = PetScheduler()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    pet_id: str
    response: str
    actions: list[dict] = []
    food_consumed: float = 0.0
    error: str | None = None


class FeedRequest(BaseModel):
    amount: float


class FeedResponse(BaseModel):
    pet_id: str
    food_added: float
    new_balance: float
    rescheduled: bool


class CreatePetRequest(BaseModel):
    owner_id: str
    stats: dict | None = None
    rarity: str | None = None
    egg_color: str | None = None


@router.get("/pets/by-owner/{owner_id}")
async def get_pet_by_owner(owner_id: str):
    """Look up a pet by owner ID. Checks in-memory first, falls back to DB."""
    for pet in _pets.values():
        if str(pet.owner_id) == owner_id:
            return pet

    # Fallback: load from Supabase (survives server restarts)
    try:
        rows = await query_rows("pets", {"owner_id": owner_id}, limit=1)
        if rows:
            row = rows[0]
            pet_id = row["id"]
            # Load body voxels from pet_body table
            body_data = await load_pet_body(pet_id)
            voxels = []
            if body_data and body_data.get("voxels"):
                voxels = body_data["voxels"]

            pet = Pet(
                id=UUID(pet_id) if isinstance(pet_id, str) else pet_id,
                owner_id=UUID(owner_id),
                name=row.get("name", "Pet"),
                seed_curiosity=row.get("seed_curiosity", ""),
                food_balance=row.get("food_balance", 0.0),
                status=row.get("status", "idle"),
                position_x=row.get("position_x", 0.0),
                position_y=row.get("position_y", 0.0),
                position_z=row.get("position_z", 0.0),
                created_at=row.get("created_at", datetime.utcnow()),
                rarity=row.get("rarity", "common"),
                stats=row.get("stats", {}),
                backstory=row.get("backstory", ""),
                initial_curiosity=row.get("initial_curiosity", ""),
                voxels=voxels,
                soul=row.get("soul", ""),
                world_voxels=[],  # Loaded separately via /world endpoint
            )
            # Cache in memory for this session
            _pets[str(pet.id)] = pet
            return pet
    except Exception as e:
        logger.warning(f"DB fallback for owner {owner_id} failed: {e}")

    return {}


async def _run_birth_burst(pet_id: str, pet: Pet) -> None:
    """Background task: the creature's first burst of activity after being born."""
    try:
        food = await check_food(pet_id)
        pet_state = {
            "name": pet.name,
            "seed_curiosity": pet.seed_curiosity,
            "created_at": pet.created_at.isoformat(),
            "food_balance": food,
            "position": {"x": 0, "y": 0, "z": 0},
            "memories": [],
            "digested_notes": [],
            "agenda": [],
            "soul": getattr(pet, "soul", ""),
            "stats": getattr(pet, "stats", {}),
        }

        brain = PetBrain(pet_id, pet_state)
        result = await brain.think(trigger="birth", context={})

        # Update food balance on the pet object
        remaining = await check_food(pet_id)
        pet.food_balance = remaining

        logger.info(
            f"Birth burst for {pet.name} ({pet_id}): "
            f"{len(result.actions)} actions, ${result.food_consumed:.6f} consumed, "
            f"${remaining:.6f} remaining"
        )

        # Now generate the agenda for the rest of the day and schedule
        agenda_state = {
            "name": pet.name,
            "seed_curiosity": pet.seed_curiosity,
            "memories": [],
        }
        await generate_daily_agenda(pet_id, agenda_state)
        await _scheduler.schedule_pet(pet_id, remaining)

    except Exception as e:
        logger.error(f"Birth burst failed for pet {pet_id}: {e}")


@router.post("/pets", response_model=Pet)
async def create_pet(request: CreatePetRequest):
    """Create a new pet with rolled stats, rarity, and species."""
    new_pet = await create_pet_service(request.owner_id, request.stats, request.rarity, request.egg_color)
    _pets[str(new_pet.id)] = new_pet

    pet_id_str = str(new_pet.id)

    # Persist pet to Supabase (required for FK constraints on world_chunks, pet_body, etc.)
    try:
        await insert_row("pets", {
            "id": pet_id_str,
            "owner_id": str(new_pet.owner_id),
            "name": new_pet.name,
            "seed_curiosity": new_pet.seed_curiosity,
            "food_balance": new_pet.food_balance,
            "status": new_pet.status,
            "position_x": new_pet.position_x,
            "position_y": new_pet.position_y,
            "position_z": new_pet.position_z,
            "rarity": new_pet.rarity,
            "stats": new_pet.stats,
            "backstory": new_pet.backstory,
            "initial_curiosity": new_pet.initial_curiosity,
            "soul": new_pet.soul,
        })
    except Exception as e:
        logger.error(f"Failed to persist pet {pet_id_str} to database: {e}")

    # Persist creation voxels to Supabase so the creature can manipulate them later
    try:
        # Body voxels → pet_body table
        if new_pet.voxels:
            await save_pet_body(pet_id_str, new_pet.voxels)

        # World voxels → world_chunks table (add alpha channel)
        if new_pet.world_voxels:
            world = WorldService(pet_id_str)
            voxels_with_alpha = [
                {**v, "a": v.get("a", 255)} for v in new_pet.world_voxels
            ]
            await world.place_voxels(voxels_with_alpha)
    except Exception as e:
        logger.warning(f"Failed to persist creation voxels for {pet_id_str}: {e}")

    # Fire the birth burst in the background — the user sees activity
    # via WebSocket as soon as they land on the World page
    asyncio.create_task(_run_birth_burst(pet_id_str, new_pet))

    return new_pet


@router.get("/pets/{pet_id}", response_model=Pet)
async def get_pet(pet_id: UUID):
    """Get pet info."""
    pet = _pets.get(str(pet_id))
    if pet is None:
        # Return placeholder for now
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
            rarity="common",
            stats={"curiosity": 5, "creativity": 5, "social": 5, "focus": 5, "energy": 5, "resilience": 5, "humor": 5},
            backstory="A mysterious pet that appeared from nowhere.",
            initial_curiosity="",
            voxels=[{"x": 0, "y": 0, "z": 0, "r": 255, "g": 255, "b": 255}],
            soul="",
            world_voxels=[],
        )
    return pet


@router.post("/pets/{pet_id}/chat", response_model=ChatResponse)
async def chat(pet_id: UUID, request: ChatRequest):
    """Send a chat message to a pet. The pet's brain processes and responds."""
    pet_id_str = str(pet_id)

    # Look up pet state
    pet = _pets.get(pet_id_str)
    if pet is None:
        # Create a default state for unknown pets (for testing)
        pet = Pet(
            id=pet_id,
            owner_id=uuid4(),
            name="Unknown Pet",
            seed_curiosity="mysteries",
            food_balance=100.0,
            status="idle",
            position_x=0.0,
            position_y=0.0,
            position_z=0.0,
            created_at=datetime.utcnow(),
        )
        _pets[pet_id_str] = pet
        await initialize_food(pet_id_str, 100.0)

    # Acquire chat lock to prevent conflicts with autonomous ticks
    acquired = await _lock.acquire(pet_id_str, mode="chat", timeout=300)
    if not acquired:
        raise HTTPException(
            status_code=409,
            detail="Pet is currently busy (autonomous tick in progress). Try again shortly.",
        )

    try:
        # Build pet state for brain
        pet_state = {
            "name": pet.name,
            "seed_curiosity": pet.seed_curiosity,
            "created_at": pet.created_at.isoformat(),
            "food_balance": await check_food(pet_id_str),
            "position": {
                "x": pet.position_x,
                "y": pet.position_y,
                "z": pet.position_z,
            },
            "memories": [],  # Will be populated from DB later
            "digested_notes": [],
            "agenda": [],
        }

        # Run the brain
        brain = PetBrain(pet_id_str, pet_state)
        result: BrainResult = await brain.think(
            trigger="user_chat",
            context={"user_message": request.message},
        )

        # Update pet's food balance in memory
        remaining_food = await check_food(pet_id_str)
        pet.food_balance = remaining_food

        return ChatResponse(
            pet_id=pet_id_str,
            response=result.response_to_user or "(The pet didn't say anything)",
            actions=result.actions,
            food_consumed=result.food_consumed,
            error=result.error,
        )

    finally:
        # Always release the chat lock
        await _lock.release(pet_id_str, mode="chat")


@router.post("/pets/{pet_id}/feed", response_model=FeedResponse)
async def feed_pet(pet_id: UUID, request: FeedRequest):
    """
    Add food to a pet's balance.
    If the pet was unscheduled (out of food), reschedule it.
    """
    pet_id_str = str(pet_id)

    if request.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive.")

    if request.amount > 1000:
        raise HTTPException(status_code=400, detail="Maximum feed amount is 1000.")

    # Check if pet exists
    pet = _pets.get(pet_id_str)
    if pet is None:
        raise HTTPException(status_code=404, detail="Pet not found.")

    # Get current balance
    current_balance = await check_food(pet_id_str)
    was_empty = current_balance <= 0

    # Add food (using negative deduction)
    await initialize_food(pet_id_str, current_balance + request.amount)
    new_balance = await check_food(pet_id_str)

    # Update pet model
    pet.food_balance = new_balance

    # Reschedule if pet was sleeping (out of food)
    rescheduled = False
    if was_empty and new_balance > 0:
        await _scheduler.schedule_pet(pet_id_str, new_balance)
        rescheduled = True

        # Also generate a new agenda since we have food now
        pet_state = {
            "name": pet.name,
            "seed_curiosity": pet.seed_curiosity,
            "memories": [],
        }
        await generate_daily_agenda(pet_id_str, pet_state)

    return FeedResponse(
        pet_id=pet_id_str,
        food_added=request.amount,
        new_balance=new_balance,
        rescheduled=rescheduled,
    )


@router.get("/pets/{pet_id}/world")
async def get_world(pet_id: UUID):
    """Get world chunks for a pet from the database."""
    world = WorldService(str(pet_id))
    chunks = await world.get_all_chunks()
    return chunks


class SeedWorldRequest(BaseModel):
    chunks: list[dict]


@router.post("/pets/{pet_id}/world/seed")
async def seed_world(pet_id: UUID, request: SeedWorldRequest):
    """
    Seed the base world for a pet.
    Idempotent — chunks that already exist (creation voxels, birth burst)
    are skipped via the unique index on (pet_id, chunk_x, chunk_y, chunk_z).
    """
    world = WorldService(str(pet_id))
    total = await world.seed_world(request.chunks)
    return {"seeded": True, "voxels": total, "chunks": len(request.chunks)}


@router.get("/pets/{pet_id}/body")
async def get_pet_body(pet_id: UUID):
    """Get persisted body data (voxels + position) for a pet."""
    body_data = await load_pet_body(str(pet_id))
    if body_data is None:
        return {"voxels": None, "position": None}
    return {
        "voxels": body_data.get("voxels"),
        "position": body_data.get("position"),
    }


@router.get("/pets/{pet_id}/memories", response_model=list[DigestedNote])
async def get_memories(pet_id: UUID, query: str = ""):
    """Search pet memories."""
    return []


@router.get("/pets/{pet_id}/artifacts", response_model=list[Artifact])
async def get_artifacts(pet_id: UUID):
    """List artifacts created by a pet."""
    return []


@router.get("/pets/{pet_id}/agenda")
async def get_agenda(pet_id: UUID):
    """Get today's agenda for a pet."""
    pet_id_str = str(pet_id)
    agenda = await get_current_agenda(pet_id_str)

    if agenda.get("status") == "no_agenda":
        # Return the Pydantic model format for backward compatibility
        return Agenda(
            id=uuid4(),
            pet_id=pet_id,
            date=date.today(),
            plan={"tasks": []},
            current_task=None,
            food_allocated=0.0,
            food_spent=0.0,
        )

    return Agenda(
        id=uuid4(),
        pet_id=pet_id,
        date=date.today(),
        plan={"tasks": agenda.get("tasks", [])},
        current_task=None,
        food_allocated=agenda.get("food_at_generation", 0.0),
        food_spent=agenda.get("food_at_generation", 0.0) - agenda.get("food_at_last_check", 0.0),
    )


@router.get("/pets/{pet_id}/schedule")
async def get_schedule_status(pet_id: UUID):
    """Get the scheduling status for a pet."""
    pet_id_str = str(pet_id)
    status = await _scheduler.get_status(pet_id_str)
    return status


@router.get("/pets/{pet_id}/neighbors", response_model=list[SocialGraphEntry])
async def get_neighbors(pet_id: UUID):
    """Get nearby pets in the social graph."""
    return []
