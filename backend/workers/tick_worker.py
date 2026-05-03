"""
Tick Worker — standalone process that polls Redis for due pet ticks and processes them.

Run with: python -m backend.workers.tick_worker

Can run multiple instances for horizontal scaling.
"""

import asyncio
import logging
import os
import signal
import sys

from dotenv import load_dotenv

# Ensure the project root is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

load_dotenv()

from backend.services.scheduler import PetScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("tick_worker")

# How long to sleep when no jobs are due (seconds)
POLL_INTERVAL = 5.0

# Graceful shutdown flag
_shutdown = False


def _handle_signal(signum, frame):
    """Handle shutdown signals gracefully."""
    global _shutdown
    logger.info(f"Received signal {signum}, shutting down...")
    _shutdown = True


async def main():
    """Main worker loop."""
    global _shutdown

    # Register signal handlers
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info("Tick worker starting...")
    scheduler = PetScheduler()
    await scheduler.start()

    logger.info("Tick worker running. Polling for due ticks...")

    try:
        while not _shutdown:
            try:
                # Get all pets whose tick is due
                due_pets = await scheduler.get_due_pets()

                if due_pets:
                    logger.info(f"Found {len(due_pets)} due pet(s): {due_pets}")

                    # Process each due pet
                    for pet_id in due_pets:
                        if _shutdown:
                            break

                        try:
                            logger.info(f"Processing tick for pet {pet_id}")
                            result = await scheduler.process_tick(pet_id)

                            if result:
                                logger.info(
                                    f"Tick complete for {pet_id}: "
                                    f"{len(result.actions)} actions, "
                                    f"{result.food_consumed:.4f} food consumed"
                                )
                            else:
                                logger.info(f"Tick skipped for {pet_id} (locked/no food)")

                        except Exception as e:
                            logger.error(f"Error processing tick for {pet_id}: {e}", exc_info=True)

                else:
                    # No due jobs, sleep briefly
                    await asyncio.sleep(POLL_INTERVAL)

            except Exception as e:
                logger.error(f"Worker loop error: {e}", exc_info=True)
                await asyncio.sleep(POLL_INTERVAL)

    finally:
        logger.info("Tick worker shutting down...")
        await scheduler.stop()
        logger.info("Tick worker stopped.")


if __name__ == "__main__":
    asyncio.run(main())
