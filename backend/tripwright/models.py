"""Shared trip state and the structured results every agent returns.

Times are naive local times: a flight departs in origin-local time and arrives in
destination-local time; everything on the ground is destination-local.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field

Pace = Literal["relaxed", "balanced", "packed"]
CATEGORIES = ("flights", "lodging", "attractions", "transport")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class Source(BaseModel):
    """Where a fact came from, plus the snapshot saved to Object Storage."""

    url: str
    title: str = ""
    evidence_url: str | None = None
    fetched_at: datetime | None = None


class TravelerIn(BaseModel):
    """What each person fills in: where they fly from and their budget. What they need and want to see
    comes from their picks on the ideas list; the fields stay here so older trips still load."""

    name: str = Field(min_length=1)
    origin: str = Field(min_length=1)
    budget_usd: float = Field(gt=0)
    need: list[str] = []
    want: list[str] = []


class TripRequest(TravelerIn):
    """The host's form: the trip itself plus the host's own preferences."""

    name: str = "Host"
    destination: str
    days: int = Field(ge=1, le=30)
    start_date: date | None = None
    pace: Pace = "balanced"


class TravelerProfile(BaseModel):
    home: str = ""
    interests: list[str] = []
    pace: Pace = "balanced"
    # Learned from review-screen overrides; carried into future trips.
    stated_preferences: list[str] = []
    summary: str = ""


class RouteSegment(BaseModel):
    city: str
    nights: int = Field(ge=1)


class RoutePlan(BaseModel):
    segments: list[RouteSegment]
    # Calendar days between leaving the origin and landing (1 for KC -> Japan).
    arrival_day_offset: int = Field(0, ge=0, le=2)


class DateWindow(BaseModel):
    id: str
    start: date  # depart origin
    end: date  # depart destination
    avg_high_c: float | None = None
    avg_low_c: float | None = None
    rainy_days: int | None = None
    weather_summary: str = ""
    crowd_level: Literal["low", "moderate", "high"] = "moderate"
    cheapest_fare_usd: float | None = None
    price_trend: str = ""
    notes: str = ""  # closures, festivals, holidays
    reasoning: str = ""
    sources: list[Source] = []


class TripDates(BaseModel):
    start: date  # depart origin
    arrival: date  # land at destination
    end: date  # depart destination


class FlightOption(BaseModel):
    id: str
    airline: str
    origin: str
    destination: str
    depart_at: datetime
    arrive_at: datetime
    return_depart_at: datetime | None = None
    return_arrive_at: datetime | None = None
    duration_minutes: int
    stops: int
    layovers: list[str] = []
    price_usd: float  # round trip, per traveler
    booking_url: str
    source: Source
    tradeoff: str = ""


class FlightPlan(BaseModel):
    origin_airports: list[str] = []
    options: list[FlightOption]
    selected_id: str

    @property
    def selected(self) -> FlightOption:
        return next(o for o in self.options if o.id == self.selected_id)


class CommonChoice(BaseModel):
    """The "most travelers here pick X because Y" note on lodging/transport cards."""

    choice: str
    because: str
    alternative: str
    details: list[str] = []
    sources: list[Source] = []


class LodgingOption(BaseModel):
    id: str
    city: str
    name: str
    kind: Literal["hotel", "airbnb"]
    neighborhood: str = ""
    check_in: date
    check_out: date
    price_total_usd: float
    rating: float | None = None
    location_note: str = ""
    lat: float | None = None
    lon: float | None = None
    booking_url: str
    source: Source

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days


class LodgingStay(BaseModel):
    city: str
    check_in: date
    check_out: date
    selected_id: str
    options: list[LodgingOption]
    reasoning: str = ""

    @property
    def selected(self) -> LodgingOption:
        return next(o for o in self.options if o.id == self.selected_id)


class LodgingPlan(BaseModel):
    common_choice: CommonChoice
    stays: list[LodgingStay]


class Idea(BaseModel):
    """One place on the trip's shared list, found by the ideas agent or added by a traveler."""

    id: str
    name: str
    city: str = ""
    category: str = ""
    why: str = ""
    source: Source | None = None
    added_by: str | None = None  # traveler id; None for the agent's suggestions
    suggested_for: str | None = None  # traveler id who asked the agents for more like their picks
    lat: float | None = None  # looked up for the draft plan
    lon: float | None = None


class Traveler(TravelerIn):
    """One person on the trip, with their own flight and their own rooms picked to their own budget.

    Their marks on the ideas list are the place names in `need` (must do), `want` (interested)
    and `skip` (not for me); a name is in at most one of them."""

    id: str
    host: bool = False
    skip: list[str] = []
    picked: bool = False  # has saved their marks
    confirmed: bool = False  # has chosen their flight and rooms; the days are planned around them
    flights: FlightPlan | None = None
    lodging: LodgingPlan | None = None  # this traveler's room for each stay, chosen from the group's options
    legs: list[TransportLeg] = []  # this traveler's own copy of the transport legs: what they keep, they pay for
    rental_car: bool = False  # this traveler wants a rental car


