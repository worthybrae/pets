"""Pet scheduler — manages autonomous tick scheduling for all active pets."""

import logging
import os
import time
from typing import Any

import redis.asyncio as redis

from backend.services.brain import PetBrain, BrainResult
from backend.services.food import check_food
from backend.services.lock import PetLock
from backend.services.agenda import generate_daily_agenda, get_current_agenda

logger = logging.getLogger(__name__)

# Redis keys
SCHEDULE_KEY = "pet:schedule"  # Sorted set: score=next_tick_ts, member=pet_id
STATUS_PREFIX = "pet:scheduler:status:"  # Hash per pet with scheduling metadata

# Interval bounds in minutes
MIN_INTERVAL_MINUTES = 10
MAX_INTERVAL_MINUTES = 30
MAX_FOOD_FOR_SCALING = 100.0  # Food balance at which interval is at minimum


def compute_tick_interval(food_balance: float) -> float:
    """
    Compute tick interval in minutes based on food balance.
    More food = shorter interval (min 10 min, max 30 min).
    No food = don't schedule (returns 0).
    """
    if food_balance <= 0:
        return 0.0

    ratio = min(food_balance / MAX_FOOD_FOR_SCALING, 1.0)
    # interval = 30 - ratio * 20 (clamped to [10, 30])
    interval = MAX_INTERVAL_MINUTES - ratio * (MAX_INTERVAL_MINUTES - MIN_INTERVAL_MINUTES)
    return max(MIN_INTERVAL_MINUTES, min(MAX_INTERVAL_MINUTES, interval))


def _get_redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://localhost:6379")


