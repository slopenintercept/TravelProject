"""FastAPI backend: trip endpoints, the SSE activity stream, evidence files and the built frontend."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, evidence, orchestrator, store
from .booking import BookingStep, booking_steps
from .cards import Card, review_cards
from .events import bus
from .models import TravelerIn, TripRequest, TripState

app = FastAPI(title="Tripwright")
FRONTEND = config.ROOT / "frontend" / "dist"
FIXTURE_EVIDENCE = Path(__file__).parent / "fixtures" / "evidence"

_live: dict[str, TripState] = {}  # trips being worked on; the database copy lags a running stage
_locks: dict[str, asyncio.Lock] = {}
_tasks: set[asyncio.Task] = set()


class TripView(BaseModel):
    state: TripState
    cards: list[Card]
    booking: list[BookingStep]  # the finish screen: what to book, in order, with links
    busy: bool
    message: str = ""


class DatesIn(BaseModel):
    start: date


class DecisionIn(BaseModel):
    action: Literal["approve", "remove", "restore", "swap", "switch"]
    card: str
    option_id: str | None = None


class TravelerRef(BaseModel):
    traveler: str


class MoveIn(BaseModel):
    item_id: str
    day: date


class SwapIn(BaseModel):
    item_id: str
    attraction_id: str


def _trip(trip_id: str) -> TripState:
    if trip_id not in _live:
        state = store.load_trip(trip_id)
        if state is None:
            raise HTTPException(404, "Trip not found")
        _live[trip_id] = state
    return _live[trip_id]


def _lock(trip_id: str) -> asyncio.Lock:
    return _locks.setdefault(trip_id, asyncio.Lock())


def _view(state: TripState, message: str = "") -> TripView:
    return TripView(state=state, cards=review_cards(state), booking=booking_steps(state),
                    busy=_lock(state.id).locked(), message=message)


def _background(state: TripState, work) -> None:
    """Run a stage without blocking the request; one stage at a time per trip."""

    async def runner() -> None:
        async with _lock(state.id):
            try:
                await work
            except Exception as e:
                bus(state.id).emit("error", message=f"{type(e).__name__}: {e}")
                store.save_trip(state)

    task = asyncio.create_task(runner())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


@app.get("/api/health")
def health() -> dict:
    return {
        "inference": {"base_url": config.OPENAI_BASE_URL, "model": config.CHAT_MODEL, "key": bool(config.OPENAI_API_KEY)},
        "research": "tavily" if config.TAVILY_API_KEY else "no TAVILY_API_KEY",
        "database": config.DATABASE_URL.split(":", 1)[0],
        "evidence": "object storage" if config.OBJ_BUCKET else "local disk",
        "demo_mode": config.DEMO_MODE,
    }


@app.post("/api/trips")
async def create_trip(request: TripRequest) -> TripView:
    state = orchestrator.new_trip(request)
    _live[state.id] = state
    _background(state, orchestrator.plan_timeframe(state))
    return _view(state)


@app.get("/api/trips/{trip_id}")
def get_trip(trip_id: str) -> TripView:
    return _view(_trip(trip_id))


@app.get("/api/trips/{trip_id}/events")
async def events(trip_id: str) -> StreamingResponse:
    _trip(trip_id)

    async def stream():
        async for event in bus(trip_id).stream():
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/trips/{trip_id}/dates")
async def choose_dates(trip_id: str, body: DatesIn) -> TripView:
    """The host sets the dates. Planning waits until everyone invited has added their preferences."""
    state = _trip(trip_id)
    if body.start <= date.today():
        raise HTTPException(400, "Pick a start date in the future")
    async with _lock(trip_id):
        await orchestrator.choose_dates(state, body.start)
    return _view(state)


@app.post("/api/trips/{trip_id}/travelers")
async def join(trip_id: str, body: TravelerIn) -> TripView:
    """An invited traveler adds themselves and their preferences."""
    state = _trip(trip_id)
    if state.stage in ("planning", "review"):
        raise HTTPException(400, "Planning has already started for this trip")
    orchestrator.join(state, body)
    return _view(state)


@app.delete("/api/trips/{trip_id}/travelers/{traveler_id}")
async def leave(trip_id: str, traveler_id: str) -> TripView:
    state = _trip(trip_id)
    if state.stage in ("planning", "review"):
        raise HTTPException(400, "Planning has already started for this trip")
    try:
        orchestrator.leave(state, traveler_id)
    except (ValueError, StopIteration) as e:
        raise HTTPException(400, str(e) or "Unknown traveler") from e
    return _view(state)


@app.post("/api/trips/{trip_id}/plan")
async def plan(trip_id: str) -> TripView:
    """Everyone's in: find each traveler's flights and lodging, and plan attractions for the group."""
    state = _trip(trip_id)
    if state.dates is None:
        raise HTTPException(400, "Choose the dates first")
    state.stage = "planning"
    _background(state, orchestrator.plan_trip(state))
    return _view(state)


@app.post("/api/trips/{trip_id}/decisions")
async def decide(trip_id: str, body: DecisionIn) -> TripView:
    state = _trip(trip_id)
    if body.action == "switch":  # re-runs a specialist, so it goes to the background
        _background(state, orchestrator.decide(state, body.action, body.card, body.option_id))
        await asyncio.sleep(0)
        return _view(state)
    async with _lock(trip_id):
        try:
            await orchestrator.decide(state, body.action, body.card, body.option_id)
        except (ValueError, StopIteration, IndexError) as e:
            raise HTTPException(400, str(e) or "Unknown card") from e
    return _view(state)


@app.post("/api/trips/{trip_id}/budget/apply")
async def apply_budget(trip_id: str, body: TravelerRef) -> TripView:
    state = _trip(trip_id)
    async with _lock(trip_id):
        await orchestrator.apply_budget_proposal(state, body.traveler)
    return _view(state)


@app.post("/api/trips/{trip_id}/itinerary/move")
async def move_item(trip_id: str, body: MoveIn) -> TripView:
    state = _trip(trip_id)
    async with _lock(trip_id):
        try:
            message = await orchestrator.move_item(state, body.item_id, body.day)
        except (ValueError, StopIteration) as e:
            raise HTTPException(400, str(e) or "Unknown itinerary item") from e
    return _view(state, message)


@app.post("/api/trips/{trip_id}/itinerary/swap")
async def swap_item(trip_id: str, body: SwapIn) -> TripView:
    state = _trip(trip_id)
    async with _lock(trip_id):
        try:
            await orchestrator.swap_item(state, body.item_id, body.attraction_id)
        except StopIteration as e:
            raise HTTPException(400, "Unknown itinerary item") from e
    return _view(state)


@app.get("/evidence/{path:path}")
def evidence_file(path: str) -> FileResponse:
    """Local evidence snapshots (when Object Storage isn't configured) and the demo fixtures' snapshots."""
    for root in (evidence.LOCAL_DIR, FIXTURE_EVIDENCE):
        file = (root / path).resolve()
        if file.is_file() and root.resolve() in file.parents:
            return FileResponse(file)
    raise HTTPException(404, "No such evidence file")


if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
