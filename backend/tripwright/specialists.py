"""The specialist agents: what each is told, which tools it gets, and how its answer is checked.

Every specialist answers with a small structured output (ids, short text, source URLs).
Its `build` function is the deterministic half of the orchestrator's review: it joins
those ids and URLs back to what the tools really returned and raises `Rejected` with
specific feedback when something doesn't hold up. Prices and times are never taken
from the model's own text for flights and lodging.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, time, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

from .budget import allotted
from .geo import haversine_km, same_city
from .models import (
    Attraction, CommonChoice, DateWindow, DayWeather, FlightPlan, LodgingPlan, LodgingStay, RoutePlan,
    RouteSegment, Source, TransportLeg, TransportPlan, Traveler, TravelerProfile, TripState, new_id,
)
from .scheduler import stay_plan
from .toolbox import RunContext, Toolbox
from .tools import places

MAX_KM_FROM_CENTER = 20
SUGGESTIONS = {"relaxed": 3, "balanced": 5, "packed": 8}

PREAMBLE = (
    "You are the {title} on Tripwright, a team of travel-planning agents led by an orchestrator. "
    "Gather real data with your tools. Never invent a price, time, option id or URL: use only what "
    "your tools returned. Call only the tools you were given; you cannot delegate to other agents. "
    "Keep every explanation to one or two plain sentences."
)


class Rejected(Exception):
    """The result failed review; `problems` is the feedback sent back to the agent."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


def brief(state: TripState, who: Traveler | None = None) -> str:
    """The trip as every agent sees it. `who` is set for an agent planning one traveler's flight or lodging."""
    r = state.request
    lines = [f"Trip: {r.destination}, {r.days} days, {r.pace} pace, {len(state.travelers)} traveler(s)."]
    for t in state.travelers:
        lines.append(f"- {t.name}: flying from {t.origin}, budget ${t.budget_usd:,.0f}; needs to see: "
                     f"{', '.join(t.need) or 'nothing specified'}; would like to see: {', '.join(t.want) or 'nothing specified'}.")
    if who:
        lines.append(f"You are planning for {who.name} only.")
    if state.profile:
        lines.append(f"Host: {state.profile.summary} Stated preferences: "
                     f"{'; '.join(state.profile.stated_preferences) or 'none yet'}.")
    if state.dates:
        lines.append(f"Dates: leave home {state.dates.start}, land {state.dates.arrival}, fly home {state.dates.end}.")
    if state.route and state.dates:
        lines.append("Stays: " + "; ".join(
            f"{i}) {city} {a} to {b} ({(b - a).days} nights)" for i, (city, a, b) in enumerate(stay_plan(state), 1)))
    elif state.route:
        lines.append("Route: " + ", ".join(f"{s.city} {s.nights} nights" for s in state.route.segments) + ".")
    return "\n".join(lines)


def wishes(state: TripState) -> list[tuple[str, str, list[str], list[str]]]:
    """Everyone's attraction requests merged: (wish id, text, ids who need it, ids who want it)."""
    merged: dict[str, dict] = {}
    for t in state.travelers:
        for kind, names in (("need", t.need), ("want", t.want)):
            for name in names:
                if name.strip():
                    wish = merged.setdefault(name.strip().lower(), {"text": name.strip(), "need": [], "want": []})
                    wish[kind].append(t.id)
    return [(f"w{i}", w["text"], w["need"], w["want"]) for i, w in enumerate(merged.values(), 1)]


def _sources(ctx: RunContext, urls: list[str]) -> list[Source]:
    return [s for url in urls if (s := ctx.source(url))]


def _time(text: str) -> time | None:
    try:
        return time.fromisoformat(text.strip()[:5])
    except ValueError:
        return None


# --- profile -----------------------------------------------------------------

class ProfileOut(BaseModel):
    interests: list[str] = Field(description="3-6 short interest tags inferred from the request")
    summary: str = Field(description="One sentence describing this traveler")


async def build_profile(state: TripState, ctx: RunContext, out: ProfileOut) -> TravelerProfile:
    known = state.profile or TravelerProfile()
    return TravelerProfile(home=state.request.origin, interests=out.interests, pace=state.request.pace,
                           stated_preferences=known.stated_preferences, summary=out.summary)


# --- route (the orchestrator's own planning step) ------------------------------

