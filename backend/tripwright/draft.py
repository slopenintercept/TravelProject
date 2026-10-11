"""The draft plan: a rough sketch of the days from everyone's picks, before anyone has flights or hotels.

It is rebuilt shortly after anyone saves their picks, joins or leaves, so the group sees how its wishes
fit without waiting for the host to start planning. Three steps:

1. The orchestrator's route planner re-decides the cities and nights from everyone's picks (one quick
   model call, no tools).
2. Code turns each place someone wants into a rough activity (a typical duration for its category,
   located once by name), assigns it to the nearest city on the route, and runs the real scheduler on a
   copy of the trip where everyone lands mid-afternoon on arrival day and leaves mid-afternoon on the last
   day. Splits, regroups and skips work exactly as in the final plan.
3. The orchestrator reads the result and writes a short note for the group.

The draft is stored apart from the real itinerary, so planning starts clean.
"""

from __future__ import annotations

import re
from datetime import datetime, time

from pydantic import BaseModel, Field
from strands import Agent

from . import config, store
from .events import bus
from .geo import haversine_km, same_city
from .llm import RateLimit, make_model
from .models import Attraction, Draft, FlightOption, FlightPlan, Idea, Source, TripState
from .orchestrator import fit_route_to_dates, route_graph, run
from .scheduler import schedule
from .specialists import brief, same_place
from .tools import places

# Typical visit length by category, in minutes; real hours and durations come from the attractions agent.
MINUTES = {"day trips": 480, "family": 180, "nightlife": 150, "shopping": 120, "food": 90, "nature": 90,
           "sights": 90, "culture": 90}
THEME_PARK = re.compile(r"disney|universal studios|theme park", re.IGNORECASE)
# Typical hours by category, so the draft puts a bar in the evening; real hours come from the attractions agent.
HOURS = {"nightlife": (time(18, 0), time(23, 59))}
LAND, LEAVE = time(15, 0), time(15, 0)  # stand-ins for everyone's flights

DRAFT_ROLE = (
    "You are the orchestrator of Tripwright, a team of travel-planning agents. Before any flights or hotels are "
    "found, the group sees a rough draft of its days built from everyone's picks. Explain the draft to the group "
    "in 2 to 4 short, friendly sentences: what everyone does together, who splits off for what and when, and "
    "anything that doesn't fit yet with what could make it fit. Use the travelers' names. Do not invent places, "
    "times or prices that are not in the draft."
)


class DraftNote(BaseModel):
    note: str = Field(description="2 to 4 short sentences for the group")


def minutes(idea: Idea) -> int:
    if THEME_PARK.search(idea.name):
        return 540
    return MINUTES.get(idea.category.strip().lower(), 120)


async def locate(state: TripState) -> dict[str, tuple[float, float]]:
    """Coordinates for every place (looked up once and kept on the idea) and for every city on the route."""
    for idea in state.ideas:
        if idea.lat is None:  # lookups, misses included, are cached, so a retry costs nothing
            coords = None
            # The place by name; failing that ("Nara day trip" isn't on a map), the town it's in.
            for query in (f"{idea.name}, {idea.city or state.request.destination}",
                          f"{idea.city}, {state.request.destination}" if idea.city else None):
                if query and coords is None:
                    try:
                        coords = await places.geocode(query)
                    except Exception:
                        coords = None
            idea.lat, idea.lon = coords or (None, None)
    cities = {}
    for segment in state.route.segments:
        if segment.city not in cities:
            try:
                coords = await places.geocode(f"{segment.city}, {state.request.destination}")
            except Exception:
                coords = None
            if coords:
                cities[segment.city] = coords
    return cities


def home_city(idea: Idea, route_cities: list[str], coords: dict[str, tuple[float, float]]) -> str:
    """The route city this place is visited from: its own city if the group sleeps there, else the nearest."""
    if own := next((c for c in route_cities if same_city(c, idea.city)), None):
        return own
    if idea.lat is not None and coords:
        return min(coords, key=lambda c: haversine_km(idea.lat, idea.lon, *coords[c]))
    return route_cities[0]


