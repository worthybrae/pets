"""The active survival life: its state, block changes and the owner's interactions."""

from __future__ import annotations

import random
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.api.lives import UNAVAILABLE, open_registry, world_unavailable
from backend.survival.care import CareRefused, give_care
from backend.survival.clock import time_scale
from backend.survival.registry import LifeRegistry
from backend.survival.snapshot import alive_snapshot, life_row, life_summary
from backend.survival.world import LifeOver, SurvivalWorld, WorldBehind

router = APIRouter()


class OwnerAction(BaseModel):
    action: str
    item: str


class CareRequest(BaseModel):
    kind: Literal["snack", "bandage"]


def active_world(registry: LifeRegistry, life: dict | None = None, read_only: bool = False) -> tuple[dict, SurvivalWorld]:
    """The active life and its world. Pass an already-fetched `life` to avoid asking the
    registry twice (a life could die between two separate lookups in the same request)."""
    if life is None:
        life = registry.active_life()
    if life is None:
        raise HTTPException(status_code=409, detail="No pet is alive. Hatch the egg first.")
    try:
        return life, SurvivalWorld(registry.world_path(life), read_only=read_only)
    except UNAVAILABLE as error:
        raise world_unavailable(life, error) from error


@router.get("/mimo")
def get_mimo():
    registry, now, scale = open_registry(), time.time(), time_scale()
    life = registry.active_life()
    if life is None:
        last = registry.last_life()
        summary = None
        if last:
            try:
                summary = life_summary(registry, last, scale, now)
            except UNAVAILABLE:
                # The egg screen must never dead-end on a broken last life: show it without
                # its notable events rather than a 503.
                summary = life_row(last, scale, now)
        return {"phase": "egg", "egg": registry.pending_egg(random.Random(), now),
                "last_life": summary, "server_time": now}
    life, world = active_world(registry, life=life, read_only=True)
    return alive_snapshot(life, world, now, scale)


@router.get("/mimo/blocks")
def get_mimo_blocks(since: int = Query(0, ge=0), limit: int = Query(5000, ge=1, le=5000)):
    _, world = active_world(open_registry(), read_only=True)
    return world.blocks_since(since, limit)


@router.post("/mimo/hello")
def greet_mimo():
    _, world = active_world(open_registry())
    try:
        return world.greet(time.time())
    except (LifeOver, WorldBehind) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/mimo/action")
def act_with_mimo(request: OwnerAction):
    _, world = active_world(open_registry())
    try:
        return world.owner_action(request.action, request.item, time.time())
    except (LifeOver, WorldBehind) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/mimo/care")
def care_for_mimo(request: CareRequest):
    _, world = active_world(open_registry())
    try:
        return give_care(world, request.kind, time.time())
    except (LifeOver, CareRefused, WorldBehind) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