class RouteOut(BaseModel):
    segments: list[RouteSegment] = Field(description="Cities to sleep in, in order, with nights in each")
    arrival_day_offset: int = Field(description="Calendar days between leaving home and landing: 0 or 1")


async def build_route(state: TripState, ctx: RunContext, out: RouteOut) -> RoutePlan:
    """Accept the cities; make the nights add up exactly, which the model often gets wrong."""
    offset = min(max(out.arrival_day_offset, 0), 1)
    nights = state.request.days - offset
    if not out.segments or nights < 1:
        raise Rejected(["give at least one city to stay in"])
    segments = [s.model_copy() for s in out.segments[:nights]]
    while sum(s.nights for s in segments) > nights:
        longest = max(segments, key=lambda s: s.nights)
        if longest.nights == 1:
            segments.pop()
        else:
            longest.nights -= 1
    segments[0].nights += nights - sum(s.nights for s in segments)
    gateway = segments[0].city
    if not same_city(segments[-1].city, gateway):
        raise Rejected([f"the route must end in {gateway}, where the flight home leaves from: "
                        f"move one night from another stay to a final night in {gateway}"])
    return RoutePlan(segments=segments, arrival_day_offset=offset)


# --- timeframe ---------------------------------------------------------------

class WindowPick(BaseModel):
    start_date: str = Field(description="YYYY-MM-DD, a date you checked with window_outlook")
    crowd_level: Literal["low", "moderate", "high"]
    price_trend: str = Field(description="How fares for this window compare, one sentence")
    notes: str = Field(description="Closures, festivals or holidays in this window; empty if none")
    reasoning: str = Field(description="Why this window, one or two sentences")
    source_urls: list[str] = Field(description="URLs from web_research that support this")


class TimeframeOut(BaseModel):
    windows: list[WindowPick] = Field(description="2 or 3 windows, best first")


async def build_timeframe(state: TripState, ctx: RunContext, out: TimeframeOut) -> list[DateWindow]:
    problems, windows = [], []
    for pick in out.windows[:3]:
        outlook = ctx.windows.get(pick.start_date)
        if outlook is None:
            problems.append(f"{pick.start_date} was not checked with window_outlook")
            continue
        if date.fromisoformat(pick.start_date) <= date.today():
            problems.append(f"{pick.start_date} is not in the future")
            continue
        if outlook["fare"] is None:
            problems.append(f"{pick.start_date} has no fare: call window_outlook for it again or propose another window")
            continue
        weather = outlook["weather"]
        windows.append(DateWindow(
            id=new_id("w"), start=pick.start_date, end=outlook["end"],
            avg_high_c=weather["avg_high_c"], avg_low_c=weather["avg_low_c"], rainy_days=weather["rainy_days"],
            weather_summary=f"Highs near {weather['avg_high_c']:.0f}°C, lows near {weather['avg_low_c']:.0f}°C, "
                            f"about {weather['rainy_days']} rainy day{'s' * (weather['rainy_days'] != 1)}",
            crowd_level=pick.crowd_level, cheapest_fare_usd=outlook["fare"], price_trend=pick.price_trend,
            notes=pick.notes, reasoning=pick.reasoning,
            sources=_sources(ctx, pick.source_urls + [weather["url"]]),
        ))
    if len(windows) < 2:
        problems.append("propose at least 2 windows, each checked with window_outlook")
    if problems:
        raise Rejected(problems)
    return windows


def timeframe_task(state: TripState, who: Traveler | None = None) -> str:
    r = state.request
    if r.start_date:
        ask = (f"The traveler wants to leave on {r.start_date}. Make that the first window, then offer one or "
               f"two alternatives within three weeks of it that are cheaper, quieter or drier.")
    else:
        earliest = date.today() + timedelta(days=21)
        ask = (f"The traveler is flexible. Consider windows starting between {earliest} and "
               f"{earliest + timedelta(days=240)}, spread across different seasons and including the low "
               "season, because fares vary a lot through the year.")
    return (f"{brief(state)}\n\nSuggest 2 or 3 date windows for this trip. {ask}\n"
            "Use web_research for crowd levels, seasonal events, holidays and closures, then call "
            "window_outlook for each candidate start date to get typical weather and the cheapest fare. "
            "Check at most 4 candidates, and only propose windows you checked with window_outlook.")


