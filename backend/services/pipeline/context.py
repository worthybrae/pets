"""Loads shared context for pipeline stages."""

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.services.memory import MemoryService
from backend.services.world_map import WorldMapService
from backend.services.mood_board import MoodBoardService
from backend.services.agenda import get_current_agenda

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """All shared state available to pipeline stages."""

    pet_id: str
    pet_name: str
    pet_soul: str
    pet_stats: dict[str, Any]
    food_balance: float
    position: dict[str, float]

    # World awareness
    regions: list[dict[str, Any]] = field(default_factory=list)
    recent_journal: list[dict[str, Any]] = field(default_factory=list)
    last_review: dict[str, Any] | None = None

    # Mood board
    mood_board_summary: str = ""

    # Memory
    knowledge: list[dict[str, Any]] = field(default_factory=list)
    digested_notes: list[dict[str, Any]] = field(default_factory=list)

    # Agenda
    agenda_tasks: list[dict[str, Any]] = field(default_factory=list)
    current_task: dict[str, Any] | None = None


async def load_pipeline_context(pet_id: str, pet_state: dict[str, Any]) -> PipelineContext:
    """Load all context needed by pipeline stages from DB."""

    ctx = PipelineContext(
        pet_id=pet_id,
        pet_name=pet_state.get("name", "Pet"),
        pet_soul=pet_state.get("soul", ""),
        pet_stats=pet_state.get("stats", {}),
        food_balance=pet_state.get("food_balance", 0.0),
        position=pet_state.get("position", {"x": 0, "y": 0, "z": 0}),
    )

    # Load world map
    try:
        world_map = WorldMapService(pet_id)
        ctx.regions = await world_map.get_all_regions()
        ctx.recent_journal = await world_map.get_recent_journal(limit=5)
        ctx.last_review = await world_map.get_last_review()
    except Exception as e:
        logger.warning(f"Failed to load world map for {pet_id}: {e}")

    # Load mood board
    try:
        mood = MoodBoardService(pet_id)
        ctx.mood_board_summary = await mood.get_mood_board_summary()
    except Exception as e:
        logger.warning(f"Failed to load mood board for {pet_id}: {e}")

    # Load memory tiers
    try:
        memory = MemoryService(pet_id)
        ctx.knowledge = await memory.get_all_knowledge()
        ctx.digested_notes = await memory.get_recent_digests(limit=10)
    except Exception as e:
        logger.warning(f"Failed to load memory for {pet_id}: {e}")

    # Load agenda
    try:
        agenda_data = await get_current_agenda(pet_id)
        if agenda_data.get("status") != "no_agenda":
            ctx.agenda_tasks = agenda_data.get("tasks", [])
            ctx.current_task = agenda_data.get("current_task")
    except Exception as e:
        logger.warning(f"Failed to load agenda for {pet_id}: {e}")

    return ctx