def sketch(state: TripState, coords: dict[str, tuple[float, float]]) -> Draft:
    """The days as the real scheduler would place everyone's picks, on a copy of the trip."""
    trial = state.model_copy(deep=True)
    stand_in = Source(url="")
    for t in trial.travelers:
        flight = FlightOption(
            id="draft", airline="", origin=t.origin, destination="", duration_minutes=0, stops=0, price_usd=0,
            depart_at=datetime.combine(trial.dates.start, time(9, 0)), arrive_at=datetime.combine(trial.dates.arrival, LAND),
            return_depart_at=datetime.combine(trial.dates.end, LEAVE), booking_url="", source=stand_in)
        t.flights = FlightPlan(options=[flight], selected_id="draft")

    route_cities = [s.city for s in trial.route.segments]
    trial.attractions = []
    for idea in trial.ideas:
        need = [t.id for t in trial.travelers if any(same_place(n, idea.name) for n in t.need)]
        want = [t.id for t in trial.travelers if t.id not in need and any(same_place(n, idea.name) for n in t.want)]
        if not need + want:
            continue  # nobody asked for it
        skip = [t.id for t in trial.travelers if any(same_place(n, idea.name) for n in t.skip)]
        opens, closes = HOURS.get(idea.category.strip().lower(), (None, None))
        trial.attractions.append(Attraction(
            opens=opens, closes=closes,
            id=idea.id, name=idea.name, city=home_city(idea, route_cities, coords), must_have=bool(need),
            need_by=need, want_by=want, skip_by=skip, why=idea.why, duration_minutes=minutes(idea),
            lat=idea.lat, lon=idea.lon, source=idea.source or stand_in))
    trial.itinerary, trial.weather = [], []
    schedule(trial)
    return Draft(itinerary=trial.itinerary, unscheduled=trial.unscheduled, plan_note=trial.plan_note,
                 route=trial.route, built_at=datetime.now())


def describe(state: TripState, draft: Draft) -> str:
    """The draft as the orchestrator reads it: each day, who goes where, and what didn't fit."""
    everyone = len(state.travelers)
    lines = []
    for item in draft.itinerary:
        who = "everyone" if len(item.travelers) == everyone else ", ".join(state.names(item.travelers))
        lines.append(f"{item.day:%a %b %d} {item.start:%H:%M}-{item.end:%H:%M} {item.city}: {item.title} ({who})")
    for u in draft.unscheduled:
        lines.append(f"Doesn't fit: {u.name}, wanted by {', '.join(state.names(u.wanted_by))}: {u.reason}")
    return "\n".join(lines)


async def explain(state: TripState, draft: Draft) -> str:
    """The orchestrator's note for the group, or nothing if the model is unavailable or the trip is recorded."""
    if not config.OPENAI_API_KEY or state.request.recorded:
        return ""
    agent = Agent(model=make_model(), name="orchestrator", system_prompt=DRAFT_ROLE, hooks=[RateLimit()],
                  callback_handler=None)
    try:
        result = await agent.invoke_async(
            f"{brief(state)}\n\nDraft of the days:\n{describe(state, draft)}\n\nScheduler's summary: {draft.plan_note}",
            structured_output_model=DraftNote)
        return result.structured_output.note if result.structured_output else ""
    except Exception:
        return ""


async def build_draft(state: TripState) -> None:
    """Re-plan the route from everyone's picks, sketch the days, and have the orchestrator explain them."""
    events = bus(state.id)
    events.status(state, "draft", "working", "Re-planning the cities from everyone's picks", 1)
    await run(state, route_graph(), "draft")
    if state.stage != "gathering":
        return  # planning started meanwhile; it makes its own route
    fit_route_to_dates(state)
    events.status(state, "draft", "working", "Placing everyone's picks on the days", 1)
    draft = sketch(state, await locate(state))
    events.status(state, "draft", "working", "The orchestrator is reading the draft", 1)
    draft.note = await explain(state, draft)
    if state.stage != "gathering":
        return
    state.draft = draft
    splits = len({i.ref_id for i in draft.itinerary if i.kind == "attraction"
                  and len(i.travelers) < len(state.travelers)})
    events.status(state, "draft", "accepted", "Draft updated",
                  found=f"{sum(i.kind == 'attraction' for i in draft.itinerary)} activities, {splits} not with everyone")
    store.save_trip(state)
    events.emit("state")
