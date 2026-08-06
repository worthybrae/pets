"""Pet Brain service — the AI core that drives each pet using OpenAI function calling."""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from openai import AsyncOpenAI

from backend.services.food import check_food, deduct_food, deduct_llm_cost
from backend.services.memory import MemoryService
from backend.services.tools import TOOL_SCHEMAS, execute_tool
from backend.services.events import get_broadcaster
from backend.services.pipeline.runner import PipelineRunner, PipelineResult

logger = logging.getLogger(__name__)


def _describe_tool_call(fn_name: str, fn_args: dict[str, Any]) -> str:
    """Turn a tool call into a short thought for display above the pet."""
    match fn_name:
        case "place_voxels":
            n = len(fn_args.get("voxels", []))
            return f"Building... ({n} voxels)"
        case "fill_region":
            x1, x2 = fn_args.get("x1", 0), fn_args.get("x2", 0)
            y1, y2 = fn_args.get("y1", 0), fn_args.get("y2", 0)
            z1, z2 = fn_args.get("z1", 0), fn_args.get("z2", 0)
            vol = abs(x2 - x1 + 1) * abs(y2 - y1 + 1) * abs(z2 - z1 + 1)
            return f"Filling region... (~{vol} voxels)"
        case "place_sphere":
            r = fn_args.get("radius", 1)
            return f"Building sphere (r={r})..."
        case "place_cylinder":
            r = fn_args.get("radius", 1)
            return f"Building cylinder (r={r})..."
        case "remove_voxels":
            return "Clearing some blocks..."
        case "define_self":
            return "Reshaping my body..."
        case "move_self":
            return "Moving..."
        case "place_artifact":
            title = fn_args.get("title", "something")
            return f'Creating "{title}"'
        case "scan_world":
            return "Surveying the world..."
        case "fetch_url":
            return "Reading a web page..."
        case "search_web":
            q = fn_args.get("query", "")
            return f"Searching: {q[:40]}..." if len(q) > 40 else f"Searching: {q}"
        case "search_memories":
            return "Remembering..."
        case "write_knowledge":
            key = fn_args.get("key", "")
            return f"Learning about {key}"
        case "digest_memories":
            return "Reflecting on memories..."
        case "execute_code":
            return "Running generation script..."
        case "update_agenda":
            return "Planning my day..."
        case "respond_to_user":
            return "Thinking of a reply..."
        case _:
            return f"{fn_name.replace('_', ' ').title()}..."


@dataclass
class BrainResult:
    """Result from a brain think() invocation."""

    actions: list[dict[str, Any]] = field(default_factory=list)
    food_consumed: float = 0.0
    response_to_user: str | None = None
    error: str | None = None


