"""Read the real Mimo worker state and deliver owner interactions."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.live_mimo import MimoStore

router = APIRouter()


class OwnerAction(BaseModel):
    action: str
    item: str


@router.get("/mimo")
def get_mimo():
    return MimoStore().snapshot()


@router.get("/mimo/blocks")
def get_mimo_blocks(since: int = Query(0, ge=0), limit: int = Query(5000, ge=1, le=5000)):
    return MimoStore().blocks_since(since, limit)


@router.post("/mimo/hello")
def greet_mimo():
    return MimoStore().greet()


@router.post("/mimo/action")
def act_with_mimo(request: OwnerAction):
    try:
        return MimoStore().owner_action(request.action, request.item)
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