class PetScheduler:
    """Manages autonomous tick scheduling for all active pets."""

    def __init__(self, redis_client: redis.Redis | None = None):
        self._redis = redis_client
        self._lock = PetLock(redis_client)
        self._running = False

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(_get_redis_url(), decode_responses=True)
            # Share the redis client with the lock manager
            self._lock = PetLock(self._redis)
        return self._redis

    async def start(self) -> None:
        """Start the scheduler (mark as running)."""
        self._running = True
        logger.info("PetScheduler started.")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        logger.info("PetScheduler stopped.")
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    async def schedule_pet(self, pet_id: str, food_balance: float) -> None:
        """
        Schedule a pet's next tick based on its food balance.

        More food = shorter interval (min 10 min, max 30 min).
        No food = don't schedule.
        """
        interval = compute_tick_interval(food_balance)
        if interval <= 0:
            logger.info(f"Pet {pet_id} has no food, not scheduling.")
            await self.unschedule_pet(pet_id)
            return

        r = await self._get_redis()
        next_tick = time.time() + (interval * 60)

        # Add to sorted set (score = next tick timestamp)
        await r.zadd(SCHEDULE_KEY, {pet_id: next_tick})

        # Store status metadata
        status_key = f"{STATUS_PREFIX}{pet_id}"
        await r.hset(status_key, mapping={
            "interval_minutes": str(interval),
            "next_tick": str(next_tick),
            "food_balance": str(food_balance),
            "scheduled_at": str(time.time()),
            "status": "scheduled",
        })

        logger.info(
            f"Scheduled pet {pet_id}: interval={interval:.1f}min, "
            f"next_tick in {interval:.1f}min"
        )

    async def unschedule_pet(self, pet_id: str) -> None:
        """Remove a pet from the schedule (e.g., when food runs out)."""
        r = await self._get_redis()
        await r.zrem(SCHEDULE_KEY, pet_id)

        status_key = f"{STATUS_PREFIX}{pet_id}"
        await r.hset(status_key, mapping={
            "status": "unscheduled",
            "unscheduled_at": str(time.time()),
        })

        logger.info(f"Unscheduled pet {pet_id}")

    async def get_due_pets(self) -> list[str]:
        """Get all pets whose tick is due (score <= now)."""
        r = await self._get_redis()
        now = time.time()
        # Get all members with score <= current timestamp
        due = await r.zrangebyscore(SCHEDULE_KEY, "-inf", str(now))
        return due

    async def process_tick(self, pet_id: str, pet_state: dict[str, Any] | None = None) -> BrainResult | None:
        """
        Execute one autonomous tick for a pet.

        Steps:
        1. Check if pet is currently chatting (lock check) — skip if so
        2. Check food balance — skip if empty
        3. Acquire tick lock
        4. Call brain.think(trigger="autonomous_tick")
        5. Schedule next tick based on remaining food
        6. Release lock and log results
        """
        r = await self._get_redis()

        # 1. Check if currently locked (e.g., user is chatting)
        current_lock = await self._lock.is_locked(pet_id)
        if current_lock is not None:
            logger.info(f"Pet {pet_id} is locked ({current_lock}), skipping tick.")
            # Reschedule for later (5 minutes)
            next_tick = time.time() + 300
            await r.zadd(SCHEDULE_KEY, {pet_id: next_tick})
            return None

        # 2. Check food balance
        food_balance = await check_food(pet_id)
        if food_balance <= 0:
            logger.info(f"Pet {pet_id} has no food, unscheduling.")
            await self.unschedule_pet(pet_id)
            return None

        # 3. Acquire tick lock
        acquired = await self._lock.acquire(pet_id, mode="tick", timeout=60)
        if not acquired:
            logger.info(f"Could not acquire tick lock for pet {pet_id}, skipping.")
            # Reschedule for later
            next_tick = time.time() + 300
            await r.zadd(SCHEDULE_KEY, {pet_id: next_tick})
            return None

        try:
            # Build pet state if not provided
            if pet_state is None:
                # Minimal state — in production this would come from DB
                agenda = await get_current_agenda(pet_id)
                pet_state = {
                    "name": f"Pet-{pet_id[:8]}",
                    "seed_curiosity": "the unknown",
                    "created_at": "2024-01-01T00:00:00Z",
                    "food_balance": food_balance,
                    "position": {"x": 0, "y": 0, "z": 0},
                    "memories": [],
                    "digested_notes": [],
                    "agenda": agenda.get("tasks", []),
                }

            # 4. Call brain.think
            brain = PetBrain(pet_id, pet_state)
            result = await brain.think(
                trigger="autonomous_tick",
                context={"agenda": pet_state.get("agenda", [])},
            )

            # 5. Schedule next tick based on remaining food
            remaining_food = await check_food(pet_id)
            await self.schedule_pet(pet_id, remaining_food)

            # Update status with tick result
            status_key = f"{STATUS_PREFIX}{pet_id}"
            await r.hset(status_key, mapping={
                "last_tick_at": str(time.time()),
                "last_tick_actions": str(len(result.actions)),
                "last_tick_food_consumed": str(result.food_consumed),
                "last_tick_error": result.error or "",
            })

            logger.info(
                f"Tick processed for pet {pet_id}: "
                f"actions={len(result.actions)}, "
                f"food_consumed={result.food_consumed:.4f}, "
                f"remaining_food={remaining_food:.4f}"
            )

            return result

        except Exception as e:
            logger.error(f"Error processing tick for pet {pet_id}: {e}")
            # Still reschedule even on error
            remaining_food = await check_food(pet_id)
            if remaining_food > 0:
                await self.schedule_pet(pet_id, remaining_food)
            return None

        finally:
            # 6. Release lock
            await self._lock.release(pet_id, mode="tick")

    async def get_status(self, pet_id: str) -> dict:
        """Get scheduling status for a pet."""
        r = await self._get_redis()
        status_key = f"{STATUS_PREFIX}{pet_id}"

        status_data = await r.hgetall(status_key)
        if not status_data:
            return {
                "pet_id": pet_id,
                "status": "unknown",
                "scheduled": False,
            }

        # Check if still in the sorted set
        score = await r.zscore(SCHEDULE_KEY, pet_id)
        is_scheduled = score is not None

        return {
            "pet_id": pet_id,
            "status": status_data.get("status", "unknown"),
            "scheduled": is_scheduled,
            "interval_minutes": float(status_data.get("interval_minutes", 0)),
            "next_tick": float(status_data.get("next_tick", 0)) if score else None,
            "food_balance": float(status_data.get("food_balance", 0)),
            "last_tick_at": float(status_data.get("last_tick_at", 0)) or None,
            "last_tick_actions": int(status_data.get("last_tick_actions", 0)),
            "last_tick_food_consumed": float(status_data.get("last_tick_food_consumed", 0)),
            "last_tick_error": status_data.get("last_tick_error") or None,
        }
