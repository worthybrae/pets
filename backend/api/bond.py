"""Bond: talking with Mimo (B1); the owner's visits and Mimo's inbox (B2); the diary (B3)."""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.lives import open_registry
from backend.api.mimo import active_world
from backend.survival.bond_view import note_visit
from backend.survival.clock import time_scale
from backend.survival.diary import DIARY_SHOWN, diary_entries
from backend.survival.inbox import MARKED_AT_MOST, inbox_listing, mark_ids, mark_one, mark_read, name_place, unread
from backend.survival.questions import answer_question
from backend.survival.talk import ChatLimited, owner_says
from backend.survival.world import LifeOver

router = APIRouter()


class ChatLine(BaseModel):
    text: str


class ReadUpTo(BaseModel):
    up_to: int | None = None  # every item up to this id
    id: int | None = None  # B3: this one only (the story the owner just read)
    ids: list[int] | None = None  # Bond's final fix wave (I7): the items the inbox listed, and only those


class PlaceName(BaseModel):
    text: str | None = None  # a name for the place a naming question is about
    choice: int | None = None  # W1: the chip the owner picks for one of Mimo's questions


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
    """Mimo's messages: every unread one first, then the newest read ones (Bond follow-up, N1), each part
    newest first, and how many are unread. Reads only."""
    _, world = active_world(open_registry(), read_only=True)
    with world.connect() as db:
        return {"items": inbox_listing(db), "unread": unread(db)}


@router.post("/mimo/inbox/read")
def read_inbox(request: ReadUpTo):
    """Mark Mimo's messages read up to an id, one message, or the ones listed (ids). Returns how many are
    still unread."""
    if sum(given is not None for given in (request.up_to, request.id, request.ids)) != 1:
        raise HTTPException(status_code=400, detail="Give one of up_to, id or ids")
    if request.ids is not None and len(request.ids) > MARKED_AT_MOST:
        raise HTTPException(status_code=400, detail=f"At most {MARKED_AT_MOST} ids")
    _, world = active_world(open_registry())
    try:
        if request.ids is not None:
            return {"unread": mark_ids(world, request.ids, time.time())}
        if request.id is not None:
            return {"unread": mark_one(world, request.id, time.time())}
        return {"unread": mark_read(world, request.up_to, time.time())}
    except LifeOver as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/mimo/inbox/{item_id}/answer")
def answer_inbox(item_id: int, request: PlaceName):
    """Name the place a naming question is about, or (W1) pick an answer chip for one of Mimo's questions."""
    if (request.text is None) == (request.choice is None):
        raise HTTPException(status_code=400, detail="Give one of text or choice")
    _, world = active_world(open_registry())
    try:
        if request.choice is not None:
            return {"item": answer_question(world, item_id, request.choice, time.time(), time_scale())}
        return {"item": name_place(world, item_id, request.text, time.time(), time_scale())}
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except LifeOver as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/mimo/diary")
def get_diary():
    """The newest stories of Mimo's diary, newest first. Reads only."""
    _, world = active_world(open_registry(), read_only=True)
    with world.connect() as db:
        return {"entries": diary_entries(db, DIARY_SHOWN)}