# --- flights -----------------------------------------------------------------

class FlightPick(BaseModel):
    option_id: str = Field(description="An id from search_flights, e.g. f3")
    tradeoff: str = Field(description="One sentence: price, duration, layovers and arrival time versus the others")


class FlightsOut(BaseModel):
    origin_airports: list[str] = Field(description="IATA codes of the nearest major airports to the origin")
    picks: list[FlightPick] = Field(description="The 3 best options, best first")


async def build_flights(state: TripState, ctx: RunContext, out: FlightsOut) -> FlightPlan:
    problems, picks = [], []
    for pick in out.picks:
        option = ctx.flights.get(pick.option_id)
        if option is None:
            problems.append(f"{pick.option_id} is not an id returned by search_flights")
        elif option.id not in {p.id for p in picks}:
            picks.append(option.model_copy(update={"tradeoff": pick.tradeoff}))
    if not picks:
        raise Rejected(problems or ["call search_flights, then pick 3 option ids from its results"])

    d = state.dates
    for o in picks:
        if o.depart_at.date() != d.start:
            problems.append(f"{o.id} leaves on {o.depart_at.date()} but the trip starts {d.start}")
        if o.arrive_at.date() != d.arrival:
            problems.append(f"{o.id} lands on {o.arrive_at.date()} but lodging starts {d.arrival}")
        if o.price_usd < 80 or (o.duration_minutes >= 480 and o.price_usd < 250):
            problems.append(f"{o.id} at ${o.price_usd:.0f} is not a plausible fare for this route")

    share = allotted(ctx.traveler)["flights"]
    on_dates = [o for o in ctx.flights.values() if (o.depart_at.date(), o.arrive_at.date()) == (d.start, d.arrival)]
    cheapest = min(on_dates, key=lambda o: o.price_usd, default=None)
    if cheapest and picks[0].price_usd > share and picks[0].price_usd > cheapest.price_usd * 1.05:
        problems.append(f"first pick costs ${picks[0].price_usd:.0f}, over the ${share:.0f} flight budget, "
                        f"and {cheapest.id} is cheaper at ${cheapest.price_usd:.0f}")
    if problems:
        raise Rejected(problems)
    return FlightPlan(origin_airports=out.origin_airports, options=picks[:3], selected_id=picks[0].id)


def flights_task(state: TripState, who: Traveler) -> str:
    gateway = state.route.segments[0].city
    return (f"{brief(state, who)}\n\nFind round-trip flights for {who.name} from {who.origin}. Resolve that origin "
            f"to its nearest major airport(s) and search to {gateway} with search_flights for exactly these dates. "
            f"The flight must land on {state.dates.arrival}. {who.name}'s flight budget is about "
            f"${allotted(who)['flights']:,.0f}. Pick the 3 best options, best first, and give each a one-sentence "
            "tradeoff (price, duration, layovers, arrival time).")


# --- lodging -----------------------------------------------------------------

class StayPick(BaseModel):
    stay: int = Field(description="Stay number from the brief, starting at 1")
    option_id: str = Field(description="An id from search_hotels or search_airbnb")
    alternative_ids: list[str] = Field(description="Up to 3 other ids from the same search")
    reasoning: str = Field(description="Why this place: transit, location, rating. One or two sentences. "
                                       "No budgets or traveler names")


class LodgingOut(BaseModel):
    most_travelers_pick: Literal["hotel", "airbnb"] = Field(description="What most travelers choose here")
    because: str = Field(description='Finish the sentence "Most travelers here pick this because ..."')
    neighborhoods: list[str] = Field(description="Neighborhoods most travelers stay in, per city")
    source_urls: list[str] = Field(description="URLs from web_research backing the claim")
    stays: list[StayPick] = Field(description="One pick per stay in the brief")


