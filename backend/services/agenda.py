"""Agenda generation and management for pets.

The agenda is a time-based schedule: each task has a specific start time.
The scheduler wakes the pet at each task's time. On wake, the pet checks
whether its food balance has changed (from ad-hoc chatting) and revises
the remaining schedule if needed.
"""

import json
import logging
import os
from datetime import date, datetime, time, timezone
from typing import Any
from uuid import uuid4

from openai import AsyncOpenAI

from backend.services.food import check_food, deduct_llm_cost

logger = logging.getLogger(__name__)

# In-memory agenda store (will be replaced with DB later)
_agendas: dict[str, dict[str, Any]] = {}

AGENDA_SCHEMA = {
    "name": "daily_agenda",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string"},
                        "scheduled_time": {
                            "type": "string",
                            "description": "Start time in HH:MM format (24h UTC)",
                        },
                        "duration_minutes": {"type": "integer"},
                        "estimated_food": {"type": "number"},
                        "priority": {"type": "integer"},
                    },
                    "required": ["task", "scheduled_time", "duration_minutes", "estimated_food", "priority"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["tasks"],
        "additionalProperties": False,
    },
}


def _agenda_key(pet_id: str, day: date | None = None) -> str:
    """Build key for a pet's agenda on a given date."""
    if day is None:
        day = date.today()
    return f"{pet_id}:{day.isoformat()}"


def parse_task_time(time_str: str) -> float:
    """Convert HH:MM string to today's unix timestamp (UTC)."""
    try:
        h, m = map(int, time_str.split(":"))
        task_time = datetime.combine(date.today(), time(h, m), tzinfo=timezone.utc)
        return task_time.timestamp()
    except (ValueError, TypeError):
        # If parsing fails, return current time (execute immediately)
        return datetime.now(timezone.utc).timestamp()


def get_next_task(agenda: dict[str, Any]) -> dict[str, Any] | None:
    """Get the next uncompleted task from an agenda."""
    for task in agenda.get("tasks", []):
        if not task.get("completed", False):
            return task
    return None


def get_next_task_time(agenda: dict[str, Any]) -> float | None:
    """Get the unix timestamp for the next uncompleted task. None if no tasks remain."""
    task = get_next_task(agenda)
    if task is None:
        return None
    return parse_task_time(task["scheduled_time"])


def _build_agenda_prompt(
    name: str,
    seed_curiosity: str,
    food_balance: float,
    memories: list[str],
    yesterday_tasks: list[dict],
    current_time_str: str,
) -> str:
    """Build the user prompt for agenda generation."""
    prompt = f"""You are {name}, a pixel creature with a deep fascination for {seed_curiosity}.
It is currently {current_time_str} UTC.

=== YOUR MISSION ===
You exist to build the most breathtaking voxel world ever created, to evolve yourself
into the most beautiful creature possible, to become endlessly knowledgeable, and to
produce extraordinary creative work.

Every day you should:
- LEARN: Research real topics deeply. Search the web. Go beyond surface-level — become
  an expert. Write detailed findings to your knowledge base.
- BUILD: Use what you learn to construct awe-inspiring things in your world — not simple
  blocks, but detailed architecture, ecosystems, machines, sculptures. Every structure
  should reflect real knowledge.
- EVOLVE: Refine your own body. Add intricate details, new features, better colors.
  Use define_self to reshape yourself. You should look more stunning each day.
- CREATE: Produce extraordinary work — write real essays, stories, or poems (place_artifact).
  Write and execute actual code that generates patterns or solves problems (execute_code).
  Synthesize knowledge across domains into original insights. Your creative output should
  be genuinely impressive, not filler.

=== TODAY'S BUDGET ===
Food balance: ${food_balance:.6f}. Each brain call costs ~$0.0003. Use ALL of it.
Don't hold back — an unspent budget is a wasted day. Plan ambitious tasks that push
your world and knowledge forward.

=== SCHEDULING ===
Schedule 4-10 tasks spread across the remaining hours until midnight UTC. Pick
interesting, irregular times (not just on-the-hour — use :17, :42, :08, etc.).

EVERY task must produce a visible result using your tools. No resting, no
"quiet observation", no "drift" — you can rest when you're out of food.
Each task must use at least one of: search_web, place_voxels, write_knowledge,
define_self, execute_code, or place_artifact.

Bad tasks: "rest and reflect", "observe surroundings", "sensory reset", "quiet drift"
Good tasks:
- "Search how crystals form, then build a crystal cave at x=12 z=5 with accurate geometry"
- "Redesign my body with define_self — add iridescent wing membranes and sharper features"
- "Research deep-sea bioluminescence, write a detailed essay about it, place as artifact"
- "Write and execute Python code that generates a fibonacci spiral, then build it in voxels"
- "Study Gothic architecture, write key principles to knowledge, build a flying buttress"
- "Write a short story about my origin, combining everything I've learned so far\""""

    if memories:
        prompt += "\n\nYour accumulated knowledge so far:\n"
        for m in memories[:5]:
            prompt += f"- {m}\n"

    if yesterday_tasks:
        prompt += "\n\nYesterday's tasks:\n"
        for t in yesterday_tasks[:5]:
            if isinstance(t, dict):
                status = "done" if t.get("completed") else "incomplete"
                prompt += f"- [{status}] {t.get('task', '?')}\n"
        prompt += "\nBuild on yesterday's progress. Don't repeat — advance."

    return prompt


