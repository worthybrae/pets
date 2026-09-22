"""Read the real Mimo worker state and deliver owner interactions."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.live_mimo import MimoStore

router = APIRouter()


class OwnerAction(BaseModel):
    action: str
    item: str


@router.get("/mimo")
def get_mimo():
    return MimoStore().snapshot()


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
