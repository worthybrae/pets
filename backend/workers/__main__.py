"""Allow running with: python -m backend.workers"""

import asyncio
from backend.workers.tick_worker import main

if __name__ == "__main__":
    asyncio.run(main())
