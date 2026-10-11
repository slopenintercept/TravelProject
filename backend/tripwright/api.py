"""FastAPI backend: trip endpoints, the SSE activity stream, evidence files and the built frontend."""

from __future__ import annotations

import asyncio
import contextlib
import json
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from stripe import StripeError

from . import config, draft, evidence, orchestrator, payments, recorded, store
from .booking import BookingStep, booking_steps
from .cards import Card, review_cards
from .events import bus
from .models import Traveler, TravelerIn, TripRequest, TripState

app = FastAPI(title="Tripwright")
FRONTEND = config.ROOT / "frontend" / "dist"
FIXTURE_EVIDENCE = Path(__file__).parent / "fixtures" / "evidence"

_live: dict[str, TripState] = {}  # trips being worked on; the database copy lags a running stage
_locks: dict[str, asyncio.Lock] = {}
_tasks: set[asyncio.Task] = set()

You = Annotated[str | None, Header(alias="X-Traveler")]  # the traveler id from the person's own trip link
STARTED = ("planning", "choosing", "review")  # once planning starts, nobody joins, leaves or re-picks places


class TripView(BaseModel):
    state: TripState
    cards: list[Card]
    booking: list[BookingStep]  # the finish screen: what to book, in order, with links
    busy: bool
    message: str = ""
    you: str | None = None  # set when joining: the new traveler's id


class DatesIn(BaseModel):
    start: date


class DecisionIn(BaseModel):
    action: Literal["approve", "remove", "restore", "swap", "switch"]
    card: str
    option_id: str | None = None


class PicksIn(BaseModel):
    """Place names from the ideas list: must do, interested, not for me."""

    need: list[str] = []
    want: list[str] = []
    skip: list[str] = []


class IdeaIn(BaseModel):
    name: str = Field(min_length=1)
    city: str = ""


class ChoicesIn(BaseModel):
    """A traveler's flight (None when no flight was found) and one room per stay, in stay order."""

    flight_id: str | None = None
    stay_ids: list[str] = []


class TravelerRef(BaseModel):
    traveler: str


class MoveIn(BaseModel):
    item_id: str
    day: date


class SwapIn(BaseModel):
    item_id: str
    attraction_id: str


class PayIn(BaseModel):
    card: Literal["visa", "mastercard", "declined"]  # a test card from payments.CARDS


def _trip(trip_id: str) -> TripState:
    if trip_id not in _live:
        state = store.load_trip(trip_id)
        if state is None:
            raise HTTPException(404, "Trip not found")
        orchestrator.recover(state)  # nothing is running for it in this process
        recorded.replaying.set(state.request.recorded)  # before the work below starts
        _live[trip_id] = state
        if state.stage == "choosing" and any(t.confirmed for t in state.travelers):
            _background(state, orchestrator.schedule_choices(state))  # research was cut off after someone chose
        if state.stage == "gathering" and state.draft is None:
            _redraft(state)
    recorded.replaying.set(_live[trip_id].request.recorded)  # for this request and the work it starts
    return _live[trip_id]


DRAFT_DELAY_S = 10  # saves closer together than this build one draft
_draft_waits: dict[str, asyncio.Task] = {}  # a draft waiting for the picks to settle, per trip
_draft_locks: dict[str, asyncio.Lock] = {}


def _redraft(state: TripState) -> None:
    """Rebuild the draft plan shortly after the group's picks change. A save while one is waiting restarts the
    wait; a save while one is being built queues one more after it."""
    if state.stage != "gathering" or state.dates is None or state.route is None:
        return
    if (waiting := _draft_waits.get(state.id)) and not waiting.done():
        waiting.cancel()
    bus(state.id).status(state, "draft", "working", "Waiting a moment for more picks", 1)

    async def later() -> None:
        await asyncio.sleep(DRAFT_DELAY_S)
        if _draft_waits.get(state.id) is asyncio.current_task():
            del _draft_waits[state.id]  # building now: a new save starts a new wait instead of cancelling this
        async with _draft_locks.setdefault(state.id, asyncio.Lock()):
            try:
                await draft.build_draft(state)
            except Exception as e:
                bus(state.id).status(state, "draft", "failed", f"{type(e).__name__}: {e}")

    task = asyncio.create_task(later())
    _draft_waits[state.id] = task
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def _acting(state: TripState, traveler_id: str | None) -> Traveler:
    """Who is making this request (the `X-Traveler` header). Each person on the trip has their own link;
    there are no accounts, so this keeps people to their own choices rather than securing them."""
    acting = next((t for t in state.travelers if t.id == traveler_id), None)
    if acting is None:
        raise HTTPException(403, "Choose who you are on this trip first")
    return acting


def _host(state: TripState, traveler_id: str | None) -> Traveler:
    acting = _acting(state, traveler_id)
    if not acting.host:
        raise HTTPException(403, "Only the host can do that")
    return acting


def _owner(card: str) -> str | None:
    """Whose card this is: flights ("flight:<traveler>"), stays ("stay:<traveler>:<n>"), transport legs
    ("leg:<traveler>:<leg>") and adding a rental car ("transport:<traveler>") belong to one traveler."""
    kind, _, ref = card.partition(":")
    return ref.partition(":")[0] or None if kind in ("flight", "stay", "leg", "transport") else None


