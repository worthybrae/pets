"""Bond: talking with Mimo (B1)."""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.lives import open_registry
from backend.api.mimo import active_world
from backend.survival.clock import time_scale
from backend.survival.talk import ChatLimited, owner_says
from backend.survival.world import LifeOver

router = APIRouter()


class ChatLine(BaseModel):
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
