"""Redis-based distributed lock for pet operations."""

import logging
import os
import time

import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Lock TTLs in seconds
LOCK_TTLS = {
    "tick": 60,
    "chat": 300,
}


def _get_redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://localhost:6379")


class PetLock:
    """
    Simple Redis-based distributed lock to prevent conflicts
    between autonomous ticks and user chats.
    """

    def __init__(self, redis_client: redis.Redis | None = None):
        self._redis = redis_client

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(_get_redis_url(), decode_responses=True)
        return self._redis

    def _key(self, pet_id: str) -> str:
        return f"pet:lock:{pet_id}"

    async def acquire(self, pet_id: str, mode: str, timeout: int | None = None) -> bool:
        """
        Acquire lock for a pet.

        Args:
            pet_id: The pet ID to lock.
            mode: 'tick' or 'chat'.
            timeout: Override TTL in seconds. Defaults to mode-based TTL.

        Returns:
            True if lock acquired, False if already locked.
        """
        if timeout is None:
            timeout = LOCK_TTLS.get(mode, 60)

        r = await self._get_redis()
        key = self._key(pet_id)

        # Use SET NX (set if not exists) with expiry for atomic acquire
        value = f"{mode}:{int(time.time())}"
        acquired = await r.set(key, value, nx=True, ex=timeout)
        if acquired:
            logger.debug(f"Lock acquired for pet {pet_id} mode={mode} ttl={timeout}s")
            return True

        logger.debug(f"Lock NOT acquired for pet {pet_id} mode={mode} (already locked)")
        return False

    async def release(self, pet_id: str, mode: str) -> None:
        """
        Release the lock for a pet.

        Only releases if the current lock matches the given mode,
        preventing accidental release of another mode's lock.
        """
        r = await self._get_redis()
        key = self._key(pet_id)

        current = await r.get(key)
        if current and current.startswith(f"{mode}:"):
            await r.delete(key)
            logger.debug(f"Lock released for pet {pet_id} mode={mode}")
        else:
            logger.debug(
                f"Lock release skipped for pet {pet_id} mode={mode} "
                f"(current={current})"
            )

    async def is_locked(self, pet_id: str) -> str | None:
        """
        Check if a pet is locked.

        Returns:
            The lock mode ('tick' or 'chat') if locked, None otherwise.
        """
        r = await self._get_redis()
        key = self._key(pet_id)

        current = await r.get(key)
        if current:
            # Value format is "mode:timestamp"
            return current.split(":")[0]
        return None

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None
