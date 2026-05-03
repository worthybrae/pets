"""Pet creation service with stat rolling, rarity, and AI generation."""

import json
import logging
import os
import random
from datetime import datetime
from uuid import UUID, uuid4

from openai import AsyncOpenAI

from backend.models.pet import Pet
from backend.services.food import initialize_food

logger = logging.getLogger(__name__)

DEFAULT_FOOD_BALANCE = 100.0

STAT_NAMES = ["curiosity", "creativity", "social", "focus", "energy", "resilience", "humor"]

# Rarity ranges for 7 stats (total range 7-70)
RARITY_RANGES = {
    "common": (18, 34),
    "uncommon": (35, 43),
    "rare": (44, 51),
    "legendary": (52, 60),
    "mythic": (61, 70),
}


def _roll_stats() -> dict:
    """Roll 7 stats using median-of-3 for a bell-curve distribution."""
    stats = {}
    for name in STAT_NAMES:
        rolls = [random.randint(1, 10) for _ in range(3)]
        stats[name] = sorted(rolls)[1]
    return stats


def _determine_rarity(total: int) -> str:
    """Determine rarity via weighted random (60/25/10/4/1%)."""
    roll = random.random() * 100
    if roll < 1:
        return "mythic"
    elif roll < 5:
        return "legendary"
    elif roll < 15:
        return "rare"
    elif roll < 40:
        return "uncommon"
    else:
        return "common"


def _adjust_stats_for_rarity(stats: dict, rarity: str) -> dict:
    """Adjust stats to fall within the target range for the rarity tier."""
    total = sum(stats.values())
    target_min, target_max = RARITY_RANGES[rarity]
    target_total = random.randint(target_min, target_max)
    diff = target_total - total

    stat_names = list(stats.keys())

    if diff > 0:
        for _ in range(diff):
            candidates = [s for s in stat_names if stats[s] < 10]
            if not candidates:
                break
            stats[random.choice(candidates)] += 1
    elif diff < 0:
        for _ in range(abs(diff)):
            candidates = [s for s in stat_names if stats[s] > 1]
            if not candidates:
                break
            stats[random.choice(candidates)] -= 1

    return stats


CREATION_SCHEMA = {
    "name": "pet_creation",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "pet_voxels": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer"},
                        "y": {"type": "integer"},
                        "z": {"type": "integer"},
                        "r": {"type": "integer"},
                        "g": {"type": "integer"},
                        "b": {"type": "integer"},
                    },
                    "required": ["x", "y", "z", "r", "g", "b"],
                    "additionalProperties": False,
                },
            },
            "world_voxels": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer"},
                        "y": {"type": "integer"},
                        "z": {"type": "integer"},
                        "r": {"type": "integer"},
                        "g": {"type": "integer"},
                        "b": {"type": "integer"},
                    },
                    "required": ["x", "y", "z", "r", "g", "b"],
                    "additionalProperties": False,
                },
            },
            "soul": {"type": "string"},
            "backstory": {"type": "string"},
        },
        "required": ["pet_voxels", "world_voxels", "soul", "backstory"],
        "additionalProperties": False,
    },
}

