"""Stage 4: Critic — evaluates builds using o4-mini."""

import json
import logging
import os
from typing import Any

from openai import AsyncOpenAI

from backend.services.pipeline.context import PipelineContext
from backend.services.pipeline.types import (
    BuildPlan,
    BuildReport,
    CreativeBrief,
    CriticReview,
    ReviewIssue,
)

logger = logging.getLogger(__name__)

CRITIC_SYSTEM_PROMPT = """You are the quality critic for a pet's voxel world builds. You evaluate what was built against the original creative vision.

=== Creative Brief (Original Intent) ===
Vision: {vision}
Emotional intent: {emotional_intent}

=== Build Plan ===
Project: {project}
Phases planned: {phases_planned}

=== Build Results ===
Voxels placed: {voxels_placed}
Phases completed: {phases_completed}
Phases remaining: {phases_remaining}
Errors: {errors}

=== Recent World Context ===
{journal}

=== Instructions ===
Evaluate this build session. Consider:
- Did the build match the creative brief's vision and emotional intent?
- What worked well? What structures or details are effective?
- What needs improvement? (texture variation, density, scale, spatial coherence)
- What should the next session focus on?
- Should this region be marked as "complete", "in_progress", or "needs_revision"?

Be specific and constructive. Reference particular aspects of the build.

Respond with ONLY a JSON object:
{{
  "overall_assessment": "1-2 sentence summary",
  "strengths": ["strength 1", "strength 2"],
  "issues": [
    {{"area": "what part", "problem": "what's wrong", "suggestion": "how to fix"}}
  ],
  "next_session_priorities": ["priority 1", "priority 2"],
  "region_status": "in_progress|complete|needs_revision"
}}"""


async def run_critic(
    ctx: PipelineContext,
    brief: CreativeBrief,
    plan: BuildPlan,
    report: BuildReport,
    model: str = "o4-mini",
) -> tuple[CriticReview, Any]:
    """Run the Critic stage. Returns a CriticReview and token usage."""

    # Format journal context
    if ctx.recent_journal:
        journal_lines = [
            f"- {j.get('creative_brief', '?')[:80]} ({j.get('voxels_placed', 0)} voxels)"
            for j in ctx.recent_journal[:3]
        ]
        journal_text = "\n".join(journal_lines)
    else:
        journal_text = "This is the first build session."

    phases_planned = ", ".join(p.name for p in plan.phases)

    system = CRITIC_SYSTEM_PROMPT.format(
        vision=brief.vision,
        emotional_intent=brief.emotional_intent,
        project=plan.project,
        phases_planned=phases_planned,
        voxels_placed=report.voxels_placed,
        phases_completed=", ".join(report.phases_completed) or "none",
        phases_remaining=", ".join(report.phases_remaining) or "none",
        errors="; ".join(report.errors) if report.errors else "none",
        journal=journal_text,
    )

    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": "Evaluate this build session."},
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {
            "overall_assessment": "Unable to evaluate",
            "strengths": [], "issues": [],
            "next_session_priorities": [], "region_status": "in_progress",
        }

    issues = []
    for issue_data in data.get("issues", []):
        issues.append(ReviewIssue(
            area=issue_data.get("area", "unknown"),
            problem=issue_data.get("problem", "unknown"),
            suggestion=issue_data.get("suggestion", ""),
        ))

    review = CriticReview(
        overall_assessment=data.get("overall_assessment", "No assessment"),
        strengths=data.get("strengths", []),
        issues=issues,
        next_session_priorities=data.get("next_session_priorities", []),
        region_status=data.get("region_status", "in_progress"),
    )

    return review, response.usage