async def build_lodging(state: TripState, ctx: RunContext, out: LodgingOut) -> LodgingPlan:
    problems, stays = [], []
    want = state.lodging_override or out.most_travelers_pick
    sources = _sources(ctx, out.source_urls)
    if not sources:
        problems.append("the most-travelers-pick claim needs source_urls returned by web_research")

    for i, (city, check_in, check_out) in enumerate(stay_plan(state), 1):
        pick = next((p for p in out.stays if p.stay == i), None)
        room = ctx.rooms.get(pick.option_id) if pick else None
        label = f"stay {i} ({city}, {check_in} to {check_out})"
        if room is None:
            problems.append(f"{label} needs an option_id returned by a search tool")
            continue
        if (room.check_in, room.check_out) != (check_in, check_out) or not same_city(room.city, city):
            problems.append(f"{label}: {room.id} was searched for {room.city} {room.check_in} to {room.check_out}")
        if room.kind != want:
            problems.append(f"{label}: {room.id} is a {room.kind}, but the plan calls for {want}")
        if room.price_total_usd / max(room.nights, 1) < 12:
            problems.append(f"{label}: ${room.price_total_usd:.0f} is not a plausible price")
        center = await places.geocode(city)
        if room.lat and center and haversine_km(room.lat, room.lon, *center) > MAX_KM_FROM_CENTER:
            problems.append(f"{label}: {room.name} is too far from central {city}; stay near transit and the attractions")
        others = [r for r in ctx.rooms.values() if r.id != room.id and r.kind == room.kind
                  and (r.city, r.check_in, r.check_out) == (room.city, room.check_in, room.check_out)]
        others.sort(key=lambda r: (r.id not in pick.alternative_ids, r.price_total_usd))
        options = [room, *others[:7]]
        tightest = min(state.travelers, key=lambda t: t.budget_usd)
        cap = _nightly_cap(state, tightest)
        if min(o.price_total_usd / max(o.nights, 1) for o in options) > cap * 1.15:
            problems.append(f"{label}: nothing fits {tightest.name}'s lodging budget of about ${cap:.0f} a night; "
                            "search again with a lower max_nightly_usd")
        stays.append(LodgingStay(city=city, check_in=check_in, check_out=check_out, selected_id=room.id,
                                 options=options, reasoning=pick.reasoning))
    if problems:
        raise Rejected(problems)
    return LodgingPlan(
        common_choice=CommonChoice(
            choice=out.most_travelers_pick, because=out.because, details=out.neighborhoods, sources=sources,
            alternative="airbnb" if out.most_travelers_pick == "hotel" else "hotel"),
        stays=stays,
    )


def _nightly_cap(state: TripState, traveler: Traveler) -> float:
    """What this traveler can spend on a room per night: their lodging share spread over the trip."""
    return allotted(traveler)["lodging"] / max(sum(s.nights for s in state.route.segments), 1)


def assign_rooms(state: TripState) -> None:
    """Give each traveler their own room for every stay, chosen by their own budget alone.

    Deterministic: the best-rated option within their budget, else the cheapest one found.
    Nobody else's budget plays a part, so travelers can end up in different places.
    """
    def nightly(room) -> float:
        return room.price_total_usd / max(room.nights, 1)

    for t in state.travelers:
        cap, stays = _nightly_cap(state, t), []
        for stay in state.lodging.stays:
            within = [o for o in stay.options if nightly(o) <= cap]
            if within:
                room = max(within, key=lambda o: (o.rating or 0, -o.price_total_usd))
                why = (f"Best-rated option within {t.name}'s lodging budget of about ${cap:.0f} a night "
                       f"(rated {room.rating or 'n/a'}, ${nightly(room):.0f} a night).")
                if room == stay.selected:
                    why += f" {stay.reasoning}"
            else:
                room = min(stay.options, key=lambda o: o.price_total_usd)
                why = (f"Cheapest option found at ${nightly(room):.0f} a night; that is over {t.name}'s lodging "
                       f"budget of about ${cap:.0f} a night.")
            stays.append(stay.model_copy(update={"selected_id": room.id, "reasoning": why}))
        t.lodging = LodgingPlan(common_choice=state.lodging.common_choice, stays=stays)


