import logging
import os
from collections import defaultdict
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import require_telegram_auth
from calculator import calculate_ingredients
from database import (
    delete_event,
    get_all_dishes,
    get_all_events,
    get_event_by_id,
    init_db,
    save_event,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Karavan API")

MINIAPP_ORIGIN = os.environ.get("MINIAPP_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[MINIAPP_ORIGIN] if MINIAPP_ORIGIN != "*" else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


class CalculateRequest(BaseModel):
    guests: int
    dish_ids: List[int]


class EventCreateRequest(BaseModel):
    name: str
    guests: int
    dish_ids: List[int]
    event_date: Optional[str] = ""


@app.get("/api/dishes")
def list_dishes():
    dishes = get_all_dishes()
    grouped = defaultdict(list)
    for dish in dishes:
        grouped[dish["category"]].append(dish)
    return {"categories": grouped}


@app.post("/api/calculate")
def calculate(payload: CalculateRequest):
    if payload.guests <= 0:
        raise HTTPException(status_code=400, detail="guests must be positive")
    if not payload.dish_ids:
        raise HTTPException(status_code=400, detail="dish_ids must not be empty")
    return {"ingredients": calculate_ingredients(payload.guests, payload.dish_ids)}


@app.get("/api/events")
def list_events(_=Depends(require_telegram_auth)):
    return {"events": get_all_events()}


@app.get("/api/events/{event_id}")
def get_event(event_id: int, _=Depends(require_telegram_auth)):
    event = get_event_by_id(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    import json

    dish_ids = json.loads(event["dish_ids"])
    event["ingredients"] = calculate_ingredients(event["guests"], dish_ids)
    return event


@app.post("/api/events")
def create_event(payload: EventCreateRequest, _=Depends(require_telegram_auth)):
    if payload.guests <= 0:
        raise HTTPException(status_code=400, detail="guests must be positive")
    if not payload.dish_ids:
        raise HTTPException(status_code=400, detail="dish_ids must not be empty")
    event_id = save_event(payload.name, payload.guests, payload.dish_ids, payload.event_date or "")
    return {"id": event_id}


@app.delete("/api/events/{event_id}")
def remove_event(event_id: int, _=Depends(require_telegram_auth)):
    if get_event_by_id(event_id) is None:
        raise HTTPException(status_code=404, detail="Event not found")
    delete_event(event_id)
    return {"ok": True}


@app.get("/health")
def health():
    return {"status": "ok"}