SYSTEM_PROMPT = """You are a creature designer for a voxel world. You create unique 3D pixel-art creatures and environments using voxels (1x1x1 cubes on an integer grid).

Design principles:
- Build creatures layer-by-layer. y=0 is the ground, build upward.
- Use bilateral symmetry where appropriate (creatures look better symmetric).
- Use 3-5 main colors per creature, not random noise. Colors should feel cohesive.
- Creatures should be recognizable from multiple angles, not flat/2D. They should have depth.
- The creature should be centered around origin (0,0,0).
- World landmarks should sit on the y=0 ground plane, offset from the pet (e.g. x=10..25).

Example of a simple 24-voxel bird (to show format):
[{"x":0,"y":0,"z":0,"r":100,"g":180,"b":255},{"x":1,"y":0,"z":0,"r":100,"g":180,"b":255},{"x":0,"y":1,"z":0,"r":100,"g":180,"b":255},{"x":1,"y":1,"z":0,"r":100,"g":180,"b":255},{"x":0,"y":0,"z":1,"r":100,"g":180,"b":255},{"x":1,"y":0,"z":1,"r":100,"g":180,"b":255},{"x":0,"y":1,"z":1,"r":100,"g":180,"b":255},{"x":1,"y":1,"z":1,"r":100,"g":180,"b":255},{"x":-1,"y":1,"z":0,"r":80,"g":160,"b":240},{"x":2,"y":1,"z":0,"r":80,"g":160,"b":240},{"x":-1,"y":1,"z":1,"r":80,"g":160,"b":240},{"x":2,"y":1,"z":1,"r":80,"g":160,"b":240},{"x":0,"y":2,"z":0,"r":120,"g":200,"b":255},{"x":1,"y":2,"z":0,"r":120,"g":200,"b":255},{"x":0,"y":2,"z":1,"r":120,"g":200,"b":255},{"x":1,"y":2,"z":1,"r":120,"g":200,"b":255},{"x":0,"y":3,"z":0,"r":255,"g":200,"b":50},{"x":1,"y":3,"z":0,"r":255,"g":200,"b":50},{"x":0,"y":3,"z":1,"r":255,"g":200,"b":50},{"x":1,"y":3,"z":1,"r":255,"g":200,"b":50},{"x":0,"y":2,"z":-1,"r":255,"g":180,"b":0},{"x":1,"y":2,"z":-1,"r":255,"g":180,"b":0},{"x":0,"y":-1,"z":0,"r":200,"g":150,"b":50},{"x":1,"y":-1,"z":0,"r":200,"g":150,"b":50}]

This is a small example. Real creatures should be 150-400 voxels."""


def _build_user_prompt(name: str, curiosity: str, stats: dict, rarity: str) -> str:
    """Build the user prompt for the creation LLM call."""
    stats_block = "\n".join(f"  {k.capitalize()}: {v}/10" for k, v in stats.items())

    return f"""Create a pet and its world based on these attributes:

Name: {name}
Curiosity: {curiosity or "the mysteries of the world"}
Rarity: {rarity}
Stats:
{stats_block}

Generate:

1. pet_voxels (150-400 voxels): A unique creature that embodies these stats. High energy = dynamic pose. High creativity = unusual features. High humor = playful expression. The rarity should influence elaborateness — mythic creatures are more complex than common ones.

2. world_voxels (200-500 voxels): A single landmark or feature that relates to the pet's curiosity "{curiosity or "the mysteries of the world"}". Place it offset from the origin (around x=10..25) so it doesn't overlap the pet. This is the first thing in an otherwise empty void.

3. soul (~600 words): The pet's inner identity document with these sections:
   - Temperament: emotional baseline
   - Speech style: how they talk to their owner
   - Quirks: 2-3 specific behavioral habits
   - Fears: what makes them anxious or avoidant
   - Goals: what they want to achieve long-term
   - Worldview: how they interpret their existence
   - Initial questions: 3-5 things they're actively wondering about right now

   All sections should be shaped by the stats. Make the personality feel coherent and alive.

4. backstory (2-3 sentences): Third-person origin story referencing their name, curiosity, and strongest stat."""


