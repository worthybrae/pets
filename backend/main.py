import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.api.pets import router as pets_router
from backend.api.websocket import router as ws_router
from backend.services.scheduler import PetScheduler

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

# Global scheduler instance (shared with API routes via import)
_scheduler = PetScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Startup
    logger.info("Starting PetScheduler...")
    await _scheduler.start()
    logger.info(
        "PetScheduler initialized. "
        "Note: Run 'python -m backend.workers.tick_worker' separately "
        "to process autonomous ticks."
    )
    yield
    # Shutdown
    logger.info("Stopping PetScheduler...")
    await _scheduler.stop()
    logger.info("PetScheduler stopped.")


app = FastAPI(
    title="AI Pet Voxel World",
    description="An autonomous AI pet that lives in a 3D voxel world",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pets_router, prefix="/api")
app.include_router(ws_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "AI Pet Voxel World API", "version": "0.1.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}
