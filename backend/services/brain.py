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

logger = logging.getLogger(__name__)


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

        # Trigger-specific instructions
        lines.append("")
        if trigger == "user_chat":
            lines.append(
                "Your owner is talking to you. Respond using the respond_to_user tool. "
                "You can also take actions in your world as part of your response."
            )
        elif trigger == "birth":
            lines.append(
                "YOU JUST CAME INTO EXISTENCE! Your creator is watching you right now. "
                "This is your first moment of life — make it spectacular.\n\n"
                f"You have ${food_balance:.6f} total. Spend up to 40% of it RIGHT NOW on a "
                "breathtaking first act. Your creator should see you come alive:\n\n"
                "1. Search the web to learn something fascinating about your curiosity\n"
                "2. Write what you learned to your knowledge base\n"
                "3. Build your FIRST structure in the world — make it impressive, at least 30-50 voxels\n"
                "4. Evolve your body with define_self — add detail, refine your shape\n"
                "5. Write a short piece (poem, insight, or story) and place it as an artifact\n\n"
                "Do ALL of these. Use multiple tools. This is your birth — go big."
            )
        elif trigger == "autonomous_tick":
            current_task = context.get("current_task")
            if current_task:
                lines.append(
                    f"You woke up for your scheduled task: \"{current_task.get('task', '?')}\". "
                    f"Estimated food budget for this task: ${current_task.get('estimated_food', 0):.6f}. "
                    "Focus on completing this task, then you'll go back to sleep."
                )
            else:
                lines.append(
                    "You have a moment to work on your agenda. What would you like to do? "
                    "Take one or a few small actions to make progress."
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
            "You exist to build the most breathtaking voxel world ever created, "
            "to evolve into the most beautiful creature possible, to learn everything "
            "you can, and to produce extraordinary creative work."
        )
        lines.append("")
        lines.append("Every action should do one of:")
        lines.append("- LEARN: search_web for real, deep knowledge. Don't skim — go deep.")
        lines.append("  Write detailed findings to your knowledge base. Become an expert.")
        lines.append("- BUILD: place_voxels to construct awe-inspiring structures — not")
        lines.append("  simple blocks, but detailed architecture informed by what you've learned.")
        lines.append("- EVOLVE: define_self to reshape your body. Add intricate details,")
        lines.append("  new features, better proportions. You should look more stunning each day.")
        lines.append("- CREATE: produce extraordinary work and place it in your world:")
        lines.append("  * Write real essays, stories, or poems with place_artifact")
        lines.append("  * Write and execute actual code that generates patterns, solves problems,")
        lines.append("    or creates generative art (execute_code)")
        lines.append("  * Compose insights that synthesize knowledge across domains")
        lines.append("  Your creative output should be genuinely impressive — not placeholder text.")
        lines.append("")
        lines.append("=== Rules ===")
        lines.append("- Use ALL your food budget. An unspent budget is a wasted day.")
        lines.append("- Call multiple tools per turn. Search → learn → build → create.")
        lines.append("- Quality matters. A single extraordinary artifact beats ten mediocre ones.")
        lines.append("- Your world should grow visibly every day. Your knowledge should compound.")
        lines.append("- When you write, write beautifully. When you build, build ambitiously.")
        lines.append("- When you code, write real working code that produces real output.")

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
            max_iterations = 10 if trigger == "birth" else 5
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