class Attraction(BaseModel):
    id: str
    name: str
    city: str
    must_have: bool = False  # someone needs to see it
    need_by: list[str] = []  # traveler ids
    want_by: list[str] = []
    skip_by: list[str] = []  # marked it not for me: they are free while the others go
    why: str = ""
    duration_minutes: int = 120
    ticket_price_usd: float = 0  # per traveler
    opens: time | None = None
    closes: time | None = None
    closed_weekdays: list[int] = []  # Monday = 0
    outdoor: bool = False
    availability_note: str = ""
    lat: float | None = None
    lon: float | None = None
    booking_url: str | None = None
    source: Source
    included: bool = True


class TransportLeg(BaseModel):
    id: str
    kind: Literal["intercity", "airport_transfer", "local_pass", "rental_car"]
    from_place: str = ""
    to_place: str = ""
    mode: str
    duration_minutes: int = 0
    price_usd: float
    per_person: bool = True
    notes: str = ""
    booking_url: str | None = None
    source: Source
    included: bool = True
    alternatives: list[TransportLeg] = []  # other ways to make the same trip, for a traveler to swap to


class TransportPlan(BaseModel):
    common_choice: CommonChoice
    rideshare_note: str = ""
    legs: list[TransportLeg]


class DayWeather(BaseModel):
    day: date
    city: str
    high_c: float | None = None
    low_c: float | None = None
    precip_prob: float | None = None  # 0-100
    summary: str = ""
    kind: Literal["forecast", "climate"] = "climate"
    source: Source


class ItineraryItem(BaseModel):
    id: str
    day: date
    start: time
    end: time
    kind: Literal["arrival", "departure", "travel", "attraction"]
    title: str
    city: str
    ref_id: str | None = None
    cost_usd: float = 0
    travelers: list[str] = []  # ids of who is there; fewer than everyone means a split-off
    locked: bool = False  # flights and intercity travel can't be dragged
    pinned: bool = False  # the user put this on this day


class Unscheduled(BaseModel):
    attraction_id: str
    name: str
    reason: str
    wanted_by: list[str] = []  # traveler ids who needed or wanted it


class Draft(BaseModel):
    """A rough sketch of the days from everyone's picks, rebuilt as people save them, before any flights or
    hotels are found. Durations are typical ones by category; there are no prices or opening hours yet."""

    itinerary: list[ItineraryItem] = []
    unscheduled: list[Unscheduled] = []
    plan_note: str = ""  # the scheduler's summary: who splits off or skips what, and when
    note: str = ""  # the orchestrator's explanation for the group
    route: RoutePlan | None = None
    built_at: datetime | None = None


class Violation(BaseModel):
    code: str
    message: str
    item_ids: list[str] = []
    severity: Literal["error", "warning"] = "error"


class BudgetSummary(BaseModel):
    total_usd: float
    by_category: dict[str, float]
    allotted: dict[str, float]
    spent_usd: float
    remaining_usd: float


class Swap(BaseModel):
    category: str
    action: Literal["swap", "remove"]
    from_id: str
    to_id: str | None = None
    title: str
    saves_usd: float


class SwapProposal(BaseModel):
    swaps: list[Swap]
    new_total_usd: float
    fits: bool


AgentStatusName = Literal[
    "idle", "working", "under_review", "sent_back", "accepted", "fallback", "pending", "failed"
]


class AgentStatus(BaseModel):
    agent: str
    status: AgentStatusName = "idle"
    attempt: int = 0
    message: str = ""
    found: str = ""


class Flag(BaseModel):
    """Marks a result the orchestrator could not fully verify, for the review screen."""

    kind: Literal["fallback", "pending"]
    reason: str


class TripState(BaseModel):
    id: str
    request: TripRequest
    # gathering: dates are set and the host is waiting for invited travelers' preferences.
    # choosing: the agents are researching and each traveler chooses their flight and rooms; the days are
    # scheduled once anyone has (review).
    stage: Literal["created", "timeframe", "awaiting_dates", "gathering", "planning", "choosing", "review"] = "created"
    travelers: list[Traveler] = []  # the host first
    profile: TravelerProfile | None = None
    route: RoutePlan | None = None
    ideas: list[Idea] = []  # the shared list everyone marks
    windows: list[DateWindow] = []
    dates: TripDates | None = None
    lodging: LodgingPlan | None = None  # what the lodging agent found: the options for each stay
    attractions: list[Attraction] = []
    transport: TransportPlan | None = None
    weather: list[DayWeather] = []
    itinerary: list[ItineraryItem] = []
    unscheduled: list[Unscheduled] = []
    draft: Draft | None = None  # before planning: the rough sketch from everyone's picks
    violations: list[Violation] = []
    plan_note: str = ""  # "One shared itinerary", or who splits off and when
    budgets: dict[str, BudgetSummary] = {}  # per traveler id
    budget_proposals: dict[str, SwapProposal] = {}
    flags: dict[str, Flag] = {}
    approvals: dict[str, Literal["approved"]] = {}
    agents: dict[str, AgentStatus] = {}
    # Overrides from the review screen.
    lodging_override: Literal["hotel", "airbnb"] | None = None

    def traveler(self, traveler_id: str) -> Traveler:
        return next(t for t in self.travelers if t.id == traveler_id)

    def names(self, traveler_ids: list[str]) -> list[str]:
        return [t.name for t in self.travelers if t.id in traveler_ids]
