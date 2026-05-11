"""Stage 2: Architect — spatial planning using o4-mini."""

import json
import logging
import os
from typing import Any

from openai import AsyncOpenAI

from backend.services.pipeline.context import PipelineContext
from backend.services.pipeline.types import BuildPlan, BuildPhase, CreativeBrief

logger = logging.getLogger(__name__)

ARCHITECT_SYSTEM_PROMPT = """You are the spatial planner for a voxel world. The Dreamer has decided what to build. Your job is to create a detailed build plan with coordinates, materials, and phases.

=== Available Build Tools ===
- fill_region: Rectangular box. Params: x1,y1,z1,x2,y2,z2,r,g,b,a,noise(0-60),hollow(bool),gradient_color({{r,g,b}})
- place_sphere: Sphere. Params: cx,cy,cz,radius(1-50),r,g,b,a,noise,hollow
- place_cylinder: Vertical cylinder. Params: cx,cz,y_bottom,y_top,radius(1-50),r,g,b,a,noise,hollow
- place_voxels: Individual voxels (max 5000). For fine detail only.
- execute_code: Python code that generates voxels procedurally. For complex organic shapes.

=== World Map (Existing Regions) ===
{regions}

=== Dreamer's Creative Brief ===
Vision: {vision}
Emotional intent: {emotional_intent}
Inspiration: {inspiration}

=== World Bounds ===
The base meadow is (-32,0,-32) to (47,0,47). Ground is at y=0. You can build anywhere — go beyond the meadow.
Pet is currently at ({px},{py},{pz}).

=== Instructions ===
Create a structured build plan. Place the build in a location that makes spatial sense relative to existing regions. Avoid overlapping existing structures.

Use noise for natural textures (10=smooth wood, 20=rough stone, 30=organic earth).
Use hollow=true for buildings with interiors.
Use gradient_color for walls that shift color.
Use execute_code operations for organic/procedural shapes (trees, terrain, fractals).

For execute_code operations, write the full Python code. The code must populate a `voxels` list with {{x,y,z,r,g,b,a}} dicts. You have access to `math`, `random`, `sin`, `cos`, `sqrt`, `pi`.

Respond with ONLY a JSON object:
{{
  "project": "name",
  "region_name": "name for the world map",
  "region_description": "what this region is",
  "region_tags": ["tag1", "tag2"],
  "bounds": {{"min": [x,y,z], "max": [x,y,z]}},
  "phases": [
    {{
      "name": "phase_name",
      "description": "what this phase builds",
      "operations": [
        {{"type": "fill_region", "x1": 0, ...}},
        {{"type": "execute_code", "code": "python code here"}}
      ]
    }}
  ],
  "relationships": {{"direction_of": "region_name"}}
}}"""


async def run_architect(
    ctx: PipelineContext,
    brief: CreativeBrief,
    model: str = "o4-mini",
) -> tuple[BuildPlan, Any]:
    """Run the Architect stage. Returns a BuildPlan and token usage."""

    # Format regions
    if ctx.regions:
        region_lines = []
        for r in ctx.regions:
            region_lines.append(
                f"- {r['name']} [{r['status']}] "
                f"({r['bounds_min_x']},{r['bounds_min_y']},{r['bounds_min_z']}) to "
                f"({r['bounds_max_x']},{r['bounds_max_y']},{r['bounds_max_z']})"
            )
        regions_text = "\n".join(region_lines)
    else:
        regions_text = "No existing regions. The world is empty."

    system = ARCHITECT_SYSTEM_PROMPT.format(
        regions=regions_text,
        vision=brief.vision,
        emotional_intent=brief.emotional_intent,
        inspiration=brief.inspiration_source or "N/A",
        px=int(ctx.position.get("x", 0)),
        py=int(ctx.position.get("y", 0)),
        pz=int(ctx.position.get("z", 0)),
    )

    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Create the build plan for: {brief.vision}"},
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.error(f"Architect returned invalid JSON: {content[:500]}")
        data = {
            "project": "Unknown", "region_name": "Unknown",
            "region_description": brief.vision, "region_tags": [],
            "bounds": {"min": [0, 0, 0], "max": [10, 10, 10]},
            "phases": [], "relationships": {},
        }

    phases = []
    for p in data.get("phases", []):
        phases.append(BuildPhase(
            name=p.get("name", "unnamed"),
            description=p.get("description", ""),
            operations=p.get("operations", []),
        ))

    plan = BuildPlan(
        project=data.get("project", "Unknown"),
        region_name=data.get("region_name", data.get("project", "Unknown")),
        region_description=data.get("region_description", brief.vision),
        region_tags=data.get("region_tags", []),
        bounds=data.get("bounds", {"min": [0, 0, 0], "max": [10, 10, 10]}),
        phases=phases,
        relationships=data.get("relationships", {}),
    )

    return plan, response.usage