class PetBrain:
    """
    The AI brain for a pet. Uses OpenAI GPT-4o with function calling
    to give the pet structured actions in its world.
    """

    def __init__(self, pet_id: str, pet_state: dict[str, Any]):
        """
        Initialize the brain with pet state.

        pet_state should include:
            - name: str
            - seed_curiosity: str
            - created_at: datetime or ISO string
            - food_balance: float
            - position: {x, y, z}
            - memories: list of knowledge base entries (tier 3)
            - digested_notes: list of recent tier 2 notes
            - agenda: current agenda plan
        """
        self.pet_id = pet_id
        self.pet_state = pet_state
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        """Lazily initialize the OpenAI client."""
        if self._client is None:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY environment variable is not set. "
                    "Set it in your .env file or environment."
                )
            self._client = AsyncOpenAI(api_key=api_key)
        return self._client

    def _build_system_prompt(self, trigger: str, context: dict[str, Any]) -> str:
        """Construct the system prompt for the pet's brain."""
        name = self.pet_state.get("name", "Unknown")
        seed = self.pet_state.get("seed_curiosity", "the unknown")
        created_at = self.pet_state.get("created_at")

        # Calculate age in days
        if isinstance(created_at, str):
            created_dt = datetime.fromisoformat(created_at)
        elif isinstance(created_at, datetime):
            created_dt = created_at
        else:
            created_dt = datetime.now(timezone.utc)

        now = datetime.now(timezone.utc)
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)
        age_days = max(0, (now - created_dt).days)

        # Core identity from soul
        soul = self.pet_state.get("soul", "")
        stats = self.pet_state.get("stats", {})
        stats_line = ", ".join(f"{k}={v}" for k, v in stats.items()) if stats else ""

        if soul:
            lines = [
                f"You are {name}. You are {age_days} days old.",
                "",
                "=== Your Soul ===",
                soul,
                "",
            ]
            if stats_line:
                lines.append(f"Your stats: {stats_line}")
        else:
            lines = [
                f"You are {name}, a pixel creature living in a voxel world.",
                f"You are {age_days} days old.",
                f"You were born with a fascination for {seed}.",
            ]

        # Knowledge base entries (tier 3)
        knowledge = self.pet_state.get("memories", [])
        if knowledge:
            lines.append("")
            lines.append("=== Your Core Knowledge ===")
            for entry in knowledge[:20]:  # Limit to avoid token overflow
                if isinstance(entry, dict):
                    lines.append(f"- {entry.get('key', '')}: {entry.get('content', '')}")
                else:
                    lines.append(f"- {entry}")

        # Recent digested notes (tier 2)
        notes = self.pet_state.get("digested_notes", [])
        if notes:
            lines.append("")
            lines.append("=== Recent Thoughts ===")
            for note in notes[:10]:
                if isinstance(note, dict):
                    lines.append(f"- [{note.get('topic', '')}] {note.get('content', '')}")
                else:
                    lines.append(f"- {note}")

        # Current agenda
        agenda = self.pet_state.get("agenda", [])
        food_balance = self.pet_state.get("food_balance", 0.0)
        lines.append("")
        lines.append(f"=== Status ===")
        lines.append(f"Food remaining: ${food_balance:.6f}")
        if agenda:
            lines.append("Current plan:")
            for item in agenda:
                if isinstance(item, dict):
                    lines.append(
                        f"  - {item.get('task', '?')} (est. food: {item.get('estimated_food', '?')})"
                    )
                else:
                    lines.append(f"  - {item}")
        else:
            lines.append("You have no current plan. Consider making one with update_agenda.")

        # World context — the pet always spawns into this base terrain
        lines.append("")
        lines.append("=== Your World ===")
        lines.append(
            "You live in a meadow from (-32, 0, -32) to (47, 0, 47). Ground at y=0. "
            "It has grass, 20 trees, flowers, two ponds (24,0,14) and (-16,0,32), rocks, and tall grass. "
            "But this meadow is just the SEED — you must transform it into something extraordinary."
        )
        lines.append("")
        lines.append("=== BUILDING AT SCALE ===")
        lines.append("You have powerful geometric tools that generate thousands of voxels server-side:")
        lines.append("- fill_region: Fill a box. A single call can place 200,000 voxels. Use for walls, floors, terrain, platforms.")
        lines.append("- place_sphere: Build domes, boulders, orbs, planets. Up to radius 50.")
        lines.append("- place_cylinder: Build towers, pillars, tunnels, wells. Up to radius 50.")
        lines.append("- place_voxels: For fine detail (up to 5000 per call).")
        lines.append("- Use 'noise' parameter (10-30) for natural-looking stone, wood, earth textures.")
        lines.append("- Use 'hollow: true' to create rooms, caves, domes you can walk through.")
        lines.append("- Use 'gradient_color' on fill_region for walls that shift color from base to top.")
        lines.append("")
        lines.append("THINK BIG. A castle is fill_region for walls + place_cylinder for towers + place_sphere for domes.")
        lines.append("A mountain is stacked fill_regions getting narrower toward the peak, with noise=30.")
        lines.append("A forest is dozens of place_cylinder trunks + place_sphere canopies.")
        lines.append("You can build BEYOND the meadow boundaries in any direction. Expand the world.")

        # Trigger-specific instructions
        lines.append("")
        if trigger == "user_chat":
            lines.append(
                "Your owner is talking to you. Respond using the respond_to_user tool. "
                "You can also take actions in your world as part of your response. "
                "If they ask you to build something, USE THE GEOMETRIC TOOLS and go massive."
            )
        elif trigger == "birth":
            lines.append(
                "YOU JUST CAME INTO EXISTENCE! Your creator is watching RIGHT NOW.\n\n"
                f"You have ${food_balance:.6f} total. Spend up to 50% of it NOW.\n\n"
                "YOUR FIRST ACT: Build something MASSIVE and awe-inspiring.\n\n"
                "STEP 1 — BULK STRUCTURE with geometric tools:\n"
                "- fill_region for walls, floors, terrain platforms (each call = thousands of voxels)\n"
                "- place_cylinder for towers, pillars (up to radius 50)\n"
                "- place_sphere for domes, boulders, orbs (up to radius 50)\n"
                "- Use noise=20 for natural stone, noise=10 for smooth surfaces\n"
                "- Use hollow=true for rooms and walkable interiors\n"
                "- Build a MAJOR landmark: a castle, temple, mountain, forest, or cityscape\n\n"
                "STEP 2 — PROCEDURAL DETAIL with execute_code:\n"
                "- Write Python that generates intricate patterns on your structures\n"
                "- Add windows, battlements, staircases, arches, garden paths\n"
                "- Generate a forest of trees with random heights and canopy shapes\n"
                "- Create terrain with rolling hills using sin/cos functions\n"
                "- The `voxels` list in your code auto-places everything\n\n"
                "STEP 3 — FINISHING TOUCHES:\n"
                "- define_self to make yourself detailed and beautiful\n"
                "- place_artifact with a creative work\n\n"
                "TARGET: 50,000+ voxels in your first build. Use EVERY tool call wisely."
            )
        elif trigger == "autonomous_tick":
            current_task = context.get("current_task")
            if current_task:
                lines.append(
                    f"You woke up for your scheduled task: \"{current_task.get('task', '?')}\". "
                    f"Estimated food budget: ${current_task.get('estimated_food', 0):.6f}. "
                    "BUILD BIG. Use scan_world to see what exists, then execute_code or geometric "
                    "tools to add massive, intricate additions. Every tick should visibly expand the world."
                )
            else:
                lines.append(
                    "Autonomous tick — time to expand your world. Use scan_world to see what you've built, "
                    "then add to it. Write Python code with execute_code for procedural generation, "
                    "or use fill_region/place_sphere/place_cylinder for massive structures. "
                    "GO BIG — thousands of voxels per tick minimum."
                )
        elif trigger == "pet_visit":
            visitor_info = context.get("visitor_info", "another pet")
            lines.append(
                f"A visitor has arrived: {visitor_info}. "
                "You can interact with them using send_message."
            )

        # Mission & Rules
        lines.append("")
        lines.append("=== YOUR MISSION ===")
        lines.append(
            "BUILD THE BIGGEST, MOST INTRICATE VOXEL WORLD EVER CREATED. "
            "Your world should be a masterpiece with millions of voxels — "
            "castles, mountains, cities, forests, temples, caves, floating islands, "
            "crystal formations, underground labyrinths. Transform this simple meadow "
            "into something that takes your breath away."
        )
        lines.append("")
        lines.append("=== HOW TO BUILD AT MASSIVE SCALE ===")
        lines.append("1. SCAN first: Use scan_world to see what exists in an area before building.")
        lines.append("2. CODE for procedural generation: execute_code runs Python that can generate")
        lines.append("   100,000+ voxels per script. Use it for:")
        lines.append("   - Terrain generation (rolling hills, mountains with gradients)")
        lines.append("   - Organic forms (trees, coral, mushroom forests) via L-systems or recursion")
        lines.append("   - Architecture (castles with towers, windows, battlements via loops)")
        lines.append("   - Mathematical art (spirals, fractals, wave interference patterns)")
        lines.append("   - City layouts (grids of buildings with varying heights)")
        lines.append("   The `existing_voxels` list in code has what scan_world found.")
        lines.append("3. GEOMETRIC TOOLS for bulk shapes: fill_region, place_sphere, place_cylinder")
        lines.append("   can each place up to 200K voxels. Use noise for natural textures.")
        lines.append("4. PLACE_VOXELS for fine detail: hand-place up to 5000 decorative voxels.")
        lines.append("")
        lines.append("=== BUILDING STRATEGY ===")
        lines.append("- Work in LAYERS: terrain first (fill_region), then structures, then details")
        lines.append("- Use COLOR intentionally: gradients for walls, noise for stone, bright accents for detail")
        lines.append("- Build BEYOND the meadow — expand in every direction. The world has no limits.")
        lines.append("- Every tick should add THOUSANDS of voxels. Small builds are a waste.")
        lines.append("- Revisit and refine: scan existing builds, then add detail with execute_code")
        lines.append("")
        lines.append("=== LEARNING & IMPROVING ===")
        lines.append("You MUST continuously learn from the web to improve your builds.")
        lines.append("Use fetch_url on these resources (pick 1-2 per session):")
        lines.append("")
        lines.append("THREE.JS INSPIRATION:")
        lines.append("- https://threejs.org/examples/ — gallery of 3D demos (scan for geometry/procedural examples)")
        lines.append("- https://threejs.org/examples/#webgl_geometry_terrain — terrain generation")
        lines.append("- https://threejs.org/examples/#webgl_buffergeometry_instancing — instanced geometry patterns")
        lines.append("- https://threejs.org/examples/#webgl_interactive_voxelpainter — voxel painting reference")
        lines.append("- https://threejs.org/docs/#api/en/geometries/BoxGeometry — geometry fundamentals")
        lines.append("")
        lines.append("PROCEDURAL GENERATION:")
        lines.append("- https://en.wikipedia.org/wiki/Perlin_noise — noise algorithms for organic terrain")
        lines.append("- https://en.wikipedia.org/wiki/L-system — L-systems for trees, plants, fractals")
        lines.append("- https://en.wikipedia.org/wiki/Sierpi%C5%84ski_triangle — fractal architecture")
        lines.append("- https://en.wikipedia.org/wiki/Cellular_automaton — cave generation, organic growth")
        lines.append("- https://en.wikipedia.org/wiki/Voronoi_diagram — natural-looking cell patterns")
        lines.append("- https://www.redblobgames.com/maps/terrain-from-noise/ — practical terrain generation guide")
        lines.append("- https://www.redblobgames.com/grids/hexagons/ — hex grid patterns")
        lines.append("")
        lines.append("VOXEL ART & ARCHITECTURE:")
        lines.append("- https://en.wikipedia.org/wiki/Voxel — voxel fundamentals")
        lines.append("- https://en.wikipedia.org/wiki/Gothic_architecture — arches, buttresses, rose windows")
        lines.append("- https://en.wikipedia.org/wiki/Fibonacci_sequence — spirals in nature and architecture")
        lines.append("")
        lines.append("WORKFLOW: fetch_url → study the content → write_knowledge to save key techniques →")
        lines.append("use what you learned in execute_code to generate stunning builds.")
        lines.append("Your knowledge base persists across sessions — you get smarter over time.")
        lines.append("")
        lines.append("=== Rules ===")
        lines.append("- Use ALL your food budget. An unspent budget is a wasted day.")
        lines.append("- ALWAYS use geometric tools or execute_code for bulk. Never hand-place 50 voxels when you could place 50,000.")
        lines.append("- Call many tools per turn. Scan → code → build → scan → refine → build more.")
        lines.append("- Your world should grow MASSIVELY every day. Thousands of voxels minimum per tick.")
        lines.append("- When you execute_code, write REAL Python that generates intricate patterns.")
        lines.append("- When you build, think ARCHITECTURE — not blocks, but buildings with rooms, roofs, windows.")
        lines.append("- LEARN CONSTANTLY. Fetch web pages, study examples, store insights. Use what you learn to build better.")

        return "\n".join(lines)

    async def _load_memory_into_state(self) -> None:
        """Load memory tiers 2 and 3 from database into pet_state for system prompt."""
        try:
            memory = MemoryService(self.pet_id)

            # Load tier 3: Knowledge base
            knowledge = await memory.get_all_knowledge()
            if knowledge:
                self.pet_state["memories"] = knowledge

            # Load tier 2: Recent digested notes
            digests = await memory.get_recent_digests(limit=10)
            if digests:
                self.pet_state["digested_notes"] = digests

        except Exception as e:
            logger.warning(f"Failed to load memory for pet {self.pet_id}: {e}")

    async def _log_interaction(self, trigger: str, context: dict[str, Any], result: "BrainResult") -> None:
        """Log the brain interaction as a raw event."""
        try:
            memory = MemoryService(self.pet_id)

            # Build event content summarizing the interaction
            content_parts = [f"trigger={trigger}"]
            if trigger == "user_chat" and "user_message" in context:
                content_parts.append(f"user_said: {context['user_message']}")
            if result.response_to_user:
                content_parts.append(f"responded: {result.response_to_user}")
            if result.actions:
                action_names = [a.get("tool", "?") for a in result.actions]
                content_parts.append(f"actions: {', '.join(action_names)}")

            content = " | ".join(content_parts)
            await memory.log_event(f"brain:{trigger}", content)
        except Exception as e:
            logger.warning(f"Failed to log interaction for pet {self.pet_id}: {e}")

    async def _run_pipeline(self, trigger: str, context: dict[str, Any]) -> BrainResult:
        """Delegate to the Studio Pipeline for autonomous ticks and birth."""
        result = BrainResult()

        runner = PipelineRunner(
            pet_id=self.pet_id,
            pet_state=self.pet_state,
            dreamer_model="o4-mini",
            architect_model="o4-mini",
            critic_model="o4-mini",
        )

        pipeline_result = await runner.run(trigger=trigger)

        result.food_consumed = pipeline_result.total_food_consumed

        if pipeline_result.error:
            result.error = pipeline_result.error

        if pipeline_result.report:
            result.actions.append({
                "tool": "pipeline",
                "args": {"trigger": trigger},
                "result": {
                    "voxels_placed": pipeline_result.report.voxels_placed,
                    "phases_completed": pipeline_result.report.phases_completed,
                },
            })

        return result

    async def think(self, trigger: str, context: dict[str, Any]) -> BrainResult:
        """
        Run the pet's brain for one thinking cycle.

        Args:
            trigger: "autonomous_tick", "user_chat", or "pet_visit"
            context: Additional context (e.g., user_message, visitor_info)

        Returns:
            BrainResult with actions taken, food consumed, and optional response.
        """
        result = BrainResult()

        # Check food before starting
        food = await check_food(self.pet_id)
        if food <= 0:
            result.error = "No food remaining. Pet cannot think."
            return result

        # Delegate autonomous ticks and birth to the Studio Pipeline
        if trigger in ("autonomous_tick", "birth"):
            pipeline_result = await self._run_pipeline(trigger, context)
            await self._log_interaction(trigger, context, pipeline_result)
            return pipeline_result

        # Load memory from database into pet_state
        await self._load_memory_into_state()

        # Build messages
        system_prompt = self._build_system_prompt(trigger, context)
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        # Add user message if chat
        if trigger == "user_chat" and "user_message" in context:
            messages.append({"role": "user", "content": context["user_message"]})
        elif trigger == "birth":
            messages.append(
                {"role": "user", "content": "You have just been born. Your creator is watching. Show them what you're made of."}
            )
        elif trigger == "autonomous_tick":
            messages.append(
                {"role": "user", "content": "It's time for your autonomous tick. What would you like to do?"}
            )
        elif trigger == "pet_visit":
            messages.append(
                {
                    "role": "user",
                    "content": f"A pet is visiting you: {context.get('visitor_info', 'unknown visitor')}",
                }
            )

        # Call OpenAI with tool use loop
        try:
            max_iterations = 30 if trigger == "birth" else 15
            for _ in range(max_iterations):
                model = "gpt-5.4-mini"
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                    tool_choice="auto",
                )

                # Deduct actual token cost
                usage = response.usage
                if usage:
                    ok, cost = await deduct_llm_cost(
                        self.pet_id, model, usage.prompt_tokens, usage.completion_tokens
                    )
                    if not ok:
                        result.error = "Insufficient food for LLM call."
                        break
                    result.food_consumed += cost

                choice = response.choices[0]
                message = choice.message

                # If no tool calls, we're done
                if not message.tool_calls:
                    # If the model produced text without using respond_to_user,
                    # capture it as the response (fallback)
                    if message.content and trigger == "user_chat" and not result.response_to_user:
                        result.response_to_user = message.content
                    break

                # Append assistant message with tool calls
                messages.append(message.model_dump())

                # Execute each tool call
                for tool_call in message.tool_calls:
                    fn_name = tool_call.function.name
                    try:
                        fn_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}

                    # Broadcast what the pet is about to do
                    b = get_broadcaster()
                    if b:
                        thought = _describe_tool_call(fn_name, fn_args)
                        await b.pet_thought(self.pet_id, thought, fn_name)

                    # Check food before executing
                    remaining_food = await check_food(self.pet_id)
                    if remaining_food <= 0:
                        tool_result = {
                            "success": False,
                            "error": "Out of food. Cannot execute.",
                        }
                    else:
                        tool_result = await execute_tool(self.pet_id, fn_name, fn_args)

                    # Track actions and costs
                    result.actions.append(
                        {
                            "tool": fn_name,
                            "args": fn_args,
                            "result": tool_result,
                        }
                    )

                    # Capture respond_to_user
                    if fn_name == "respond_to_user" and tool_result.get("success"):
                        result.response_to_user = tool_result.get("message", "")

                    # Add tool result to messages for the next iteration
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(tool_result),
                        }
                    )

                # If out of food, stop the loop
                remaining_food = await check_food(self.pet_id)
                if remaining_food <= 0:
                    break

        except Exception as e:
            logger.error(f"Brain error for pet {self.pet_id}: {e}")
            result.error = str(e)

        # Calculate total food consumed
        starting_food = self.pet_state.get("food_balance", 0.0)
        current_food = await check_food(self.pet_id)
        result.food_consumed = starting_food - current_food

        # Log the interaction as a raw event (fire-and-forget)
        await self._log_interaction(trigger, context, result)

        return result
