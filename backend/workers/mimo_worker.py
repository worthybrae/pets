"""Run the active survival life independently of all browsers.

Run with: python -m backend.workers.mimo_worker
Keep exactly one worker running against a persistent MIMO_DATA_DIR. Each tick brings the
active life up to now (vitals, the interim sleep rule, death). The retired legacy world at
MIMO_DB_PATH is no longer ticked; live_mimo.run_tick stays only for reading old worlds.
"""

from __future__ import annotations

import logging
import os
import signal
import sqlite3
import time

from dotenv import load_dotenv

from backend.survival.registry import LifeRegistry, data_dir
from backend.survival.tick import tick_life
from backend.survival.world import WorldMissing

logger = logging.getLogger("mimo_worker")
stopping = False


def stop(_signum, _frame):
    global stopping
    stopping = True


def tick_seconds() -> float:
    try:
        seconds = float(os.environ.get("MIMO_TICK_SECONDS", "1"))
    except ValueError:
        return 1.0
    return seconds if seconds > 0 else 1.0


def run_once(registry: LifeRegistry, previous: str | None, timestamp: float | None = None) -> str:
    """Tick the active life once. Logs a line when the pet's status changes and returns it."""
    state = tick_life(registry, timestamp)
    if state is None:
        line = "No pet is alive. Waiting for the egg to hatch."
    elif state["died_at"] is not None:
        line = f"{state['name']} died of {state['cause']}."
    else:
        line = f"{state['name']} is {state['status']}: {state['last_thought']}"
    if line != previous:
        logger.info(line)
    return line


def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    delay = tick_seconds()
    logger.info("Survival worker started, data dir %s, one tick every %.1f s", data_dir(), delay)
    registry: LifeRegistry | None = None
    previous: str | None = None
    while not stopping:
        try:
            if registry is None:
                registry = LifeRegistry()
            previous = run_once(registry, previous)
        except (WorldMissing, OSError, sqlite3.Error):
            logger.exception("Survival data is unavailable; waiting")
            registry = None
        except Exception:
            logger.exception("Survival tick failed")
        time.sleep(delay)
    logger.info("Survival worker stopped")


if __name__ == "__main__":
    main()
