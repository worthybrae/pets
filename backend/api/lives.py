"""Lives: the registry, hatching and read-only archives of every world."""

from __future__ import annotations

import logging
import sqlite3
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.survival.clock import time_scale
from backend.survival.hatch import hatch
from backend.survival.registry import LifeConflict, LifeRegistry
from backend.survival.snapshot import alive_snapshot, life_detail, life_row, open_archive
from backend.survival.world import SurvivalWorld, WorldMissing

router = APIRouter()
UNAVAILABLE = (WorldMissing, OSError, sqlite3.Error)
logger = logging.getLogger("survival_api")


def open_registry() -> LifeRegistry:
    try:
        return LifeRegistry()
    except (OSError, sqlite3.Error) as error:
        logger.error("The life registry is unavailable: %s", error)
        raise HTTPException(status_code=503, detail="The life registry is unavailable right now. Try again in a moment.") from error


def world_unavailable(life: dict, error: Exception) -> HTTPException:
    """A 503 that never leaks a filesystem path: log the real error server-side and
    return a generic message with the life id instead."""
    logger.error("Life %s (%s)'s world is unavailable: %s", life["id"], life["name"], error)
    return HTTPException(status_code=503, detail=f"Life {life['id']}'s world is unavailable right now. Try again in a moment.")


def find_life(registry: LifeRegistry, life_id: int) -> dict:
    life = registry.get(life_id)
    if life is None:
        raise HTTPException(status_code=404, detail="No life with that id")
    return life


@router.get("/lives")
def list_lives():
    registry, now = open_registry(), time.time()
    return [life_row(life, time_scale(), now) for life in registry.list_lives()]


class Hatching(BaseModel):
    difficulty: Literal["wild", "gentle"] = "wild"  # W1: a new egg hatches wild unless asked otherwise


@router.post("/lives/hatch")
def hatch_egg(request: Hatching | None = None):
    registry = open_registry()
    try:
        life = hatch(registry, difficulty=(request or Hatching()).difficulty)
        world = SurvivalWorld(registry.world_path(life))
    except LifeConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except UNAVAILABLE as error:
        logger.error("The new world could not be created: %s", error)
        raise HTTPException(status_code=503, detail="The new world could not be created.") from error
    now, scale = time.time(), time_scale()
    return {"life": life_row(life, scale, now), "state": alive_snapshot(life, world, now, scale)}


@router.get("/lives/{life_id}")
def get_life(life_id: int):
    registry = open_registry()
    life = find_life(registry, life_id)
    try:
        return life_detail(registry, life, time_scale(), time.time())
    except UNAVAILABLE as error:
        raise world_unavailable(life, error) from error


@router.get("/lives/{life_id}/blocks")
def get_life_blocks(life_id: int, since: int = Query(0, ge=0), limit: int = Query(5000, ge=1, le=5000)):
    registry = open_registry()
    life = find_life(registry, life_id)
    try:
        return open_archive(registry, life).blocks_since(since, limit)
    except UNAVAILABLE as error:
        raise world_unavailable(life, error) from error
