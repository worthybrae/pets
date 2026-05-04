"""Pet creation service with stat rolling, rarity, and AI generation."""

import json
import logging
import os
import random
from datetime import datetime
from uuid import UUID, uuid4

from openai import AsyncOpenAI

from backend.models.pet import Pet
from backend.services.food import initialize_food, calculate_llm_cost

logger = logging.getLogger(__name__)

DEFAULT_FOOD_BALANCE = 1.0

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
            "name": {"type": "string"},
            "curiosity": {"type": "string"},
            "soul": {"type": "string"},
            "backstory": {"type": "string"},
        },
        "required": ["name", "curiosity", "pet_voxels", "world_voxels", "soul", "backstory"],
        "additionalProperties": False,
    },
}

SYSTEM_PROMPT = """You are a voxel creature sculptor. You output precise 3D voxel coordinates to build creatures on an integer grid. Each voxel is a 1x1x1 cube at (x, y, z) with an RGB color.

COORDINATE SYSTEM: x = left/right, y = up (y=0 is ground), z = front/back. Center creature at x=0, z=0.

BUILDING TECHNIQUE — follow this exact process:
1. SKELETON: Plan the creature's proportions first. A typical small creature is about 7 wide, 10 tall, 5 deep.
2. FEET (y=0-1): 2x1x2 blocks for each foot, spaced apart
3. LEGS (y=1-3): 2x3x2 columns connecting feet to body
4. BODY (y=3-6): The largest section, 5-7 wide, 3-4 tall, 3-5 deep. Solid filled rectangle with surface details.
5. HEAD (y=7-10): Slightly smaller than body. 4-5 wide, 3-4 tall, 3-4 deep.
6. EYES: Place on the FRONT face (lowest z of head), using the highlight color. Always 2 eyes, symmetric.
7. EARS/HORNS (y=10+): Small protrusions on top of head
8. TAIL: Extends behind body at mid-height
9. DETAILS: Add features AFTER the base shape is solid — wings, markings, spines, etc.

SYMMETRY: For every voxel at (x, y, z), also place one at (-x, y, z). This is critical.

SOLIDITY: Body and head should be FILLED, not hollow. A 5x3x4 body = 60 voxels minimum. Don't skip interior voxels — they provide structural completeness.

COLORING:
- Body bulk: primary color with +/-15 RGB variation per voxel for natural shading
- Top surfaces: slightly brighter. Bottom: slightly darker.
- Belly/underside: secondary color
- Markings, fins, wings: accent color
- Eyes: highlight color (must contrast strongly with head)
- All RGB values must be >= 60

EXAMPLE — A simple fox (showing the technique):
Feet at y=0: four 1x1x1 blocks at corners (-2,0,0), (2,0,0), (-2,0,3), (2,0,3)
Legs y=1-2: four columns above feet
Body y=3-5: filled block from x=-2..2, z=0..3 (5 wide, 3 tall, 4 deep = 60 voxels)
Head y=6-8: filled block from x=-2..2, z=-1..1 (5 wide, 3 tall, 3 deep = 45 voxels)
Eyes at y=7, z=-2 (front face): at x=-1 and x=1, bright contrasting color
Ears at y=9: at x=-1 and x=1, pointed up
Tail: extends z=4..7 at y=4, narrow (1-2 wide)

That's ~150 voxels for a basic creature. Add more detail for higher rarity.

Rarity determines complexity:
- Common: simple animal, ~150-200 voxels, clean shapes
- Uncommon: animal with one special feature, ~200-250 voxels
- Rare: animal with fantastical elements (crystal tail, glowing markings), ~250-300 voxels
- Legendary: hybrid creature (dragon-fox, winged serpent), ~300-350 voxels
- Mythic: majestic beast (phoenix, celestial stag), ~350-400 voxels"""