def lodging_task(state: TripState, who: Traveler | None = None) -> str:
    caps = ", ".join(f"{t.name} ${_nightly_cap(state, t):,.0f}" for t in state.travelers)
    nightly = [_nightly_cap(state, t) for t in state.travelers]
    lowest, highest = min(nightly), max(nightly)
    override = (f"The group has asked for {state.lodging_override}, so search for that, but still report "
                "what most travelers pick. ") if state.lodging_override else ""
    return (f"{brief(state)}\n\nFind lodging options for the group: each traveler gets their own room, picked to "
            f"their own budget from what you find. Nightly lodging budgets: {caps}. "
            f"First use web_research to find what most travelers to {state.request.destination} "
            "choose for this kind of trip, hotel or Airbnb, and which neighborhoods they stay in (near transit, "
            "central to the attractions, easy for the airport, budget-friendly). Keep the source URLs. "
            f"{override}Then search within that choice once per stay, with max_nightly_usd at ${highest:,.0f}, the "
            "highest budget, and pick one place per stay plus up to 3 alternatives at different prices. Every "
            f"stay needs at least one option at or under ${lowest:,.0f} a night, the lowest budget. In each "
            "stay's reasoning describe the place only; each traveler's card states their own budget, so leave "
            "budgets and traveler names out.")


# --- attractions ---------------------------------------------------------------

class AttractionOut(BaseModel):
    name: str
    city: str = Field(description="The route city you would visit it from")
    wish_ids: list[str] = Field(description="Ids of the travelers' requests this covers, e.g. [\"w1\"]; empty for your own suggestions")
    why: str = Field(description="Why it fits this group, one short sentence")
    duration_minutes: int = Field(description="Typical visit length")
    ticket_price_usd: float = Field(description="Adult ticket in USD; 0 if free")
    opens: str = Field(description="Opening time HH:MM, or empty if always open")
    closes: str = Field(description="Closing time HH:MM, or empty if always open")
    closed_weekdays: list[int] = Field(description="Weekdays it is closed, Monday=0; empty if none")
    outdoor: bool = Field(description="True if rain would spoil it")
    availability_note: str = Field(description="Booking advice in under 15 words, e.g. buy tickets in advance")
    source_url: str = Field(description="URL from your tools where the price and hours were found")
    booking_url: str = Field(description="Official ticket page, or empty")


class AttractionsOut(BaseModel):
    attractions: list[AttractionOut]


async def build_attractions(state: TripState, ctx: RunContext, out: AttractionsOut) -> list[Attraction]:
    problems, found = [], []
    cities = [s.city for s in state.route.segments]
    asked = {wish_id: (text, need, want) for wish_id, text, need, want in wishes(state)}
    covered: set[str] = set()
    order = [t.id for t in state.travelers]
    for a in out.attractions:
        mine = [asked[w] for w in a.wish_ids if w in asked]
        need_by = [t for t in order if any(t in need for _, need, _ in mine)]
        want_by = [t for t in order if t not in need_by and any(t in want for _, _, want in mine)]
        source = ctx.source(a.source_url)
        if source is None:
            # Something a traveler needs has to be fixed; an unsourced extra is simply left out.
            if need_by:
                problems.append(f"{a.name}: source_url was not returned by your tools")
            continue
        if not 20 <= a.duration_minutes <= 720:
            problems.append(f"{a.name}: a {a.duration_minutes}-minute visit is not plausible")
        if not 0 <= a.ticket_price_usd <= 500:
            problems.append(f"{a.name}: ${a.ticket_price_usd:.0f} is not a plausible ticket price")
        city = next((c for c in cities if same_city(c, a.city)), None)
        if city is None:
            problems.append(f"{a.name}: city must be one of {', '.join(dict.fromkeys(cities))}")
            continue
        try:
            coords = await places.geocode(f"{a.name}, {city}")
        except Exception:
            coords = None
        covered.update(w for w in a.wish_ids if w in asked)
        found.append(Attraction(
            id=new_id("a"), name=a.name, city=city, must_have=bool(need_by), need_by=need_by, want_by=want_by, why=a.why,
            duration_minutes=a.duration_minutes, ticket_price_usd=a.ticket_price_usd, opens=_time(a.opens),
            closes=_time(a.closes), closed_weekdays=[d for d in a.closed_weekdays if 0 <= d <= 6],
            outdoor=a.outdoor, availability_note=a.availability_note, lat=coords and coords[0],
            lon=coords and coords[1], booking_url=a.booking_url or None, source=source,
        ))
    for wish_id, (text, need, _) in asked.items():
        if need and wish_id not in covered:
            problems.append(f'{wish_id} "{text}" is needed by {", ".join(state.names(need))} but no attraction covers it')
    if problems:
        raise Rejected(problems)
    return found


