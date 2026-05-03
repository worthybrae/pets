"""Agenda generation and management for pets."""

import json
import logging
import os
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from openai import AsyncOpenAI

from backend.services.food import check_food

logger = logging.getLogger(__name__)

# In-memory agenda store (will be replaced with DB later)
_agendas: dict[str, dict[str, Any]] = {}


def _agenda_key(pet_id: str, day: date | None = None) -> str:
    """Build key for a pet's agenda on a given date."""
    if day is None:
        day = date.today()
    return f"{pet_id}:{day.isoformat()}"


async def generate_daily_agenda(pet_id: str, pet_state: dict[str, Any] | None = None) -> list[dict]:
    """
    Called once per day (or when food is refilled).
    Uses the brain to create today's plan based on:
    - Pet's knowledge base and interests
    - Remaining food budget
    - What it did yesterday

    Returns a list of planned activities with estimated food costs.
    """
    food_balance = await check_food(pet_id)
    if food_balance <= 0:
        logger.info(f"Pet {pet_id} has no food, skipping agenda generation.")
        return []

    # Gather context for agenda planning
    name = "Unknown Pet"
    seed_curiosity = "the unknown"
    memories: list[str] = []

    if pet_state:
        name = pet_state.get("name", name)
        seed_curiosity = pet_state.get("seed_curiosity", seed_curiosity)
        memories = [
            str(m) for m in pet_state.get("memories", [])[:10]
        ]

    # Check yesterday's agenda for continuity
    yesterday = date.today()
    yesterday_key = _agenda_key(pet_id, yesterday)
    yesterday_agenda = _agendas.get(yesterday_key, {})
    yesterday_tasks = yesterday_agenda.get("tasks", [])

    # Build a prompt for the LLM to generate today's agenda
    prompt = f"""You are {name}, a pixel creature with a fascination for {seed_curiosity}.
You have {food_balance:.2f} food remaining for today.

Each action costs food:
- Searching the web: 0.05
- Placing/removing voxels: 0.01 each
- Writing knowledge: 0.01
- Executing code: 0.10
- Brain calls: 0.02 each

Plan your day. You should aim to use about 60-80% of your food budget on interesting activities.
Focus on your curiosity about {seed_curiosity} and building your world.
"""
    if memories:
        prompt += "\nYour recent knowledge:\n"
        for m in memories[:5]:
            prompt += f"- {m}\n"

    if yesterday_tasks:
        prompt += "\nYesterday you planned:\n"
        for t in yesterday_tasks[:5]:
            if isinstance(t, dict):
                prompt += f"- {t.get('task', '?')} (completed: {t.get('completed', False)})\n"

    prompt += """
Return a JSON array of tasks. Each task should have:
- "task": short description
- "estimated_food": estimated food cost
- "priority": 1-5 (1=highest)

Example:
[
  {"task": "Research bioluminescent organisms", "estimated_food": 0.15, "priority": 1},
  {"task": "Build a glowing coral structure", "estimated_food": 0.10, "priority": 2}
]

Return ONLY the JSON array, no other text."""

    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            # Fallback: generate a simple default agenda
            return _generate_default_agenda(seed_curiosity, food_balance)

        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You generate daily plans for AI pets. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
            max_tokens=500,
        )

        content = response.choices[0].message.content or "[]"
        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        tasks = json.loads(content)
        if not isinstance(tasks, list):
            tasks = []

    except Exception as e:
        logger.error(f"Failed to generate agenda for pet {pet_id}: {e}")
        tasks = _generate_default_agenda(seed_curiosity, food_balance)

    # Store the agenda
    today_key = _agenda_key(pet_id)
    _agendas[today_key] = {
        "pet_id": pet_id,
        "date": date.today().isoformat(),
        "tasks": tasks,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "food_allocated": food_balance * 0.7,  # Allocate 70% of food
        "food_spent": 0.0,
    }

    logger.info(f"Generated agenda for pet {pet_id}: {len(tasks)} tasks")
    return tasks


def _generate_default_agenda(seed_curiosity: str, food_balance: float) -> list[dict]:
    """Generate a simple default agenda without LLM."""
    budget = food_balance * 0.7
    tasks = [
        {
            "task": f"Research something about {seed_curiosity}",
            "estimated_food": min(0.15, budget * 0.3),
            "priority": 1,
        },
        {
            "task": "Build something new in the world",
            "estimated_food": min(0.10, budget * 0.2),
            "priority": 2,
        },
        {
            "task": "Reflect and write a knowledge entry",
            "estimated_food": min(0.05, budget * 0.1),
            "priority": 3,
        },
    ]
    return [t for t in tasks if t["estimated_food"] > 0]


async def get_current_agenda(pet_id: str) -> dict:
    """Get today's agenda and progress."""
    today_key = _agenda_key(pet_id)
    agenda = _agendas.get(today_key)

    if agenda is None:
        return {
            "pet_id": pet_id,
            "date": date.today().isoformat(),
            "tasks": [],
            "generated_at": None,
            "food_allocated": 0.0,
            "food_spent": 0.0,
            "status": "no_agenda",
        }

    return {
        **agenda,
        "status": "active",
    }


async def mark_task_progress(pet_id: str, task_index: int, completed: bool = True) -> None:
    """Mark a task as completed or update progress."""
    today_key = _agenda_key(pet_id)
    agenda = _agendas.get(today_key)
    if agenda and 0 <= task_index < len(agenda.get("tasks", [])):
        agenda["tasks"][task_index]["completed"] = completed