def _lock(trip_id: str) -> asyncio.Lock:
    return _locks.setdefault(trip_id, asyncio.Lock())


def _view(state: TripState, message: str = "") -> TripView:
    return TripView(state=state, cards=review_cards(state), booking=booking_steps(state),
                    busy=_lock(state.id).locked(), message=message)


def _background(state: TripState, work, exclusive: bool = True) -> None:
    """Run a stage without blocking the request. Exclusive stages run one at a time per trip and show the
    trip as busy; finding more places for one traveler doesn't, so everyone can keep marking meanwhile."""

    async def runner() -> None:
        async with _lock(state.id) if exclusive else contextlib.nullcontext():
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
        "payments": "stripe test mode" if config.STRIPE_SECRET_KEY else "holds kept in the app",
        "demo_mode": config.DEMO_MODE,
    }


@app.post("/api/trips")
async def create_trip(request: TripRequest) -> TripView:
    state = orchestrator.new_trip(request)
    recorded.replaying.set(request.recorded)
    _live[state.id] = state
    _background(state, orchestrator.plan_timeframe(state))
    return _view(state)


@app.get("/api/trips/{trip_id}")
async def get_trip(trip_id: str) -> TripView:  # async: loading a trip may resume its scheduling
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
async def choose_dates(trip_id: str, body: DatesIn, you: You = None) -> TripView:
    """The host sets the dates. Planning waits until everyone invited has added their preferences."""
    state = _trip(trip_id)
    _host(state, you)
    if body.start <= date.today():
        raise HTTPException(400, "Pick a start date in the future")
    async with _lock(trip_id):
        await orchestrator.choose_dates(state, body.start)
    _redraft(state)
    return _view(state)


@app.post("/api/trips/{trip_id}/travelers")
async def join(trip_id: str, body: TravelerIn) -> TripView:
    """An invited traveler adds themselves and their preferences."""
    state = _trip(trip_id)
    if state.stage in STARTED:
        raise HTTPException(400, "Planning has already started for this trip")
    joined = orchestrator.join(state, body)
    _redraft(state)
    view = _view(state)
    view.you = joined.id
    return view


@app.delete("/api/trips/{trip_id}/travelers/{traveler_id}")
async def leave(trip_id: str, traveler_id: str, you: You = None) -> TripView:
    """The host removes someone, or a traveler leaves."""
    state = _trip(trip_id)
    if _acting(state, you).id != traveler_id:
        _host(state, you)
    if state.stage in STARTED:
        raise HTTPException(400, "Planning has already started for this trip")
    try:
        orchestrator.leave(state, traveler_id)
    except (ValueError, StopIteration) as e:
        raise HTTPException(400, str(e) or "Unknown traveler") from e
    _redraft(state)
    return _view(state)


def _picking(state: TripState) -> None:
    """Marks and added places are open until planning starts, once the ideas agent has finished."""
    if state.stage in STARTED:
        raise HTTPException(400, "Planning has already started for this trip")
    if not orchestrator.ideas_ready(state):
        raise HTTPException(400, "Agents are still finding places")


@app.put("/api/trips/{trip_id}/travelers/{traveler_id}/picks")
async def save_picks(trip_id: str, traveler_id: str, body: PicksIn, you: You = None) -> TripView:
    """A traveler marks places on the ideas list: must do, interested, or not for me."""
    state = _trip(trip_id)
    if _acting(state, you).id != traveler_id:
        raise HTTPException(403, "Each traveler picks for themselves")
    _picking(state)
    try:
        orchestrator.save_picks(state, traveler_id, body.need, body.want, body.skip)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    _redraft(state)
    return _view(state)


@app.post("/api/trips/{trip_id}/ideas")
async def add_idea(trip_id: str, body: IdeaIn, you: You = None) -> TripView:
    """Anyone on the trip adds a place the agents did not suggest."""
    state = _trip(trip_id)
    acting = _acting(state, you)
    _picking(state)
    try:
        orchestrator.add_idea(state, acting.id, body.name, body.city)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return _view(state)


@app.post("/api/trips/{trip_id}/ideas/more")
async def suggest_more(trip_id: str, body: PicksIn, you: You = None) -> TripView:
    """Find more places like what this traveler marked so far. Their marks are kept (they stay on the
    picks screen), and the new places are added to the shared list when the agent is done."""
    state = _trip(trip_id)
    acting = _acting(state, you)
    _picking(state)
    if orchestrator.finding_more(state, acting.id):
        raise HTTPException(400, "Already finding more places for you")
    try:
        orchestrator.save_picks(state, acting.id, body.need, body.want, body.skip, picked=False)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    _redraft(state)
    bus(trip_id).status(state, f"more_ideas:{acting.id}", "working", "Finding more places like your picks", 1)
    _background(state, orchestrator.suggest_more(state, acting.id), exclusive=False)
    return _view(state)