def relink_wishes(state: TripState) -> None:
    """A saved attractions list was made for other travelers: tie it to this group's requests by name."""
    def asked(wish: str, a: Attraction) -> bool:
        w, name = wish.strip().lower(), a.name.lower()
        return bool(w) and (w in name or name in w or (a.must_have and same_city(a.city, wish)))

    for a in state.attractions:
        a.need_by = [t.id for t in state.travelers if any(asked(w, a) for w in t.need)]
        a.want_by = [t.id for t in state.travelers if t.id not in a.need_by and any(asked(w, a) for w in t.want)]
    for a in state.attractions:
        a.must_have = bool(a.need_by)


def attractions_task(state: TripState, who: Traveler | None = None) -> str:
    cities = ", ".join(dict.fromkeys(s.city for s in state.route.segments))
    requests = "\n".join(
        f"{wish_id}: {text} (needed by: {', '.join(state.names(need)) or 'nobody'}; wanted by: "
        f"{', '.join(state.names(want)) or 'nobody'})"
        for wish_id, text, need, want in wishes(state)
    ) or "(nobody asked for anything specific)"
    # The more the travelers asked for themselves, the fewer extras the plan has room for.
    extras = max(1, SUGGESTIONS[state.request.pace] - sum(not need for _, _, need, _ in wishes(state)))
    return (f"{brief(state)}\n\nPlan attractions for the whole group. These are the travelers' requests:\n{requests}\n\n"
            "Cover every request someone needs, and as many wanted ones as you can. Give each attraction the "
            "wish_ids it covers; if a request is a city or region, pick its one or two top sights and give "
            f"both that wish id. Then suggest up to {extras} more, with empty wish_ids, "
            "that fit this group, the weather on these dates, popularity, and being close to what is already "
            "planned. For each one find the adult ticket price "
            "in USD, opening hours, closed weekdays, typical visit length and booking advice. Work quickly: "
            "one web_research per attraction is enough, and use browse_page only when a search result lacks "
            "the price or hours. Every source_url must be a URL your tools returned. "
            f"Each attraction's city must be one of: {cities}.")


# --- transport -----------------------------------------------------------------

class LegOut(BaseModel):
    kind: Literal["intercity", "airport_transfer", "local_pass", "rental_car"]
    from_place: str = Field(description="City or airport; empty for local_pass and rental_car")
    to_place: str = Field(description="City or airport; empty for local_pass and rental_car")
    mode: str = Field(description="e.g. Shinkansen Nozomi, Narita Express, Suica IC card")
    duration_minutes: int = Field(description="Travel time; 0 for passes and rentals")
    price_usd: float = Field(description="USD per person, or for the whole rental")
    notes: str
    source_url: str = Field(description="URL from your tools where this price was found")


class TransportOut(BaseModel):
    most_visitors_use: str = Field(description="What most visitors use to get around, e.g. trains and metro")
    because: str = Field(description='Finish the sentence "Most visitors here use this because ..."')
    alternative: str = Field(description="The main alternative, e.g. rental car")
    rideshare_note: str = Field(description="Whether rideshare is common there, one sentence")
    source_urls: list[str] = Field(description="URLs from web_research backing the claim")
    legs: list[LegOut] = Field(description="One entry per trip the traveler makes, plus passes")


async def build_transport(state: TripState, ctx: RunContext, out: TransportOut) -> TransportPlan:
    problems, legs = [], []
    sources = _sources(ctx, out.source_urls)
    if not sources:
        problems.append("the most-visitors-use claim needs source_urls returned by web_research")
    for leg in out.legs:
        label = f"{leg.mode} {leg.from_place} to {leg.to_place}".strip()
        source = ctx.source(leg.source_url)
        if source is None:
            problems.append(f"{label}: source_url was not returned by your tools")
            continue
        if not 0 <= leg.price_usd <= 2000 or (leg.kind == "intercity" and (leg.price_usd <= 0 or leg.duration_minutes <= 0)):
            problems.append(f"{label}: ${leg.price_usd:.0f} / {leg.duration_minutes} min is not plausible")
        legs.append(TransportLeg(id=new_id("l"), per_person=leg.kind != "rental_car", source=source,
                                 **leg.model_dump(exclude={"source_url"})))

    unused = [leg for leg in legs if leg.kind == "intercity"]
    plan = stay_plan(state)
    for (a, _, day), (b, _, _) in zip(plan, plan[1:]):
        if same_city(a, b):
            continue
        match = next((leg for leg in unused if {leg.from_place.lower(), leg.to_place.lower()} == {a.lower(), b.lower()}), None)
        if match is None:
            problems.append(f"no intercity leg for {a} to {b} on {day}")
        else:
            unused.remove(match)
    if state.transport_override == "rental_car" and not any(leg.kind == "rental_car" for leg in legs):
        problems.append("the traveler asked for a rental car: add a rental_car leg priced for the whole trip")
    if problems:
        raise Rejected(problems)
    return TransportPlan(
        common_choice=CommonChoice(choice=out.most_visitors_use, because=out.because,
                                   alternative=out.alternative, sources=sources),
        rideshare_note=out.rideshare_note, legs=legs,
    )


