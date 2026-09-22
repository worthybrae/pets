"""Run Mimo's persistent life loop independently of all browsers.

Run with: python -m backend.workers.mimo_worker
Keep exactly one worker process running against a persistent MIMO_DB_PATH.
"""

import logging
import signal
import time

from dotenv import load_dotenv

from backend.services.live_mimo import MimoStore, run_tick

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mimo_worker")
stopping = False


def stop(_signum, _frame):
    global stopping
    stopping = True


def main():
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    store = MimoStore()
    logger.info("Mimo worker started, database: %s", store.path)
    while not stopping:
        try:
            store.heartbeat()
            if run_tick(store):
                state = store.snapshot()
                logger.info("Mimo %s: %s", state["status"], state["last_thought"])
        except Exception:
            logger.exception("Mimo worker tick failed")
        time.sleep(5)
    logger.info("Mimo worker stopped")


if __name__ == "__main__":
    main()