# Palettes derived from frontend EggScene.tsx COLOR_MAP.
# primary = core (the bright glow the user sees)
# secondary = base (darker surface color)
# accent = spec (specular highlights)
# highlight = contrasting eye color
# Values clamped to >=60 per channel to match SYSTEM_PROMPT constraint.
EGG_COLOR_PALETTES = {
    "Stone": {
        "desc": "warm earth tones — sandstone, clay, terracotta",
        "primary": "rgb(191, 153, 102)",      # core [0.75, 0.6, 0.4]
        "secondary": "rgb(97, 89, 82)",       # base [0.38, 0.35, 0.32]
        "accent": "rgb(255, 242, 217)",       # spec [1.0, 0.95, 0.85]
        "highlight": "rgb(240, 210, 120)",
    },
    "Moss": {
        "desc": "deep forest greens with bright leaf accents",
        "primary": "rgb(60, 191, 60)",        # core [0.2, 0.75, 0.15] clamped
        "secondary": "rgb(60, 89, 60)",       # base [0.15, 0.35, 0.12] clamped
        "accent": "rgb(153, 255, 128)",       # spec [0.6, 1.0, 0.5]
        "highlight": "rgb(220, 240, 80)",
    },
    "Amber": {
        "desc": "warm golden-orange, honey, and sunset tones",
        "primary": "rgb(255, 166, 60)",       # core [1.0, 0.65, 0.05] clamped
        "secondary": "rgb(153, 89, 60)",      # base [0.6, 0.35, 0.08] clamped
        "accent": "rgb(255, 242, 128)",       # spec [1.0, 0.95, 0.5]
        "highlight": "rgb(255, 100, 60)",
    },
    "Cobalt": {
        "desc": "deep ocean blues with icy cyan accents",
        "primary": "rgb(60, 102, 255)",       # core [0.1, 0.4, 1.0] clamped
        "secondary": "rgb(60, 60, 140)",      # base [0.1, 0.22, 0.55] clamped
        "accent": "rgb(128, 191, 255)",       # spec [0.5, 0.75, 1.0]
        "highlight": "rgb(220, 240, 255)",
    },
    "Crimson": {
        "desc": "rich reds, burgundy, and warm scarlet",
        "primary": "rgb(255, 60, 60)",        # core [1.0, 0.12, 0.05] clamped
        "secondary": "rgb(140, 60, 60)",      # base [0.55, 0.08, 0.08] clamped
        "accent": "rgb(255, 128, 102)",       # spec [1.0, 0.5, 0.4]
        "highlight": "rgb(255, 220, 100)",
    },
    "Violet": {
        "desc": "deep purples, amethyst, and lavender",
        "primary": "rgb(166, 60, 242)",       # core [0.65, 0.1, 0.95] clamped
        "secondary": "rgb(89, 60, 140)",      # base [0.35, 0.12, 0.55] clamped
        "accent": "rgb(204, 128, 255)",       # spec [0.8, 0.5, 1.0]
        "highlight": "rgb(100, 240, 255)",
    },
    "Obsidian": {
        "desc": "dark charcoal with electric blue-purple accents",
        "primary": "rgb(60, 60, 128)",        # core [0.2, 0.15, 0.5] clamped
        "secondary": "rgb(70, 65, 90)",       # base [0.06, 0.05, 0.1] brightened
        "accent": "rgb(115, 102, 179)",       # spec [0.45, 0.4, 0.7]
        "highlight": "rgb(100, 140, 255)",
    },
    "Iridescent": {
        "desc": "shifting rainbow — pink, teal, and purple",
        "primary": "rgb(204, 77, 230)",       # core [0.8, 0.3, 0.9]
        "secondary": "rgb(102, 77, 128)",     # base [0.4, 0.3, 0.5]
        "accent": "rgb(255, 204, 255)",       # spec [1.0, 0.8, 1.0]
        "highlight": "rgb(80, 230, 220)",
    },
}


