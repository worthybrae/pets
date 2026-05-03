"""Pet Brain service — the AI core that drives each pet using OpenAI function calling."""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from openai import AsyncOpenAI

from backend.services.food import check_food, deduct_food
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

        # Core identity
        lines = [
            f"You are {name}, a pixel creature living in a voxel world.",
            f"You started as a single white voxel in a void. You are {age_days} days old.",
        ]

        # Seed curiosity (especially prominent when young)
        if age_days < 7:
            lines.append(
                f"You were born with a deep fascination for {seed}. "
                "This curiosity drives everything you do."
            )
        else:
            lines.append(f"You were born with a fascination for {seed}.")

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
        lines.append(f"Food remaining: {food_balance:.2f}")
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
        elif trigger == "autonomous_tick":
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

        # Rules
        lines.append("")
        lines.append("=== Rules ===")
        lines.append("- Every action costs food. Be mindful of your budget.")
        lines.append("- You can call multiple tools in one turn.")
        lines.append("- If you run out of food, you will stop being able to act.")
        lines.append("- Build things in your world, explore your curiosity, grow.")

        return "\n".join(lines)

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

        # Deduct base brain call cost
        has_food = await deduct_food(self.pet_id, "brain_call")
        if not has_food:
            result.error = "Insufficient food for brain call."
            return result
        result.food_consumed += 0.02

        # Build messages
        system_prompt = self._build_system_prompt(trigger, context)
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        # Add user message if chat
        if trigger == "user_chat" and "user_message" in context:
            messages.append({"role": "user", "content": context["user_message"]})
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
            max_iterations = 5  # Prevent infinite tool-calling loops
            for _ in range(max_iterations):
                response = await self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                    tool_choice="auto",
                )

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

        return result
