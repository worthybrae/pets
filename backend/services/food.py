"""Food cost system for pet actions."""

from typing import Optional

# In-memory pet food store (will be replaced with DB later)
_pet_food: dict[str, float] = {}

FOOD_COSTS: dict[str, Optional[float]] = {
    "place_voxels": 0.01,
    "remove_voxels": 0.01,
    "set_animation": 0.01,
    "define_self": 0.01,
    "move_self": 0.005,
    "place_artifact": 0.03,
    "search_memories": 0.01,
    "search_web": 0.05,
    "execute_code": 0.10,
    "write_knowledge": 0.01,
    "digest_memories": 0.03,
    "visit_pet": None,  # varies by distance
    "send_message": 0.01,
    "update_agenda": 0.0,
    "respond_to_user": 0.03,
    "brain_call": 0.02,  # base cost per OpenAI API call
}


def _get_food_cost(action: str, amount: Optional[float] = None) -> float:
    """Get the food cost for an action."""
    if amount is not None:
        return amount
    cost = FOOD_COSTS.get(action)
    if cost is None:
        return 0.01  # default cost for unknown or variable actions
    return cost


async def initialize_food(pet_id: str, balance: float) -> None:
    """Set initial food balance for a pet."""
    _pet_food[pet_id] = balance


async def check_food(pet_id: str) -> float:
    """Get remaining food balance."""
    return _pet_food.get(pet_id, 0.0)


async def deduct_food(pet_id: str, action: str, amount: Optional[float] = None) -> bool:
    """Deduct food for an action. Returns False if insufficient."""
    cost = _get_food_cost(action, amount)
    current = _pet_food.get(pet_id, 0.0)
    if current < cost:
        return False
    _pet_food[pet_id] = current - cost
    return True
