from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from uuid import UUID, uuid4
from datetime import date, datetime

from backend.models.pet import Pet, PetCreate
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


@router.post("/pets", response_model=Pet)
async def create_pet(pet: PetCreate):
    """Create a new pet with random seed curiosity."""
    # Use the creation service (owner_id comes from auth later, stub for now)
    owner_id = str(uuid4())
    new_pet = await create_pet_service(owner_id, pet.name)
    _pets[str(new_pet.id)] = new_pet

    # Schedule the new pet for its first autonomous tick
    pet_id_str = str(new_pet.id)
    await _scheduler.schedule_pet(pet_id_str, new_pet.food_balance)

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


@router.get("/pets/{pet_id}/world", response_model=list[WorldChunk])
async def get_world(pet_id: UUID):
    """Get world chunks for a pet."""
    return []


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
        food_allocated=agenda.get("food_allocated", 0.0),
        food_spent=agenda.get("food_spent", 0.0),
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
