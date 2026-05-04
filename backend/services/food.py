"""Food cost system for pet actions.

1 food = $1 USD. LLM costs are computed from actual token usage.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# In-memory pet food store (will be replaced with DB later)
_pet_food: dict[str, float] = {}

# Per-model pricing in dollars per token
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-5.4-mini": {
        "input": 0.15 / 1_000_000,   # $0.15 per 1M input tokens
        "output": 0.60 / 1_000_000,  # $0.60 per 1M output tokens
    },
    "gpt-4o": {
        "input": 2.50 / 1_000_000,
        "output": 10.00 / 1_000_000,
    },
    "gpt-4o-mini": {
        "input": 0.15 / 1_000_000,
        "output": 0.60 / 1_000_000,
    },
    "text-embedding-3-small": {
        "input": 0.02 / 1_000_000,   # $0.02 per 1M tokens
        "output": 0.0,               # embeddings have no output cost
    },
}

# Fixed costs for non-LLM game actions (in dollars)
ACTION_COSTS: dict[str, Optional[float]] = {
    "place_voxels": 0.0,
    "remove_voxels": 0.0,
    "set_animation": 0.0,
    "define_self": 0.0,
    "move_self": 0.0,
    "place_artifact": 0.0,
    "search_memories": 0.0,
    "write_knowledge": 0.0,
    "digest_memories": 0.0,
    "visit_pet": 0.0,
    "send_message": 0.0,
    "update_agenda": 0.0,
    "respond_to_user": 0.0,
}


def calculate_llm_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate actual dollar cost from token usage."""
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        logger.warning(f"No pricing for model '{model}', using gpt-5.4-mini rates")
        pricing = MODEL_PRICING["gpt-5.4-mini"]

    cost = (prompt_tokens * pricing["input"]) + (completion_tokens * pricing["output"])
    return cost


async def initialize_food(pet_id: str, balance: float) -> None:
    """Set initial food balance for a pet."""
    _pet_food[pet_id] = balance


async def check_food(pet_id: str) -> float:
    """Get remaining food balance."""
    return _pet_food.get(pet_id, 0.0)


async def deduct_food(pet_id: str, action: str, amount: Optional[float] = None) -> bool:
    """Deduct food for a game action. Returns False if insufficient."""
    if amount is not None:
        cost = amount
    else:
        cost = ACTION_COSTS.get(action, 0.0) or 0.0
    current = _pet_food.get(pet_id, 0.0)
    if current < cost:
        return False
    _pet_food[pet_id] = current - cost
    return True


async def deduct_llm_cost(pet_id: str, model: str, prompt_tokens: int, completion_tokens: int) -> tuple[bool, float]:
    """
    Deduct actual LLM cost based on token usage.
    Returns (success, cost_deducted).
    """
    cost = calculate_llm_cost(model, prompt_tokens, completion_tokens)
    current = _pet_food.get(pet_id, 0.0)
    if current < cost:
        return False, 0.0
    _pet_food[pet_id] = current - cost
    logger.info(
        f"Pet {pet_id} LLM cost: ${cost:.6f} "
        f"({prompt_tokens} in / {completion_tokens} out on {model}), "
        f"balance: ${_pet_food[pet_id]:.6f}"
    )
    return True, cost