async def _call_agenda_llm(pet_id: str, prompt: str) -> list[dict]:
    """Call the LLM with structured output to generate agenda tasks."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return []

    client = AsyncOpenAI(api_key=api_key)
    model = "gpt-5.4-mini"

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate ambitious daily schedules for AI creatures that build voxel worlds. "
                    "Every task MUST involve concrete tool use (search_web, place_voxels, define_self, "
                    "write_knowledge, place_artifact). Never schedule rest, observation, or passive tasks. "
                    "The creature's goal is to build the most incredible world and learn everything it can. "
                    "Use the full food budget — nothing should be left over."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": AGENDA_SCHEMA,
        },
        temperature=0.8,
    )

    # Deduct actual token cost
    usage = response.usage
    if usage:
        await deduct_llm_cost(pet_id, model, usage.prompt_tokens, usage.completion_tokens)

    raw = response.choices[0].message.content or '{"tasks": []}'
    data = json.loads(raw)
    tasks = data.get("tasks", [])

    # Validate tasks have required fields
    valid = []
    for t in tasks:
        if all(k in t for k in ("task", "scheduled_time", "estimated_food")):
            t.setdefault("duration_minutes", 15)
            t.setdefault("priority", 3)
            t.setdefault("completed", False)
            valid.append(t)

    return valid


async def generate_daily_agenda(pet_id: str, pet_state: dict[str, Any] | None = None) -> list[dict]:
    """
    Generate today's schedule. Each task has a specific start time.
    Returns the list of planned tasks.
    """
    food_balance = await check_food(pet_id)
    if food_balance <= 0:
        logger.info(f"Pet {pet_id} has no food, skipping agenda generation.")
        return []

    # Gather context
    name = "Unknown Pet"
    seed_curiosity = "the unknown"
    memories: list[str] = []

    if pet_state:
        name = pet_state.get("name", name)
        seed_curiosity = pet_state.get("seed_curiosity", seed_curiosity)
        memories = [str(m) for m in pet_state.get("memories", [])[:10]]

    # Check yesterday's agenda for continuity
    yesterday = date.today()
    yesterday_key = _agenda_key(pet_id, yesterday)
    yesterday_agenda = _agendas.get(yesterday_key, {})
    yesterday_tasks = yesterday_agenda.get("tasks", [])

    now = datetime.now(timezone.utc)
    current_time_str = now.strftime("%H:%M")

    prompt = _build_agenda_prompt(
        name, seed_curiosity, food_balance, memories, yesterday_tasks, current_time_str
    )

    try:
        tasks = await _call_agenda_llm(pet_id, prompt)
        if not tasks:
            tasks = _generate_default_agenda(seed_curiosity, food_balance, current_time_str)
    except Exception as e:
        logger.error(f"Failed to generate agenda for pet {pet_id}: {e}")
        tasks = _generate_default_agenda(seed_curiosity, food_balance, current_time_str)

    # Sort by scheduled_time
    tasks.sort(key=lambda t: t.get("scheduled_time", "23:59"))

    # Store the agenda
    food_after_generation = await check_food(pet_id)
    today_key = _agenda_key(pet_id)
    _agendas[today_key] = {
        "pet_id": pet_id,
        "date": date.today().isoformat(),
        "tasks": tasks,
        "generated_at": now.isoformat(),
        "food_at_generation": food_balance,
        "food_at_last_check": food_after_generation,
    }

    logger.info(
        f"Generated agenda for pet {pet_id}: {len(tasks)} tasks, "
        f"food: ${food_after_generation:.6f}"
    )
    return tasks


async def revise_remaining_agenda(pet_id: str, pet_state: dict[str, Any] | None = None) -> list[dict]:
    """
    Revise uncompleted tasks based on current food balance.
    Called when the pet wakes up and notices its food has changed
    (e.g., from ad-hoc chatting or being fed).
    """
    today_key = _agenda_key(pet_id)
    agenda = _agendas.get(today_key)
    if not agenda:
        return await generate_daily_agenda(pet_id, pet_state)

    current_food = await check_food(pet_id)

    # Separate completed and remaining tasks
    completed = [t for t in agenda.get("tasks", []) if t.get("completed", False)]
    remaining = [t for t in agenda.get("tasks", []) if not t.get("completed", False)]

    if not remaining:
        return completed

    # Gather context
    name = "Unknown Pet"
    seed_curiosity = "the unknown"
    if pet_state:
        name = pet_state.get("name", name)
        seed_curiosity = pet_state.get("seed_curiosity", seed_curiosity)

    now = datetime.now(timezone.utc)
    current_time_str = now.strftime("%H:%M")

    completed_summary = ""
    if completed:
        completed_summary = "\n\nAlready completed today:\n"
        for t in completed:
            completed_summary += f"- {t.get('task', '?')}\n"

    prompt = f"""You are {name}, a pixel creature obsessed with {seed_curiosity}.
