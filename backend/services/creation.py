"""Pet creation service with random seed curiosity."""

import random
from datetime import datetime
from uuid import UUID, uuid4

from backend.models.pet import Pet
from backend.services.food import initialize_food

SEED_CURIOSITIES = [
    "bioluminescence",
    "ancient architecture",
    "whale songs",
    "moss",
    "fractals",
    "underground rivers",
    "star formation",
    "origami",
    "mycelium networks",
    "aurora borealis",
    "tidal pools",
    "cave crystals",
    "wind patterns",
    "volcanic glass",
    "deep sea creatures",
    "bird migration",
    "sand dunes",
    "lightning",
    "coral reefs",
    "fog",
    "geysers",
    "amber preservation",
    "magnetic fields",
    "ice formations",
    "silk weaving",
    "bonsai",
    "tide patterns",
    "cloud types",
    "phosphorescence",
    "petrified wood",
]

DEFAULT_FOOD_BALANCE = 100.0


async def create_pet(owner_id: str | UUID, name: str) -> Pet:
    """
    Create a new pet with random seed curiosity, single white voxel, empty world.

    Returns a Pet instance ready to start exploring.
    """
    pet_id = uuid4()
    seed = random.choice(SEED_CURIOSITIES)

    # Ensure owner_id is a UUID
    if isinstance(owner_id, str):
        try:
            owner_uuid = UUID(owner_id)
        except ValueError:
            owner_uuid = uuid4()
    else:
        owner_uuid = owner_id

    # Initialize food balance
    await initialize_food(str(pet_id), DEFAULT_FOOD_BALANCE)

    # Create the pet record
    pet = Pet(
        id=pet_id,
        owner_id=owner_uuid,
        name=name,
        seed_curiosity=seed,
        food_balance=DEFAULT_FOOD_BALANCE,
        status="idle",
        position_x=0.0,
        position_y=0.0,
        position_z=0.0,
        created_at=datetime.utcnow(),
    )

    # Note: World chunk creation (single white voxel at 0,0,0) and
    # initial agenda creation will happen at the DB layer once connected.
    # For now the pet starts with defaults.

    return pet