def transport_task(state: TripState, who: Traveler | None = None) -> str:
    plan = stay_plan(state)
    hops = "; ".join(f"{a} to {b} on {day}" for (a, _, day), (b, _, _) in zip(plan, plan[1:]) if not same_city(a, b))
    override = ("The group has asked for a rental car: add a rental_car leg priced for the whole trip, "
                "but still report what most visitors use. ") if state.transport_override else ""
    return (f"{brief(state)}\n\nFirst use web_research to find how most visitors get around "
            f"{state.request.destination} (trains and transit, rental car, or rideshare) and whether rideshare "
            f"is common. Keep the source URLs. {override}Then price each leg this trip needs, one entry per "
            f"trip: intercity legs ({hops or 'none'}); an airport_transfer from the arrival airport to "
            f"{plan[0][0]} and one back for the flight home; and a local_pass covering daily transit for "
            f"{state.request.days} days. Prices are USD per person.")


# --- weather (no LLM: Open-Meteo only) -----------------------------------------

async def fetch_weather(state: TripState) -> list[DayWeather]:
    days = []
    for i, (city, check_in, check_out) in enumerate(plan := stay_plan(state)):
        last = check_out if i == len(plan) - 1 else check_out - timedelta(days=1)
        for row in await places.daily_weather(city, check_in, last):
            rain = row["precip_prob"] or 0
            days.append(DayWeather(
                day=row["day"], city=city, high_c=row["high_c"], low_c=row["low_c"], precip_prob=rain,
                kind=row["kind"], summary="Likely rain" if rain >= 60 else "Some chance of rain" if rain >= 30 else "Mostly dry",
                source=Source(url=row["url"], title="Open-Meteo", evidence_url=row["evidence_url"]),
            ))
    return days


# --- what the orchestrator's reviewer is shown: the whole result, compactly ---------

def review_flights(state: TripState, plan: FlightPlan) -> str:
    return "\n".join(
        f"{i}. {o.airline}, ${o.price_usd:,.0f}, leaves {o.depart_at:%b %d %H:%M}, lands {o.destination} "
        f"{o.arrive_at:%b %d %H:%M}, {o.duration_minutes // 60}h{o.duration_minutes % 60:02d}, {o.stops} stop(s). {o.tradeoff}"
        for i, o in enumerate(plan.options, 1))


def review_lodging(state: TripState, plan: LodgingPlan) -> str:
    lines = [f"Most travelers pick {plan.common_choice.choice} because {plan.common_choice.because}. "
             "Each traveler gets their own room from these options, by their own budget."]
    for stay in plan.stays:
        prices = sorted(o.price_total_usd / max(o.nights, 1) for o in stay.options)
        room = stay.selected
        lines.append(f"{stay.city} {stay.check_in} to {stay.check_out}: top pick {room.name} ({room.kind}, "
                     f"{room.neighborhood}, ${room.price_total_usd / max(room.nights, 1):,.0f} a night, rated {room.rating}). "
                     f"{len(stay.options)} options from ${prices[0]:,.0f} to ${prices[-1]:,.0f} a night. {stay.reasoning}")
    return "\n".join(lines)


def review_attractions(state: TripState, found: list[Attraction]) -> str:
    return "\n".join(
        f"- {a.name} ({a.city}): {a.duration_minutes} min, ${a.ticket_price_usd:,.0f}, "
        f"{f'{a.opens:%H:%M}-{a.closes:%H:%M}' if a.opens and a.closes else 'always open'}; "
        f"needed by {', '.join(state.names(a.need_by)) or 'nobody'}, wanted by {', '.join(state.names(a.want_by)) or 'nobody'}"
        for a in found)