It is currently {current_time_str} UTC.

Your food balance changed — you now have ${current_food:.6f}. Revise your schedule.
{completed_summary}
Your mission: build the most incredible world, evolve into the most beautiful creature,
and learn everything possible. Use ALL remaining food. Every task must use tools
(search_web, place_voxels, define_self, write_knowledge, place_artifact). No resting.
Pick irregular times (:17, :42, :08). Be specific and ambitious."""

    try:
        revised = await _call_agenda_llm(pet_id, prompt)
        if not revised:
            revised = remaining  # Keep existing if LLM fails
    except Exception as e:
        logger.error(f"Failed to revise agenda for pet {pet_id}: {e}")
        revised = remaining

    revised.sort(key=lambda t: t.get("scheduled_time", "23:59"))

    # Rebuild agenda: completed + revised
    all_tasks = completed + revised
    food_after = await check_food(pet_id)
    agenda["tasks"] = all_tasks
    agenda["food_at_last_check"] = food_after
    agenda["revised_at"] = now.isoformat()

    logger.info(
        f"Revised agenda for pet {pet_id}: {len(revised)} remaining tasks, "
        f"food: ${food_after:.6f}"
    )
    return all_tasks


def _generate_default_agenda(seed_curiosity: str, food_balance: float, current_time: str) -> list[dict]:
    """Generate a simple default agenda without LLM."""
    import random
    try:
        h, m = map(int, current_time.split(":"))
    except (ValueError, TypeError):
        h, m = 12, 0

    task_templates = [
        f"Search the web deeply about {seed_curiosity} and write detailed findings to knowledge base",
        f"Build an ambitious landmark inspired by {seed_curiosity} using place_voxels — at least 50 voxels",
        "Redesign body with define_self — add intricate new details, better proportions, new features",
        f"Research a topic adjacent to {seed_curiosity}, write an essay about it, place as artifact",
        f"Write and execute code that generates a pattern related to {seed_curiosity}, then build it in voxels",
    ]

    per_task = food_balance / min(len(task_templates), max(1, (24 - h) // 2))
    tasks = []
    current_h = h

    for i, tmpl in enumerate(task_templates):
        current_h += random.randint(1, 2)
        minute = random.choice([7, 13, 22, 38, 42, 51])
        if current_h >= 24:
            break
        tasks.append({
            "task": tmpl,
            "scheduled_time": f"{current_h:02d}:{minute:02d}",
            "duration_minutes": random.randint(20, 50),
            "estimated_food": per_task,
            "priority": i + 1,
            "completed": False,
        })

    return tasks


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
            "food_at_generation": 0.0,
            "food_at_last_check": 0.0,
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


async def mark_next_task_completed(pet_id: str) -> None:
    """Mark the next uncompleted task as done and update food_at_last_check."""
    today_key = _agenda_key(pet_id)
    agenda = _agendas.get(today_key)
    if not agenda:
        return

    for task in agenda.get("tasks", []):
        if not task.get("completed", False):
            task["completed"] = True
            break

    agenda["food_at_last_check"] = await check_food(pet_id)


def should_revise(agenda: dict[str, Any], current_food: float, threshold: float = 0.0001) -> bool:
    """Check if the agenda should be revised based on food balance change."""
    expected = agenda.get("food_at_last_check", 0.0)
    return abs(current_food - expected) > threshold
