"""Pipeline Runner — orchestrates Dreamer → Architect → Builder → Critic."""

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.services.pipeline.context import PipelineContext, load_pipeline_context
from backend.services.pipeline.dreamer import run_dreamer
from backend.services.pipeline.architect import run_architect
from backend.services.pipeline.builder import run_builder
from backend.services.pipeline.critic import run_critic
from backend.services.pipeline.types import (
    BuildPlan,
    BuildReport,
    CreativeBrief,
    CriticReview,
)
from backend.services.world_map import WorldMapService
from backend.services.food import check_food, deduct_llm_cost
from backend.services.events import get_broadcaster

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of a full pipeline run."""

    brief: CreativeBrief | None = None
    plan: BuildPlan | None = None
    report: BuildReport | None = None
    review: CriticReview | None = None
    total_food_consumed: float = 0.0
    error: str | None = None


class PipelineRunner:
    """Orchestrates the four-stage Studio Pipeline."""

    def __init__(
        self,
        pet_id: str,
        pet_state: dict[str, Any],
        dreamer_model: str = "o4-mini",
        architect_model: str = "o4-mini",
        critic_model: str = "o4-mini",
    ):
        self.pet_id = pet_id
        self.pet_state = pet_state
        self.dreamer_model = dreamer_model
        self.architect_model = architect_model
        self.critic_model = critic_model

    async def run(self, trigger: str = "autonomous_tick") -> PipelineResult:
        """Run the full pipeline: Dreamer → Architect → Builder → Critic."""

        result = PipelineResult()
        broadcaster = get_broadcaster()

        # Check food
        food = await check_food(self.pet_id)
        if food <= 0:
            result.error = "No food remaining."
            return result

        # Load shared context
        ctx = await load_pipeline_context(self.pet_id, self.pet_state)

        # --- Stage 1: Dreamer ---
        if broadcaster:
            await broadcaster.pet_thought(self.pet_id, "Dreaming...", "pipeline_dreamer")

        try:
            brief, dreamer_usage = await run_dreamer(ctx, model=self.dreamer_model, trigger=trigger)
            result.brief = brief
            if dreamer_usage:
                ok, cost = await deduct_llm_cost(
                    self.pet_id, self.dreamer_model,
                    dreamer_usage.prompt_tokens, dreamer_usage.completion_tokens,
                )
                if not ok:
                    result.error = "Insufficient food for Dreamer."
                    return result
                result.total_food_consumed += cost
            logger.info(f"Dreamer: {brief.vision[:100]}")
        except Exception as e:
            logger.error(f"Dreamer failed for {self.pet_id}: {e}")
            result.error = f"Dreamer failed: {e}"
            return result

        # --- Stage 2: Architect ---
        if broadcaster:
            await broadcaster.pet_thought(self.pet_id, "Planning the build...", "pipeline_architect")

        try:
            plan, architect_usage = await run_architect(ctx, brief, model=self.architect_model)
            result.plan = plan
            if architect_usage:
                ok, cost = await deduct_llm_cost(
                    self.pet_id, self.architect_model,
                    architect_usage.prompt_tokens, architect_usage.completion_tokens,
                )
                if not ok:
                    result.error = "Insufficient food for Architect."
                    return result
                result.total_food_consumed += cost
            logger.info(f"Architect: {plan.project} — {len(plan.phases)} phases")
        except Exception as e:
            logger.error(f"Architect failed for {self.pet_id}: {e}")
            result.error = f"Architect failed: {e}"
            return result

        # Register region in world map
        world_map = WorldMapService(self.pet_id)
        try:
            bounds_min = plan.bounds.get("min", [0, 0, 0])
            bounds_max = plan.bounds.get("max", [10, 10, 10])
            region_id = await world_map.create_region(
                name=plan.region_name,
                description=plan.region_description,
                tags=plan.region_tags,
                bounds_min=tuple(bounds_min),
                bounds_max=tuple(bounds_max),
                relationships=plan.relationships,
                status="in_progress",
            )
        except Exception as e:
            logger.warning(f"Failed to register region: {e}")
            region_id = None

        # --- Stage 3: Builder ---
        if broadcaster:
            await broadcaster.pet_thought(self.pet_id, "Building...", "pipeline_builder")

        try:
            report = await run_builder(self.pet_id, plan)
            result.report = report
            logger.info(f"Builder: {report.voxels_placed} voxels placed, "
                        f"{len(report.phases_completed)} phases complete")
        except Exception as e:
            logger.error(f"Builder failed for {self.pet_id}: {e}")
            result.error = f"Builder failed: {e}"
            return result

        # --- Stage 4: Critic ---
        if broadcaster:
            await broadcaster.pet_thought(self.pet_id, "Evaluating the build...", "pipeline_critic")

        try:
            review, critic_usage = await run_critic(
                ctx, brief, plan, report, model=self.critic_model,
            )
            result.review = review
            if critic_usage:
                ok, cost = await deduct_llm_cost(
                    self.pet_id, self.critic_model,
                    critic_usage.prompt_tokens, critic_usage.completion_tokens,
                )
                if not ok:
                    result.error = "Insufficient food for Critic (build was still placed)."
                result.total_food_consumed += cost
            logger.info(f"Critic: {review.overall_assessment}")
        except Exception as e:
            logger.error(f"Critic failed for {self.pet_id}: {e}")
            # Non-fatal: the build was already placed
            review = None

        # --- Persist Results ---

        # Update region status from critic
        if region_id and review:
            try:
                await world_map.update_region_status(region_id, review.region_status)
            except Exception as e:
                logger.warning(f"Failed to update region status: {e}")

        # Write journal entry
        try:
            await world_map.add_journal_entry(
                creative_brief=brief.vision,
                build_plan={
                    "project": plan.project,
                    "phases": [{"name": p.name, "description": p.description} for p in plan.phases],
                },
                critic_review={
                    "overall_assessment": review.overall_assessment,
                    "strengths": review.strengths,
                    "issues": [{"area": i.area, "problem": i.problem, "suggestion": i.suggestion}
                               for i in review.issues],
                    "next_session_priorities": review.next_session_priorities,
                } if review else {"overall_assessment": "No review (critic failed)"},
                region_id=region_id,
                voxels_placed=report.voxels_placed,
            )
        except Exception as e:
            logger.warning(f"Failed to write journal entry: {e}")

        # Broadcast food update
        remaining_food = await check_food(self.pet_id)
        if broadcaster:
            await broadcaster.food_updated(self.pet_id, remaining_food)

        return result
