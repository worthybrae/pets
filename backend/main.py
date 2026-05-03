from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.api.pets import router as pets_router
from backend.api.websocket import router as ws_router

load_dotenv()

app = FastAPI(
    title="AI Pet Voxel World",
    description="An autonomous AI pet that lives in a 3D voxel world",
    version="0.1.0",
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
