"""Bond: talking with Mimo (B1); the owner's visits and Mimo's inbox (B2)."""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.lives import open_registry
from backend.api.mimo import active_world
from backend.survival.bond_view import note_visit
from backend.survival.clock import time_scale
from backend.survival.inbox import ITEMS_SHOWN, inbox_items, mark_read, name_place, unread
from backend.survival.talk import ChatLimited, owner_says
from backend.survival.world import LifeOver

router = APIRouter()


class ChatLine(BaseModel):
    text: str


class ReadUpTo(BaseModel):
    up_to: int


class PlaceName(BaseModel):
    text: str


@router.post("/mimo/chat")
def talk_to_mimo(request: ChatLine):
    """Write a line to Mimo. The reply comes later, in /api/mimo's chat, once the worker answers."""
    _, world = active_world(open_registry())
    try:
        return owner_says(world, request.text, time.time(), time_scale())
    except LifeOver as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ChatLimited as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/mimo/visit")
def visit_mimo():
    """The viewer is open: the owner is here. Returns the bond."""
    _, world = active_world(open_registry())
    try:
        return {"bond": note_visit(world, time.time())}
    except LifeOver as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/mimo/inbox")
def get_inbox():
    """Mimo's newest messages, newest first, and how many are unread. Reads only."""
    _, world = active_world(open_registry(), read_only=True)
    with world.connect() as db:
        return {"items": inbox_items(db, ITEMS_SHOWN), "unread": unread(db)}


@router.post("/mimo/inbox/read")
def read_inbox(request: ReadUpTo):
    """Mark Mimo's messages read up to an id. Returns how many are still unread."""
    _, world = active_world(open_registry())
    return {"unread": mark_read(world, request.up_to, time.time())}


@router.post("/mimo/inbox/{item_id}/answer")
def answer_inbox(item_id: int, request: PlaceName):
    """Name the place a naming question is about."""
    _, world = active_world(open_registry())
    try:
        return {"item": name_place(world, item_id, request.text, time.time(), time_scale())}
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except LifeOver as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