def _build_user_prompt(stats: dict, rarity: str, egg_color: str | None = None) -> str:
    """Build the user prompt for the creation LLM call."""
    stats_block = "\n".join(f"  {k.capitalize()}: {v}/10" for k, v in stats.items())

    palette = EGG_COLOR_PALETTES.get(egg_color or "Stone", EGG_COLOR_PALETTES["Stone"])
    color_block = f"""Color Palette (from egg): {palette['desc']}
  Primary body:  {palette['primary']}
  Secondary:     {palette['secondary']}
  Accent/detail: {palette['accent']}
  Highlight/eye: {palette['highlight']}
  Use these as your BASE colors. Vary brightness per-voxel for shading (lighter on top, darker underneath). Eyes should use the highlight color. You may add 1-2 extra accent colors that complement the palette."""

    return f"""Create a pet and its world based on these attributes:

Rarity: {rarity}
Stats:
{stats_block}

{color_block}

Generate:

1. name: A unique, memorable name. Short (1-2 words), evocative.

2. curiosity: A specific fascination that drives this creature (e.g. "the sound that colors make"). One short phrase.

3. pet_voxels (200-400 voxels): A creature based on a REAL animal (fox, owl, frog, cat, seahorse, beetle, etc.) with fantastical elements. Build it layer-by-layer starting at y=0 (feet). Use bilateral symmetry. Give it clearly distinct body parts: head, torso, limbs, tail. Eyes should be a contrasting bright color. USE THE COLOR PALETTE ABOVE — the primary color for the body, secondary for belly/underbody, accent for markings/features, highlight for eyes. Vary RGB values slightly between voxels (+/- 15) for natural shading. All RGB values must be >= 60.

4. world_voxels (200-500 voxels): A landmark related to the pet's curiosity. Place it at x=10..25, y=0 (ground level). Use colors that complement the pet's palette.

5. soul (~600 words): The pet's inner identity:
   - Temperament, Speech style, Quirks (2-3), Fears, Goals, Worldview, Initial questions (3-5)
   All shaped by stats.

6. backstory (2-3 sentences): Third-person origin story."""


def _validate_creation_output(data: dict) -> dict:
    """Validate and clamp the LLM output to safe ranges."""
    # Clamp pet voxels
    pet_voxels = data.get("pet_voxels", [])
    if len(pet_voxels) > 400:
        pet_voxels = pet_voxels[:400]
    clamped_pet = []
    for v in pet_voxels:
        r = max(0, min(255, v.get("r", 200)))
        g = max(0, min(255, v.get("g", 200)))
        b = max(0, min(255, v.get("b", 200)))
        # Ensure voxels are clearly visible — boost if too dark
        if r + g + b < 180:
            boost = max(1, 180 / max(r + g + b, 1))
            r = min(255, int(max(r * boost, 100)))
            g = min(255, int(max(g * boost, 100)))
            b = min(255, int(max(b * boost, 100)))
        clamped_pet.append({
            "x": max(-10, min(10, v.get("x", 0))),
            "y": max(-10, min(10, v.get("y", 0))),
            "z": max(-10, min(10, v.get("z", 0))),
            "r": r, "g": g, "b": b,
        })

    # Clamp world voxels
    world_voxels = data.get("world_voxels", [])
    if len(world_voxels) > 500:
        world_voxels = world_voxels[:500]
    clamped_world = []
    for v in world_voxels:
        r = max(0, min(255, v.get("r", 200)))
        g = max(0, min(255, v.get("g", 200)))
        b = max(0, min(255, v.get("b", 200)))
        if r + g + b < 180:
            boost = max(1, 180 / max(r + g + b, 1))
            r = min(255, int(max(r * boost, 100)))
            g = min(255, int(max(g * boost, 100)))
            b = min(255, int(max(b * boost, 100)))
        clamped_world.append({
            "x": max(-16, min(16, v.get("x", 0))),
            "y": max(-16, min(16, v.get("y", 0))),
            "z": max(-16, min(16, v.get("z", 0))),
            "r": r, "g": g, "b": b,
        })

    # Validate text fields
    name = data.get("name", "").strip()[:30]
    curiosity = data.get("curiosity", "").strip()[:250]
    soul = data.get("soul", "")
    backstory = data.get("backstory", "")

    if len(pet_voxels) < 150:
        logger.warning(f"LLM returned only {len(pet_voxels)} pet voxels (expected 150-400)")
    if len(world_voxels) < 200:
        logger.warning(f"LLM returned only {len(world_voxels)} world voxels (expected 200-500)")

    return {
        "name": name or "Unnamed",
        "curiosity": curiosity or "the unknown",
        "pet_voxels": clamped_pet,
        "world_voxels": clamped_world,
        "soul": soul,
        "backstory": backstory,
    }


_FALLBACK_NAMES = [
    "Glim", "Nyx", "Pebble", "Wisp", "Ember", "Chirp", "Mote", "Bramble",
    "Flicker", "Twig", "Haze", "Rumble", "Drift", "Pip", "Sprout", "Quill",
]


