"""Stage 1: Dreamer — creative ideation using o4-mini."""

import json
import logging
import os
from typing import Any

from openai import AsyncOpenAI

from backend.services.pipeline.context import PipelineContext
from backend.services.pipeline.types import CreativeBrief

logger = logging.getLogger(__name__)

DREAMER_SYSTEM_PROMPT = """You are the creative mind of a pet named {name}. Your job is to decide what to build next in your voxel world.

=== Your Soul ===
{soul}

=== Your Stats ===
{stats}

=== Your World Map ===
{regions}

=== Recent Build Sessions ===
{journal}

=== Last Critic Review ===
{last_review}

=== Owner's Themes (Mood Board) ===
{mood_board}

=== Your Knowledge ===
{knowledge}

=== Instructions ===
You are the DREAMER. Your job is pure creative ideation. Decide WHAT to build and WHY.

Consider:
- What regions are in_progress or need_revision? Should you continue or start fresh?
- What themes from your owner's conversations could inspire your next build?
- How does this fit the overall vision of your world?
- What would delight your owner when they check in?

Do NOT include coordinates, voxel counts, or technical details. That's the Architect's job.

Respond with ONLY a JSON object:
{{
  "vision": "Describe what you want to build and why, in 2-4 sentences",
  "emotional_intent": "The feeling this build should evoke (1 sentence)",
  "inspiration_source": "What inspired this? Owner conversation, previous build, your personality, etc."
}}"""


async def run_dreamer(
    ctx: PipelineContext,
    model: str = "o4-mini",
    trigger: str = "autonomous_tick",
) -> tuple[CreativeBrief, Any]:
    """Run the Dreamer stage. Returns a CreativeBrief and token usage."""

    # Format regions for prompt
    if ctx.regions:
        region_lines = []
        for r in ctx.regions:
            region_lines.append(
                f"- {r['name']} [{r['status']}]: {r.get('description', 'no description')} "
                f"at ({r['bounds_min_x']},{r['bounds_min_y']},{r['bounds_min_z']}) to "
                f"({r['bounds_max_x']},{r['bounds_max_y']},{r['bounds_max_z']})"
            )
        regions_text = "\n".join(region_lines)
    else:
        regions_text = "Your world is empty. This is a blank canvas — build something extraordinary."

    # Format journal
    if ctx.recent_journal:
        journal_lines = []
        for j in ctx.recent_journal[:5]:
            brief = j.get("creative_brief", "no brief")
            voxels = j.get("voxels_placed", 0)
            journal_lines.append(f"- Built: {brief[:100]} ({voxels} voxels)")
        journal_text = "\n".join(journal_lines)
    else:
        journal_text = "No previous builds. This is your first session."

    # Format last review
    if ctx.last_review:
        review_text = json.dumps(ctx.last_review, indent=2)
    else:
        review_text = "No previous review."

    # Format knowledge
    if ctx.knowledge:
        knowledge_lines = [f"- {k.get('key', '?')}: {k.get('content', '')}" for k in ctx.knowledge[:15]]
        knowledge_text = "\n".join(knowledge_lines)
    else:
        knowledge_text = "No knowledge yet."

    # Format stats
    stats_text = ", ".join(f"{k}={v}" for k, v in ctx.pet_stats.items()) if ctx.pet_stats else "none"

    # Special first-build prompt
    if trigger == "birth":
        user_msg = (
            "You have just been born. Your world is an empty meadow. "
            "Dream of your first creation — something that will define who you are."
        )
    else:
        user_msg = "What do you want to build next? Dream big."

    system = DREAMER_SYSTEM_PROMPT.format(
        name=ctx.pet_name,
        soul=ctx.pet_soul or "No soul document yet.",
        stats=stats_text,
        regions=regions_text,
        journal=journal_text,
        last_review=review_text,
        mood_board=ctx.mood_board_summary or "No themes yet.",
        knowledge=knowledge_text,
    )

    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {"vision": content, "emotional_intent": "unknown", "inspiration_source": "unknown"}

    brief = CreativeBrief(
        vision=data.get("vision", "Expand the world"),
        emotional_intent=data.get("emotional_intent", "wonder"),
        inspiration_source=data.get("inspiration_source"),
    )

    return brief, response.usage
