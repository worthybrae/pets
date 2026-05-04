"""Pet scheduler — wakes pets at their scheduled agenda times.

Instead of periodic ticks at computed intervals, pets plan their day
with specific times. The scheduler sleeps until the next task, wakes
the pet, checks if food changed (from ad-hoc chat), revises if needed,
then executes the task.
"""

import logging
import os
import time
from typing import Any

import redis.asyncio as redis

from backend.services.brain import PetBrain, BrainResult
from backend.services.food import check_food
from backend.services.lock import PetLock
from backend.services.agenda import (
    generate_daily_agenda,
    get_current_agenda,
    get_next_task,
    get_next_task_time,
    mark_next_task_completed,
    revise_remaining_agenda,
    should_revise,
)

logger = logging.getLogger(__name__)

# Redis keys
SCHEDULE_KEY = "pet:schedule"  # Sorted set: score=next_task_ts, member=pet_id
STATUS_PREFIX = "pet:scheduler:status:"  # Hash per pet with scheduling metadata


def _get_redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://localhost:6379")


class PetScheduler:
    """Manages agenda-based scheduling for all active pets."""

    def __init__(self, redis_client: redis.Redis | None = None):
        self._redis = redis_client
        self._lock = PetLock(redis_client)
        self._running = False

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(_get_redis_url(), decode_responses=True)
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
        Schedule a pet's next agenda task.

        Reads the pet's agenda, finds the next uncompleted task,
        and schedules a wake at that task's time.
        """
        if food_balance <= 0:
            logger.info(f"Pet {pet_id} has no food, not scheduling.")
            await self.unschedule_pet(pet_id)
            return

        agenda = await get_current_agenda(pet_id)
        next_time = get_next_task_time(agenda)

        if next_time is None:
            logger.info(f"Pet {pet_id} has no remaining tasks, sleeping until next agenda.")
            await self.unschedule_pet(pet_id)
            return

        # If the task time is in the past, schedule for 30s from now
        now = time.time()
        if next_time <= now:
            next_time = now + 30

        r = await self._get_redis()
        await r.zadd(SCHEDULE_KEY, {pet_id: next_time})

        next_task = get_next_task(agenda)
        task_desc = next_task.get("task", "?") if next_task else "?"
        wait_minutes = (next_time - now) / 60

        # Store status metadata
        status_key = f"{STATUS_PREFIX}{pet_id}"
        await r.hset(status_key, mapping={
            "next_tick": str(next_time),
            "next_task": task_desc,
            "food_balance": str(food_balance),
            "scheduled_at": str(now),
            "status": "sleeping",
        })

        logger.info(
            f"Pet {pet_id} sleeping until '{task_desc}' "
            f"(in {wait_minutes:.1f}min)"
        )

    async def unschedule_pet(self, pet_id: str) -> None:
        """Remove a pet from the schedule."""
        r = await self._get_redis()
        await r.zrem(SCHEDULE_KEY, pet_id)

        status_key = f"{STATUS_PREFIX}{pet_id}"
        await r.hset(status_key, mapping={
            "status": "unscheduled",
            "unscheduled_at": str(time.time()),
        })

        logger.info(f"Unscheduled pet {pet_id}")

    async def get_due_pets(self) -> list[str]:
        """Get all pets whose next task is due (score <= now)."""
        r = await self._get_redis()
        now = time.time()
        due = await r.zrangebyscore(SCHEDULE_KEY, "-inf", str(now))
        return due

    async def process_tick(self, pet_id: str, pet_state: dict[str, Any] | None = None) -> BrainResult | None:
        """
        Execute a scheduled agenda task for a pet.

        Wake-check-revise flow:
        1. Check lock (skip if user is chatting)
        2. Check food (unschedule if empty)
        3. Check if food balance changed → revise agenda if needed
        4. Get current task from agenda
        5. Execute task via brain.think()
        6. Mark task completed
        7. Schedule next task
        """
        r = await self._get_redis()

        # 1. Check lock
        current_lock = await self._lock.is_locked(pet_id)
        if current_lock is not None:
            logger.info(f"Pet {pet_id} is locked ({current_lock}), rescheduling +5min.")
            next_tick = time.time() + 300
            await r.zadd(SCHEDULE_KEY, {pet_id: next_tick})
            return None

        # 2. Check food
        food_balance = await check_food(pet_id)
        if food_balance <= 0:
            logger.info(f"Pet {pet_id} has no food, unscheduling.")
            await self.unschedule_pet(pet_id)
            return None

        # 3. Acquire tick lock
        acquired = await self._lock.acquire(pet_id, mode="tick", timeout=60)
        if not acquired:
            logger.info(f"Could not acquire tick lock for pet {pet_id}, rescheduling.")
            next_tick = time.time() + 300
            await r.zadd(SCHEDULE_KEY, {pet_id: next_tick})
            return None

        try:
            # 4. Get agenda and check if food changed
            agenda = await get_current_agenda(pet_id)

            if should_revise(agenda, food_balance):
                old_food = agenda.get("food_at_last_check", 0)
                diff = food_balance - old_food
                direction = "gained" if diff > 0 else "lost"
                logger.info(
                    f"Pet {pet_id} {direction} ${abs(diff):.6f} since last check, "
                    f"revising agenda"
                )
                await revise_remaining_agenda(pet_id, pet_state)
                # Re-fetch the revised agenda
                agenda = await get_current_agenda(pet_id)

            # 5. Get current task
            current_task = get_next_task(agenda)
            if current_task is None:
                logger.info(f"Pet {pet_id} has no remaining tasks.")
                await self.unschedule_pet(pet_id)
                return None

            # Build pet state if not provided
            if pet_state is None:
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

            # 6. Execute task via brain
            brain = PetBrain(pet_id, pet_state)
            result = await brain.think(
                trigger="autonomous_tick",
                context={
                    "agenda": agenda.get("tasks", []),
                    "current_task": current_task,
                },
            )

            # 7. Mark task completed
            await mark_next_task_completed(pet_id)

            # 8. Schedule next task
            remaining_food = await check_food(pet_id)
            await self.schedule_pet(pet_id, remaining_food)

            # Update status
            status_key = f"{STATUS_PREFIX}{pet_id}"
            await r.hset(status_key, mapping={
                "last_tick_at": str(time.time()),
                "last_task": current_task.get("task", "?"),
                "last_tick_food_consumed": str(result.food_consumed),
                "last_tick_error": result.error or "",
            })

            logger.info(
                f"Pet {pet_id} completed '{current_task.get('task', '?')}': "
                f"food_consumed=${result.food_consumed:.6f}, "
                f"remaining=${remaining_food:.6f}"
            )

            return result

        except Exception as e:
            logger.error(f"Error processing task for pet {pet_id}: {e}")
            remaining_food = await check_food(pet_id)
            if remaining_food > 0:
                await self.schedule_pet(pet_id, remaining_food)
            return None

        finally:
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
            "next_tick": float(status_data.get("next_tick", 0)) if score else None,
            "next_task": status_data.get("next_task"),
            "food_balance": float(status_data.get("food_balance", 0)),
            "last_tick_at": float(status_data.get("last_tick_at", 0)) or None,
            "last_task": status_data.get("last_task"),
            "last_tick_food_consumed": float(status_data.get("last_tick_food_consumed", 0)),
            "last_tick_error": status_data.get("last_tick_error") or None,
        }