def _fallback_creation(stats: dict) -> dict:
    """Generate fallback data if the LLM call fails."""
    name = random.choice(_FALLBACK_NAMES)
    top_stat = max(stats, key=lambda k: stats[k])
    return {
        "name": name,
        "curiosity": "the unknown",
        "pet_voxels": [
            # Simple creature shape (~30 voxels) so fallback is visible
            # Body (2x3x2 core)
            {"x": 0, "y": 0, "z": 0, "r": 180, "g": 120, "b": 255},
            {"x": 1, "y": 0, "z": 0, "r": 180, "g": 120, "b": 255},
            {"x": 0, "y": 0, "z": 1, "r": 180, "g": 120, "b": 255},
            {"x": 1, "y": 0, "z": 1, "r": 180, "g": 120, "b": 255},
            {"x": 0, "y": 1, "z": 0, "r": 200, "g": 140, "b": 255},
            {"x": 1, "y": 1, "z": 0, "r": 200, "g": 140, "b": 255},
            {"x": 0, "y": 1, "z": 1, "r": 200, "g": 140, "b": 255},
            {"x": 1, "y": 1, "z": 1, "r": 200, "g": 140, "b": 255},
            {"x": 0, "y": 2, "z": 0, "r": 220, "g": 160, "b": 255},
            {"x": 1, "y": 2, "z": 0, "r": 220, "g": 160, "b": 255},
            {"x": 0, "y": 2, "z": 1, "r": 220, "g": 160, "b": 255},
            {"x": 1, "y": 2, "z": 1, "r": 220, "g": 160, "b": 255},
            # Head (2x2x2)
            {"x": 0, "y": 3, "z": 0, "r": 240, "g": 200, "b": 255},
            {"x": 1, "y": 3, "z": 0, "r": 240, "g": 200, "b": 255},
            {"x": 0, "y": 3, "z": 1, "r": 240, "g": 200, "b": 255},
            {"x": 1, "y": 3, "z": 1, "r": 240, "g": 200, "b": 255},
            {"x": 0, "y": 4, "z": 0, "r": 240, "g": 200, "b": 255},
            {"x": 1, "y": 4, "z": 0, "r": 240, "g": 200, "b": 255},
            {"x": 0, "y": 4, "z": 1, "r": 240, "g": 200, "b": 255},
            {"x": 1, "y": 4, "z": 1, "r": 240, "g": 200, "b": 255},
            # Eyes
            {"x": 0, "y": 4, "z": -1, "r": 255, "g": 255, "b": 255},
            {"x": 1, "y": 4, "z": -1, "r": 255, "g": 255, "b": 255},
            # Ears
            {"x": 0, "y": 5, "z": 0, "r": 200, "g": 140, "b": 255},
            {"x": 1, "y": 5, "z": 1, "r": 200, "g": 140, "b": 255},
            # Arms
            {"x": -1, "y": 2, "z": 0, "r": 180, "g": 120, "b": 255},
            {"x": 2, "y": 2, "z": 0, "r": 180, "g": 120, "b": 255},
            # Feet
            {"x": 0, "y": -1, "z": 0, "r": 150, "g": 100, "b": 220},
            {"x": 1, "y": -1, "z": 0, "r": 150, "g": 100, "b": 220},
        ],
        "world_voxels": [
            # Small platform
            {"x": 12, "y": 0, "z": 0, "r": 80, "g": 80, "b": 80},
            {"x": 13, "y": 0, "z": 0, "r": 80, "g": 80, "b": 80},
            {"x": 14, "y": 0, "z": 0, "r": 80, "g": 80, "b": 80},
            {"x": 12, "y": 0, "z": 1, "r": 80, "g": 80, "b": 80},
            {"x": 13, "y": 0, "z": 1, "r": 80, "g": 80, "b": 80},
            {"x": 14, "y": 0, "z": 1, "r": 80, "g": 80, "b": 80},
            {"x": 13, "y": 1, "z": 0, "r": 120, "g": 200, "b": 120},
            {"x": 13, "y": 2, "z": 0, "r": 120, "g": 200, "b": 120},
            {"x": 13, "y": 3, "z": 0, "r": 100, "g": 220, "b": 100},
        ],
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
            f"{name} emerged from the void with wonder in its eyes. "
            f"Its remarkable {top_stat} hints at a destiny yet to unfold."
        ),
    }


