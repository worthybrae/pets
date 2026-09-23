"""Run the active survival life independently of all browsers.

Run with: python -m backend.workers.mimo_worker
Keep exactly one worker running against a persistent MIMO_DATA_DIR. Each tick brings the
active life up to now (timed actions, vitals, death) with the brain; then the Chooser answers a
pending purpose trigger outside the tick's transaction (backend.survival.choosing). The retired
legacy world at MIMO_DB_PATH is no longer ticked; live_mimo.run_tick stays only for reading old
worlds.
"""

from __future__ import annotations

import logging
import math
import os
import signal
import sqlite3
import time

from dotenv import load_dotenv

from backend.survival.brain import BRAIN
from backend.survival.choosing import Chooser
from backend.survival.registry import LifeRegistry, data_dir
from backend.survival.tick import RESTING, Mind, tick_life
from backend.survival.world import WorldMissing

logger = logging.getLogger("mimo_worker")
stopping = False

# What runs the pet: reflexes, purposes and the planner.
WORKER_MIND = BRAIN


def stop(_signum, _frame):
    global stopping
    stopping = True


def tick_seconds() -> float:
    try:
        seconds = float(os.environ.get("MIMO_TICK_SECONDS", "1"))
    except ValueError:
        return 1.0
    return seconds if math.isfinite(seconds) and seconds > 0 else 1.0


def should_log_data_error(error: BaseException, last: str | None) -> tuple[bool, str]:
    """Whether this data-unavailable error is worth a fresh traceback: only the first time
    it's seen, not every second it keeps happening. Returns the key to remember next time."""
    key = f"{type(error).__name__}: {error}"
    return key != last, key


def run_once(registry: LifeRegistry, previous: str | None, timestamp: float | None = None,
             mind: Mind = RESTING, chooser: Chooser | None = None) -> str:
    """Tick the active life once, then let the chooser answer a pending purpose trigger. Logs a
    line when the pet's status changes and returns it.

    `mind` defaults to the plain sleep rule and `chooser` to none; `main` passes WORKER_MIND and
    a Chooser.
    """
    state = tick_life(registry, timestamp, mind=mind)
    if chooser is not None and state is not None and state["died_at"] is None:
        chooser.poll(registry, timestamp)
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
    last_data_error: str | None = None
    chooser = Chooser()
    while not stopping:
        try:
            if registry is None:
                registry = LifeRegistry()
            previous = run_once(registry, previous, mind=WORKER_MIND, chooser=chooser)
            last_data_error = None
        except (WorldMissing, OSError, sqlite3.Error) as error:
            log_it, last_data_error = should_log_data_error(error, last_data_error)
            if log_it:
                logger.exception("Survival data is unavailable; waiting")
            registry = None
        except Exception:
            logger.exception("Survival tick failed")
        time.sleep(delay)
    chooser.close()
    logger.info("Survival worker stopped")


if __name__ == "__main__":
    main()