def _validate_creation_output(data: dict) -> dict:
    """Validate and clamp the LLM output to safe ranges."""
    # Clamp pet voxels
    pet_voxels = data.get("pet_voxels", [])
    if len(pet_voxels) > 400:
        pet_voxels = pet_voxels[:400]
    clamped_pet = []
    for v in pet_voxels:
        clamped_pet.append({
            "x": max(-10, min(10, v.get("x", 0))),
            "y": max(-10, min(10, v.get("y", 0))),
            "z": max(-10, min(10, v.get("z", 0))),
            "r": max(0, min(255, v.get("r", 255))),
            "g": max(0, min(255, v.get("g", 255))),
            "b": max(0, min(255, v.get("b", 255))),
        })

    # Clamp world voxels
    world_voxels = data.get("world_voxels", [])
    if len(world_voxels) > 500:
        world_voxels = world_voxels[:500]
    clamped_world = []
    for v in world_voxels:
        clamped_world.append({
            "x": max(-16, min(16, v.get("x", 0))),
            "y": max(-16, min(16, v.get("y", 0))),
            "z": max(-16, min(16, v.get("z", 0))),
            "r": max(0, min(255, v.get("r", 255))),
            "g": max(0, min(255, v.get("g", 255))),
            "b": max(0, min(255, v.get("b", 255))),
        })

    # Validate text fields
    soul = data.get("soul", "")
    backstory = data.get("backstory", "")

    if len(pet_voxels) < 150:
        logger.warning(f"LLM returned only {len(pet_voxels)} pet voxels (expected 150-400)")
    if len(world_voxels) < 200:
        logger.warning(f"LLM returned only {len(world_voxels)} world voxels (expected 200-500)")

    return {
        "pet_voxels": clamped_pet,
        "world_voxels": clamped_world,
        "soul": soul,
        "backstory": backstory,
    }


def _fallback_creation(name: str, stats: dict, curiosity: str) -> dict:
    """Generate fallback data if the LLM call fails."""
    top_stat = max(stats, key=lambda k: stats[k])
    return {
        "pet_voxels": [{"x": 0, "y": 0, "z": 0, "r": 255, "g": 255, "b": 255}],
        "world_voxels": [],
        "soul": (
            f"Temperament: Curious and eager.\n"
            f"Speech style: Simple and direct.\n"
            f"Quirks: Likes to explore. Pauses to think.\n"
            f"Fears: The vastness of the void.\n"
            f"Goals: To understand the world.\n"
            f"Worldview: Everything is worth investigating.\n"
            f"Initial questions: What is this place? Why am I here? What is beyond the void?"
        ),
        "backstory": (
            f"{name} emerged from the void with a deep fascination for "
            f"{curiosity or 'the unknown'}. Their remarkable {top_stat} hints at "
            f"a destiny yet to unfold."
        ),
    }


async def _generate_pet_with_llm(
    name: str, curiosity: str, stats: dict, rarity: str
) -> dict:
    """Call OpenAI structured output to generate pet voxels, world, soul, and backstory."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not set, using fallback creation")
        return _fallback_creation(name, stats, curiosity)

    client = AsyncOpenAI(api_key=api_key)
    user_prompt = _build_user_prompt(name, curiosity, stats, rarity)

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": CREATION_SCHEMA,
            },
            timeout=15.0,
        )

        raw = response.choices[0].message.content
        data = json.loads(raw)
        return _validate_creation_output(data)

    except Exception as e:
        logger.error(f"LLM creation failed: {e}")
        return _fallback_creation(name, stats, curiosity)


async def create_pet(owner_id: str | UUID, name: str, initial_curiosity: str = "") -> Pet:
    """
    Create a new pet with rolled stats, rarity, and AI-generated content.

    1. Roll 7 stats (median-of-3)
    2. Determine rarity (weighted random)
    3. Adjust stats to fit rarity tier
    4. Call OpenAI to generate voxels, soul, world, and backstory
    5. Return the complete Pet
    """
    pet_id = uuid4()

    if isinstance(owner_id, str):
        try:
            owner_uuid = UUID(owner_id)
        except ValueError:
            owner_uuid = uuid4()
    else:
        owner_uuid = owner_id

    # Roll stats and determine rarity
    stats = _roll_stats()
    rarity = _determine_rarity(sum(stats.values()))
    stats = _adjust_stats_for_rarity(stats, rarity)

    # Generate creative content via LLM
    generated = await _generate_pet_with_llm(name, initial_curiosity, stats, rarity)

    seed_curiosity = initial_curiosity if initial_curiosity else "the unknown"
    await initialize_food(str(pet_id), DEFAULT_FOOD_BALANCE)

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
        stats=stats,
        backstory=generated["backstory"],
        initial_curiosity=initial_curiosity,
        voxels=generated["pet_voxels"],
        soul=generated["soul"],
        world_voxels=generated["world_voxels"],
    )

    return pet
