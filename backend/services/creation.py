"""Pet creation service with stat rolling, rarity, and species assignment."""

import random
from datetime import datetime
from uuid import UUID, uuid4

from backend.models.pet import Pet
from backend.services.food import initialize_food

# Species organized by rarity tier
SPECIES_BY_RARITY = {
    "common": ["cat", "dog", "bunny", "hamster"],
    "uncommon": ["fox", "owl", "turtle", "frog"],
    "rare": ["wolf", "deer", "seahorse", "hawk"],
    "legendary": ["dragon", "phoenix", "unicorn"],
    "mythic": ["leviathan", "celestial"],
}

# Rarity thresholds based on total stat roll
# Total of 6 stats, each 1-10, so range is 6-60
RARITY_THRESHOLDS = [
    ("mythic", 53, 60),
    ("legendary", 45, 52),
    ("rare", 38, 44),
    ("uncommon", 30, 37),
    ("common", 15, 29),
]

DEFAULT_FOOD_BALANCE = 100.0

BACKSTORY_TEMPLATES = [
    "Born from a spark of curiosity about {curiosity}, {name} the {species} emerged into the world with an insatiable desire to understand everything around them. Their {top_stat} is extraordinary, hinting at a destiny yet to unfold.",
    "{name} hatched under a sky full of questions. This {rarity} {species} was drawn into existence by thoughts of {curiosity}. With remarkable {top_stat}, they seem destined for great discoveries.",
    "In the space between wonder and reality, {name} came to be. A {rarity} {species} whose first thought was of {curiosity}. Their exceptional {top_stat} suggests they will leave their mark on this world.",
    "The void shimmered and {name} appeared — a {rarity} {species} born from pure fascination with {curiosity}. Already their {top_stat} sets them apart from ordinary creatures.",
    "What begins as curiosity becomes life. {name}, a {rarity} {species}, opened their eyes for the first time thinking about {curiosity}. Their {top_stat} burns bright, promising adventures ahead.",
]


def _roll_stats() -> dict:
    """
    Roll 6 stats with a weighted distribution that produces the target rarity percentages.

    Uses a modified approach: each stat is rolled with a distribution skewed
    toward lower values, creating the right spread of totals.
    """
    stats = {}
    stat_names = ["curiosity", "creativity", "social", "focus", "energy", "resilience"]

    for name in stat_names:
        # Weighted roll: take the average of two dice rolls, biased lower
        # This creates a bell curve centered around 4-5
        roll1 = random.randint(1, 10)
        roll2 = random.randint(1, 10)
        roll3 = random.randint(1, 10)
        # Take the middle value of 3 rolls for a nice distribution
        value = sorted([roll1, roll2, roll3])[1]
        stats[name] = value

    return stats


def _determine_rarity(total: int) -> str:
    """Determine rarity based on total stat points."""
    # Use weighted random to ensure proper distribution
    # The stat rolling naturally creates a bell curve, but we enforce
    # the target percentages with explicit probability
    roll = random.random() * 100

    if roll < 1:  # 1% mythic
        return "mythic"
    elif roll < 5:  # 4% legendary
        return "legendary"
    elif roll < 15:  # 10% rare
        return "rare"
    elif roll < 40:  # 25% uncommon
        return "uncommon"
    else:  # 60% common
        return "common"


def _adjust_stats_for_rarity(stats: dict, rarity: str) -> dict:
    """Adjust stats to fall within the expected range for the given rarity."""
    total = sum(stats.values())

    # Target ranges per rarity
    ranges = {
        "common": (15, 29),
        "uncommon": (30, 37),
        "rare": (38, 44),
        "legendary": (45, 52),
        "mythic": (53, 60),
    }

    target_min, target_max = ranges[rarity]
    target_total = random.randint(target_min, target_max)
    diff = target_total - total

    stat_names = list(stats.keys())

    if diff > 0:
        # Need to add points
        for _ in range(diff):
            # Pick a random stat that isn't maxed
            candidates = [s for s in stat_names if stats[s] < 10]
            if not candidates:
                break
            chosen = random.choice(candidates)
            stats[chosen] += 1
    elif diff < 0:
        # Need to remove points
        for _ in range(abs(diff)):
            # Pick a random stat that isn't at minimum
            candidates = [s for s in stat_names if stats[s] > 1]
            if not candidates:
                break
            chosen = random.choice(candidates)
            stats[chosen] -= 1

    return stats


def _generate_backstory(name: str, species: str, rarity: str, stats: dict, curiosity: str) -> str:
    """Generate a backstory from templates using the pet's attributes."""
    # Find the top stat
    top_stat_name = max(stats, key=lambda k: stats[k])

    template = random.choice(BACKSTORY_TEMPLATES)
    return template.format(
        name=name,
        species=species,
        rarity=rarity,
        curiosity=curiosity if curiosity else "the mysteries of the world",
        top_stat=top_stat_name,
    )


async def create_pet(owner_id: str | UUID, name: str, initial_curiosity: str = "") -> Pet:
    """
    Create a new pet with rolled stats, rarity, species, and backstory.

    Args:
        owner_id: The owner's UUID
        name: The pet's name
        initial_curiosity: User's description of what fascinates the pet (max 250 chars)

    Returns a Pet instance ready to start exploring.
    """
    pet_id = uuid4()

    # Ensure owner_id is a UUID
    if isinstance(owner_id, str):
        try:
            owner_uuid = UUID(owner_id)
        except ValueError:
            owner_uuid = uuid4()
    else:
        owner_uuid = owner_id

    # Roll stats
    stats = _roll_stats()

    # Determine rarity (weighted random)
    rarity = _determine_rarity(sum(stats.values()))

    # Adjust stats to match rarity tier
    stats = _adjust_stats_for_rarity(stats, rarity)

    # Pick a random species from the rarity tier
    species = random.choice(SPECIES_BY_RARITY[rarity])

    # Generate backstory
    backstory = _generate_backstory(name, species, rarity, stats, initial_curiosity)

    # Use initial_curiosity as seed_curiosity, or fall back to a random one
    seed_curiosity = initial_curiosity if initial_curiosity else "the unknown"

    # Initialize food balance
    await initialize_food(str(pet_id), DEFAULT_FOOD_BALANCE)

    # Create the pet record
    pet = Pet(
        id=pet_id,
        owner_id=owner_uuid,
        name=name,
        seed_curiosity=seed_curiosity,
        food_balance=DEFAULT_FOOD_BALANCE,
        status="idle",
        position_x=0.0,
        position_y=0.0,
        position_z=0.0,
        created_at=datetime.utcnow(),
        rarity=rarity,
        species=species,
        stats=stats,
        backstory=backstory,
        initial_curiosity=initial_curiosity,
    )

    return pet