@app.post("/api/trips/{trip_id}/plan")
async def plan(trip_id: str, you: You = None) -> TripView:
    """Everyone's in: find each traveler's flights and lodging, and plan attractions for the group."""
    state = _trip(trip_id)
    _host(state, you)
    if state.dates is None:
        raise HTTPException(400, "Choose the dates first")
    if (waiting := _draft_waits.pop(trip_id, None)) and not waiting.done():
        waiting.cancel()  # planning makes the real plan; a draft already being built discards itself
    state.stage = "planning"
    _background(state, orchestrator.plan_trip(state))
    return _view(state)


@app.post("/api/trips/{trip_id}/retry")
async def retry(trip_id: str, you: You = None) -> TripView:
    """Run again the research agents that timed out or fell back to saved results."""
    state = _trip(trip_id)
    _acting(state, you)
    if state.stage not in ("choosing", "review"):
        raise HTTPException(400, "Planning hasn't started yet")
    if _lock(trip_id).locked():
        raise HTTPException(400, "The agents are still working")
    if not orchestrator.unfinished(state):
        raise HTTPException(400, "Every agent finished; there is nothing to retry")
    _background(state, orchestrator.retry(state))
    await asyncio.sleep(0)  # let it take the trip's lock, so the response already shows the trip as busy
    return _view(state)


@app.put("/api/trips/{trip_id}/travelers/{traveler_id}/choices")
async def confirm_choices(trip_id: str, traveler_id: str, body: ChoicesIn, you: You = None) -> TripView:
    """A traveler confirms their flight and rooms. The days are planned around them now, or, while the agents
    are still researching, as soon as they finish."""
    state = _trip(trip_id)
    if _acting(state, you).id != traveler_id:
        raise HTTPException(403, "Each traveler chooses their own flight and rooms")
    if state.stage not in ("choosing", "review"):
        raise HTTPException(400, "Planning hasn't started yet")
    if not orchestrator.options_ready(state, traveler_id):
        raise HTTPException(400, "Your options are still being found")
    try:
        orchestrator.confirm_choices(state, traveler_id, body.flight_id, body.stay_ids)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if not _lock(trip_id).locked():  # otherwise the research run schedules the days when it ends
        async with _lock(trip_id):
            await orchestrator.schedule_choices(state)
    return _view(state)


@app.post("/api/trips/{trip_id}/decisions")
async def decide(trip_id: str, body: DecisionIn, you: You = None) -> TripView:
    """Each traveler decides on their own flight and stays; anyone on the trip decides on what is shared."""
    state = _trip(trip_id)
    acting = _acting(state, you)
    owner = _owner(body.card)
    if owner is not None and owner != acting.id:
        raise HTTPException(403, "Only that traveler can change their own flight and stays")
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
async def apply_budget(trip_id: str, body: TravelerRef, you: You = None) -> TripView:
    state = _trip(trip_id)
    if _acting(state, you).id != body.traveler:
        raise HTTPException(403, "Only that traveler can apply swaps to their own budget")
    async with _lock(trip_id):
        await orchestrator.apply_budget_proposal(state, body.traveler)
    return _view(state)


@app.post("/api/trips/{trip_id}/itinerary/move")
async def move_item(trip_id: str, body: MoveIn, you: You = None) -> TripView:
    state = _trip(trip_id)
    _acting(state, you)
    async with _lock(trip_id):
        try:
            message = await orchestrator.move_item(state, body.item_id, body.day)
        except (ValueError, StopIteration) as e:
            raise HTTPException(400, str(e) or "Unknown itinerary item") from e
    return _view(state, message)


@app.post("/api/trips/{trip_id}/itinerary/swap")
async def swap_item(trip_id: str, body: SwapIn, you: You = None) -> TripView:
    state = _trip(trip_id)
    _acting(state, you)
    async with _lock(trip_id):
        try:
            await orchestrator.swap_item(state, body.item_id, body.attraction_id)
        except StopIteration as e:
            raise HTTPException(400, "Unknown itinerary item") from e
    return _view(state)


async def _pay(state: TripState, step, traveler_id: str, *args) -> TripView:
    """Run a payment step off the event loop (Stripe is a network call), then save and tell every open tab."""
    async with _lock(state.id):
        try:
            message = await asyncio.to_thread(step, state, traveler_id, *args)
        except (ValueError, StripeError) as e:
            raise HTTPException(400, str(e)) from e
        finally:
            store.save_trip(state)
            bus(state.id).emit("state")
    return _view(state, message)


@app.post("/api/trips/{trip_id}/payments")
async def approve_payment(trip_id: str, body: PayIn, you: You = None) -> TripView:
    """A traveler approves their own share: a hold on a test card. Everyone is charged once everyone is in."""
    state = _trip(trip_id)
    return await _pay(state, payments.approve, _acting(state, you).id, body.card)


@app.delete("/api/trips/{trip_id}/payments")
async def back_out(trip_id: str, you: You = None) -> TripView:
    """A traveler backs out before the trip is paid: every hold is released."""
    state = _trip(trip_id)
    return await _pay(state, payments.back_out, _acting(state, you).id)


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
