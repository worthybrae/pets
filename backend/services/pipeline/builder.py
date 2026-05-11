"""Stage 3: Builder — executes build plans using existing tool handlers."""

import logging
from typing import Any

from backend.services.pipeline.types import BuildPlan, BuildReport
from backend.services.tools import execute_tool
from backend.services.events import get_broadcaster

logger = logging.getLogger(__name__)


async def run_builder(
    pet_id: str,
    plan: BuildPlan,
) -> BuildReport:
    """Execute a build plan phase by phase. Returns a BuildReport."""

    total_voxels = 0
    completed_phases: list[str] = []
    remaining_phases: list[str] = []
    errors: list[str] = []

    broadcaster = get_broadcaster()

    for i, phase in enumerate(plan.phases):
        if broadcaster:
            await broadcaster.pet_thought(
                pet_id,
                f"Building: {phase.name} — {phase.description}",
                "pipeline_builder",
            )

        phase_voxels = 0
        phase_errors = []

        for op in phase.operations:
            op_type = op.get("type", "")

            if op_type in ("fill_region", "place_sphere", "place_cylinder",
                           "place_voxels", "remove_voxels", "execute_code"):
                args = {k: v for k, v in op.items() if k != "type"}
                result = await execute_tool(pet_id, op_type, args)

                if result.get("success"):
                    placed = result.get("placed", 0) or result.get("voxels_generated", 0)
                    phase_voxels += placed
                else:
                    error_msg = result.get("error", "unknown error")
                    phase_errors.append(f"{phase.name}/{op_type}: {error_msg}")
                    logger.warning(f"Builder op failed: {op_type} in {phase.name}: {error_msg}")
            else:
                phase_errors.append(f"Unknown operation type: {op_type}")

        total_voxels += phase_voxels

        if phase_errors:
            errors.extend(phase_errors)
            if phase_voxels > 0:
                completed_phases.append(phase.name)
            else:
                remaining_phases.append(phase.name)
        else:
            completed_phases.append(phase.name)

        logger.info(f"Phase '{phase.name}' complete: {phase_voxels} voxels placed")

    return BuildReport(
        voxels_placed=total_voxels,
        phases_completed=completed_phases,
        phases_remaining=remaining_phases,
        errors=errors,
    )
