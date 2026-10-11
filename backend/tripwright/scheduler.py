"""Places attractions into days for the whole group. Deterministic: no LLM calls in here.

`build_frames` turns the facts (everyone's flights, the route, intercity legs) into one
frame per day: which city the group is in and the free window around the fixed blocks.
The validator reuses the same frames, so both agree on what "free time" means.

The goal is the fewest itineraries that meet the most preferences: everything goes on
one shared itinerary while it fits. Only when something a traveler asked for does not
fit do they split off for it, during an activity they did not ask for, and regroup after.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time, timedelta

from .geo import same_city, travel_minutes
from .models import Attraction, ItineraryItem, TripState, Unscheduled, new_id

DAY_START = time(9, 0)
DAY_END = time(21, 0)
ARRIVAL_BUFFER_MIN = 150  # immigration, bags, transfer to the hotel
DEPARTURE_BUFFER_MIN = 180  # at the airport 3h before an international flight
STATION_OVERHEAD_MIN = 45  # hotel -> station and station -> hotel around an intercity leg
DEFAULT_INTERCITY_MIN = 180
DEFAULT_AIRPORT_TRANSFER_MIN = 60
UNKNOWN_RETURN_CUTOFF = time(12, 0)  # used until a return flight time is verified
LIKELY_RAIN = 50  # percent

PACE = {
    "relaxed": {"max_items": 2, "max_minutes": 5 * 60},
    "balanced": {"max_items": 3, "max_minutes": 8 * 60},
    "packed": {"max_items": 5, "max_minutes": 11 * 60},
}


def to_min(t: time) -> int:
    return t.hour * 60 + t.minute


def to_time(minutes: int) -> time:
    minutes = max(0, min(minutes, 23 * 60 + 59))
    return time(minutes // 60, minutes % 60)


def stay_plan(state: TripState) -> list[tuple[str, date, date]]:
    """(city, check-in, check-out) for each route segment. Every traveler shares it."""
    plan, day = [], state.dates.arrival
    for segment in state.route.segments:
        plan.append((segment.city, day, day + timedelta(days=segment.nights)))
        day += timedelta(days=segment.nights)
    return plan


@dataclass
class DayFrame:
    day: date
    city: str
    start: int  # minutes after midnight; start >= end means no free time
    end: int
    fixed: list[ItineraryItem] = field(default_factory=list)


def _leg_minutes(state: TripState, kind: str, a: str = "", b: str = "", default: int = 0) -> int:
    for leg in state.transport.legs if state.transport else []:
        if leg.kind != kind or not leg.included or not leg.duration_minutes:
            continue
        ends = {leg.from_place.lower(), leg.to_place.lower()}
        if kind != "intercity" or (a.lower() in ends and b.lower() in ends):
            return leg.duration_minutes
    return default


def build_frames(state: TripState) -> list[DayFrame]:
    """One frame per day on the ground, from the last traveler landing to the first flight home."""
    flights = [t.flights.selected for t in state.travelers if t.flights]
    if not (state.dates and state.route and flights):
        return []
    everyone = [t.id for t in state.travelers]
    plan = stay_plan(state)
    first_day, last_day, gateway = state.dates.arrival, state.dates.end, plan[0][0]
    group = len(flights) > 1

    def fixed(day: date, start: int, end: int, kind: str, title: str, city: str) -> ItineraryItem:
        return ItineraryItem(id=new_id("it"), day=day, start=to_time(start), end=to_time(end), kind=kind,
                             title=title, city=city, travelers=everyone, locked=True)

    frames = []
    for offset in range((last_day - first_day).days + 1):
        day = first_day + timedelta(days=offset)
        city = next((c for c, check_in, check_out in plan if check_in <= day < check_out), plan[-1][0])
        frame = DayFrame(day, city, to_min(DAY_START), to_min(DAY_END))
        frames.append(frame)

        if day == first_day:
            # The group can start once the last person has landed (a later date counts as past midnight).
            landed = max(to_min(f.arrive_at.time()) + 1440 * (f.arrive_at.date() - first_day).days for f in flights)
            landed = max(landed, 0)
            frame.start = max(frame.start, landed + ARRIVAL_BUFFER_MIN)
            title = ("Everyone has landed; transfer to the hotels" if group
                     else f"Land at {flights[0].destination} and transfer to the hotel")
            frame.fixed.append(fixed(day, landed, landed + ARRIVAL_BUFFER_MIN, "arrival", title, city))

        previous = next((c for c, _, check_out in plan if check_out == day), None)
        if previous and day != last_day and not same_city(previous, city):
            ride = _leg_minutes(state, "intercity", previous, city, DEFAULT_INTERCITY_MIN)
            arrive = to_min(DAY_START) + ride + STATION_OVERHEAD_MIN
            frame.start = max(frame.start, arrive)
            frame.fixed.append(fixed(day, to_min(DAY_START), arrive, "travel", f"{previous} → {city}", city))

        if day == last_day:
            transfer = _leg_minutes(state, "airport_transfer", default=DEFAULT_AIRPORT_TRANSFER_MIN)
            known = [to_min(f.return_depart_at.time()) for f in flights if f.return_depart_at]
            if len(known) == len(flights):
                takeoff = min(known)  # the first flight home sets the cutoff for group plans
                title = "Head to the airport for the flights home" if group else f"Head to {flights[0].destination} for the flight home"
            else:
                takeoff = to_min(UNKNOWN_RETURN_CUTOFF) + DEPARTURE_BUFFER_MIN + transfer
                title = "Flight home (return time not verified yet)"
            leave = takeoff - DEPARTURE_BUFFER_MIN - transfer
            frame.end = min(frame.end, leave)
            if not same_city(city, gateway):
                ride = _leg_minutes(state, "intercity", city, gateway, DEFAULT_INTERCITY_MIN)
                frame.end = min(frame.end, leave - ride - STATION_OVERHEAD_MIN)
                frame.fixed.append(
                    fixed(day, leave - ride - STATION_OVERHEAD_MIN, leave, "travel", f"{city} → {gateway}", gateway)
                )
            frame.fixed.append(fixed(day, leave, takeoff, "departure", title, gateway))
    return frames


def _rain_rank(state: TripState, a: Attraction, day: date) -> float:
    """Outdoor must-sees get the driest day outright; other outdoor stops just avoid likely rain."""
    rain = next((w.precip_prob or 0 for w in state.weather if w.day == day), 0)
    if not a.outdoor:
        return 0
    return rain if a.must_have else rain >= LIKELY_RAIN


def schedule(state: TripState) -> None:
    """Rebuild `state.itinerary`, `state.unscheduled` and `state.plan_note` from the current facts.

    Shared pass: what the most travelers need goes first, then longer visits. Outdoor
    must-sees get the driest day in their city and other outdoor stops avoid likely rain;
    after that the least-loaded day wins, full days before arrival, travel and departure
    days. Items the user pinned to a day stay on that day.

    Split pass: something only some travelers asked for that did not fit is placed for
    just those travelers, alongside a group activity none of them asked for.
    """
    frames = build_frames(state)
    everyone = [t.id for t in state.travelers]
    limits = PACE[state.request.pace]
    by_id = {a.id: a for a in state.attractions}
    pins = {i.ref_id: i.day for i in state.itinerary if i.pinned and i.kind == "attraction"}
    cursor = {f.day: f.start for f in frames}
    placed: dict[date, list[ItineraryItem]] = {f.day: [] for f in frames}  # the shared sequence per day
    splits: list[ItineraryItem] = []
    unscheduled = []

    def item(a: Attraction, day: date, start: int, who: list[str], pinned: bool = False) -> ItineraryItem:
        return ItineraryItem(
            id=new_id("it"), day=day, start=to_time(start), end=to_time(start + a.duration_minutes), kind="attraction",
            title=a.name, city=a.city, ref_id=a.id, cost_usd=a.ticket_price_usd * len(who), travelers=who, pinned=pinned,
        )

    def open_at(a: Attraction, f: DayFrame, start: int, limit: int) -> int | str:
        """The start time once opening hours are applied, or why it can't go there."""
        if not same_city(f.city, a.city):
            return f"the group is in {f.city or 'transit'} that day, and it is in {a.city}"
        if f.day.weekday() in a.closed_weekdays:
            return f"closed on {f.day:%A}s"
        start = max(start, to_min(a.opens)) if a.opens else start
        if start + a.duration_minutes > min(limit, to_min(a.closes) if a.closes else limit):
            return "not enough free time while it is open"
        return start

    def fit_shared(a: Attraction, f: DayFrame, pinned: bool) -> int | str:
        after = cursor[f.day] + (travel_minutes(by_id[placed[f.day][-1].ref_id], a) if placed[f.day] else 0)
        start = open_at(a, f, after, f.end)
        if isinstance(start, str) or pinned or a.must_have:
            return start
        used = sum(by_id[i.ref_id].duration_minutes for i in placed[f.day])
        if len(placed[f.day]) >= limits["max_items"] or used + a.duration_minutes > limits["max_minutes"]:
            return f"days in {a.city} are already full for a {state.request.pace} pace"
        return start

    def fit_split(a: Attraction, f: DayFrame, who: list[str]) -> tuple[int, ItineraryItem] | None:
        """A slot for `who` alone, during a shared activity none of them asked for or that they skip."""
        for host in placed[f.day]:
            during = by_id[host.ref_id]
            free = all(t in during.skip_by or (t in host.travelers and t not in during.need_by + during.want_by)
                       for t in who)
            if not free or not set(host.travelers) - set(who):
                continue
            hop = travel_minutes(during, a)
            start = open_at(a, f, to_min(host.start) + hop, to_min(host.end) - hop)
            if not isinstance(start, str):
                return start, host
        return None

    todo = sorted(
        (a for a in state.attractions if a.included),
        key=lambda a: (a.id not in pins, -len(a.need_by), not a.must_have, -len(a.want_by), -a.duration_minutes),
    )
    leftover: list[tuple[Attraction, str]] = []
    for a in todo:
        going = [t for t in everyone if t not in a.skip_by]  # whoever skips it is free meanwhile
        if not going:
            continue
        pinned = a.id in pins
        days = [f for f in frames if (f.day == pins[a.id] if pinned else same_city(f.city, a.city))]
        days.sort(key=lambda f: (_rain_rank(state, a, f.day), len(placed[f.day]), bool(f.fixed), f.day))
        reason = f"no day in {a.city} on this trip"
        for f in days:
            start = fit_shared(a, f, pinned)
            if isinstance(start, str):
                reason = start
                continue
            new = item(a, f.day, start, going, pinned)
            placed[f.day].append(new)
            cursor[f.day] = to_min(new.end)
            break
        else:
            leftover.append((a, reason))

    for a, reason in leftover:
        who = [t for t in everyone if t in (a.need_by or a.want_by)]
        slot = None
        if who and len(who) < len(everyone):
            for f in (f for f in frames if same_city(f.city, a.city)):
                slot = fit_split(a, f, who)
                if slot:
                    start, host = slot
                    host.travelers = [t for t in host.travelers if t not in who]
                    host.cost_usd = by_id[host.ref_id].ticket_price_usd * len(host.travelers)
                    splits.append(item(a, f.day, start, who))
                    break
        if slot is None:
            unscheduled.append(Unscheduled(attraction_id=a.id, name=a.name, reason=reason,
                                           wanted_by=a.need_by + [t for t in a.want_by if t not in a.need_by]))

    items = [i for f in frames for i in f.fixed] + [i for day in placed.values() for i in day] + splits
    state.itinerary = sorted(items, key=lambda i: (i.day, i.start))
    state.unscheduled = unscheduled
    state.plan_note = _plan_note(state, splits)


def _plan_note(state: TripState, splits: list[ItineraryItem]) -> str:
    if len(state.travelers) < 2 or not state.itinerary:
        return ""
    skipped = {a.id: a.skip_by for a in state.attractions}
    moments = [
        f"{' and '.join(state.names(who))} skip{'s' * (len(who) == 1)} {i.title} on {i.day:%a %b} {i.day.day}"
        for i in state.itinerary if i.kind == "attraction" and i not in splits
        and (who := [t for t in skipped.get(i.ref_id, []) if t not in i.travelers])
    ] + [
        f"{' and '.join(state.names(s.travelers))} split{'s' * (len(s.travelers) == 1)} off for {s.title} on {s.day:%a %b} {s.day.day}"
        for s in splits
    ]
    if not moments:
        return "One shared itinerary: everything everyone asked for fits together."
    paths = {tuple(i.id for i in state.itinerary if t.id in i.travelers) for t in state.travelers}
    return f"{len(paths)} itineraries that regroup: {'; '.join(moments)}."