def review_transport(state: TripState, plan: TransportPlan) -> str:
    lines = [f"Most visitors use {plan.common_choice.choice} because {plan.common_choice.because}. {plan.rideshare_note}"]
    lines += [f"- {leg.kind}: {leg.mode} {leg.from_place} to {leg.to_place}, {leg.duration_minutes} min, ${leg.price_usd:,.0f}"
              for leg in plan.legs]
    return "\n".join(lines)


# --- registry ------------------------------------------------------------------

@dataclass
class Spec:
    name: str
    title: str
    field: str  # attribute the accepted result is written to, on TripState or on the Traveler
    type: Any
    schema: type[BaseModel]
    task: Callable[[TripState, Traveler | None], str]
    build: Callable[[TripState, RunContext, Any], Awaitable[Any]]
    tools: Callable[[Toolbox], list]
    describe: Callable[[Any], str]
    judged: bool = False  # also gets the orchestrator's LLM plausibility-and-fit review
    per_traveler: bool = False  # run once for each traveler, with their own origin and budget
    after: Callable[[TripState], None] | None = None  # runs once the result is stored
    after_fallback: Callable[[TripState], None] | None = None  # extra step when a saved result is used
    review: Callable[[TripState, Any], str] | None = None  # what the reviewer is shown; defaults to describe()

    def dump(self, value) -> str:
        return TypeAdapter(self.type).dump_json(value).decode()

    def load(self, payload: str):
        return TypeAdapter(self.type).validate_json(payload)


SPECS = {s.name: s for s in [
    Spec("profile", "Profile agent", "profile", TravelerProfile, ProfileOut,
         lambda s, who: f"{brief(s)}\n\nBuild the host's traveler profile from the request.",
         build_profile, lambda t: [], lambda p: p.summary),
    Spec("route", "Route planner", "route", RoutePlan, RouteOut,
         lambda s, who: (f"{brief(s)}\n\nDecide which cities the group sleeps in and for how many nights so "
                         "everything anyone needs to see is reachable. Start in the city where the international "
                         "flights land and end there too, so everyone can fly home. Nights must total the trip "
                         "days minus arrival_day_offset."),
         build_route, lambda t: [], lambda r: " → ".join(f"{s.city} ({s.nights}n)" for s in r.segments)),
    Spec("timeframe", "Timeframe & weather agent", "windows", list[DateWindow], TimeframeOut, timeframe_task,
         build_timeframe, lambda t: [t.web_research, t.window_outlook],
         lambda ws: "; ".join(f"{w.start:%b %d}–{w.end:%b %d}" for w in ws)),
    Spec("flight", "Flight agent", "flights", FlightPlan, FlightsOut, flights_task, build_flights,
         lambda t: [t.search_flights],
         lambda f: f"{len(f.options)} options; best is {f.selected.airline} at ${f.selected.price_usd:,.0f}",
         judged=True, per_traveler=True, review=review_flights),
    Spec("lodging", "Lodging agent", "lodging", LodgingPlan, LodgingOut, lodging_task, build_lodging,
         lambda t: [t.web_research, t.read_source, t.search_hotels, t.search_airbnb],
         lambda p: "; ".join(f"{s.city}: {len(s.options)} options from ${min(o.price_total_usd for o in s.options):,.0f}"
                             for s in p.stays),
         judged=True, after=assign_rooms, review=review_lodging),
    Spec("attractions", "Attractions agent", "attractions", list[Attraction], AttractionsOut, attractions_task,
         build_attractions, lambda t: [t.web_research, t.browse_page],
         lambda a: f"{len(a)} attractions, {sum(x.must_have for x in a)} needed by someone",
         judged=True, review=review_attractions, after_fallback=relink_wishes),
    Spec("transport", "Transport agent", "transport", TransportPlan, TransportOut, transport_task, build_transport,
         lambda t: [t.web_research, t.read_source],
         lambda p: f"{p.common_choice.choice}; {len(p.legs)} legs, ${sum(x.price_usd for x in p.legs):,.0f}",
         judged=True, review=review_transport),
]}