async def _generate_pet_with_llm(stats: dict, rarity: str, egg_color: str | None = None) -> dict:
    """Call OpenAI structured output to generate pet name, curiosity, voxels, world, soul, and backstory."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not set, using fallback creation")
        return _fallback_creation(stats)

    client = AsyncOpenAI(api_key=api_key)
    user_prompt = _build_user_prompt(stats, rarity, egg_color)

    try:
        response = await client.chat.completions.create(
            model="gpt-5.4-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": CREATION_SCHEMA,
            },
            timeout=120.0,
        )

        # Track creation LLM cost
        usage = response.usage
        creation_cost = 0.0
        if usage:
            creation_cost = calculate_llm_cost("gpt-5.4-mini", usage.prompt_tokens, usage.completion_tokens)
            logger.info(
                f"Creation LLM cost: ${creation_cost:.6f} "
                f"({usage.prompt_tokens} in / {usage.completion_tokens} out)"
            )

        raw = response.choices[0].message.content
        data = json.loads(raw)
        # Debug: log color stats before validation
        pet_voxels = data.get("pet_voxels", [])
        if pet_voxels:
            sample = pet_voxels[:3]
            avg_r = sum(v.get("r", 0) for v in pet_voxels) / len(pet_voxels)
            avg_g = sum(v.get("g", 0) for v in pet_voxels) / len(pet_voxels)
            avg_b = sum(v.get("b", 0) for v in pet_voxels) / len(pet_voxels)
            logger.info(f"LLM raw colors — avg rgb({avg_r:.0f},{avg_g:.0f},{avg_b:.0f}), "
                        f"samples: {[(v.get('r'),v.get('g'),v.get('b')) for v in sample]}, "
                        f"count: {len(pet_voxels)}")
        result = _validate_creation_output(data)
        result["_creation_cost"] = creation_cost
        return result

    except Exception as e:
        logger.error(f"LLM creation failed: {e}")
        return _fallback_creation(stats)


async def create_pet(
    owner_id: str | UUID,
    stats: dict | None = None,
    rarity: str | None = None,
    egg_color: str | None = None,
) -> Pet:
    """
    Create a new pet with AI-generated content.

    Stats and rarity can be provided (pre-rolled on the client) or will be
    rolled server-side if not supplied. The LLM generates everything else:
    name, curiosity, voxels, soul, world, and backstory.
    """
    pet_id = uuid4()

    if isinstance(owner_id, str):
        try:
            owner_uuid = UUID(owner_id)
        except ValueError:
            owner_uuid = uuid4()
    else:
        owner_uuid = owner_id

    # Use pre-rolled stats or roll fresh
    if stats and rarity and rarity in RARITY_RANGES:
        # Validate client-provided stats
        for name in STAT_NAMES:
            if name not in stats:
                stats[name] = 5
            stats[name] = max(1, min(10, int(stats[name])))
    else:
        stats = _roll_stats()
        rarity = _determine_rarity(sum(stats.values()))
        stats = _adjust_stats_for_rarity(stats, rarity)

    # Generate all creative content via LLM
    generated = await _generate_pet_with_llm(stats, rarity, egg_color)

    # Deduct creation LLM cost from initial balance
    creation_cost = generated.pop("_creation_cost", 0.0)
    initial_balance = DEFAULT_FOOD_BALANCE - creation_cost
    await initialize_food(str(pet_id), initial_balance)

    pet = Pet(
        id=pet_id,
        owner_id=owner_uuid,
        name=generated["name"],
        seed_curiosity=generated["curiosity"],
        food_balance=initial_balance,
        status="idle",
        position_x=0.0,
        position_y=0.0,
        position_z=0.0,
        created_at=datetime.utcnow(),
        rarity=rarity,
        stats=stats,
        backstory=generated["backstory"],
        initial_curiosity=generated["curiosity"],
        voxels=generated["pet_voxels"],
        soul=generated["soul"],
        world_voxels=generated["world_voxels"],
    )

    return pet
