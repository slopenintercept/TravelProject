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
EARLY_START = time(7, 0)  # the earliest an early opener (sumo practice, a fish market) is planned
DAY_END = time(21, 0)
EVENING_FROM = time(17, 0)  # a place opening this late is an evening venue (bars, karaoke, night walks)
EVENING_END = time(23, 30)  # how late an evening venue may run
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
    """How long this ride takes the group: the slowest of the ways its travelers have chosen."""
    found = []
    for leg in [leg for t in state.travelers for leg in t.legs] or (state.transport.legs if state.transport else []):
        if leg.kind != kind or not leg.included or not leg.duration_minutes:
            continue
        ends = {leg.from_place.lower(), leg.to_place.lower()}
        if kind != "intercity" or (a.lower() in ends and b.lower() in ends):
            found.append(leg.duration_minutes)
    return max(found, default=default)


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


def is_evening(a: Attraction) -> bool:
    """Bars, karaoke, night walks: places that open in the evening can run past the usual end of the day."""
    return bool(a.opens) and to_min(a.opens) >= to_min(EVENING_FROM)


def closing_min(a: Attraction) -> int | None:
    """Closing time in minutes after midnight; a bar open 19:00-02:00 closes at 26:00, not at 2 am that morning."""
    if a.closes is None:
        return None
    closes = to_min(a.closes)
    return closes + 1440 if a.opens and closes <= to_min(a.opens) else closes


def day_window(a: Attraction, f: DayFrame) -> tuple[int, int]:
    """When on this day `a` may happen. An ordinary day runs 09:00-21:00; on one that starts then (not arrival or a
    travel morning), an early opener like sumo practice can start before 09:00, and evening venues may run late."""
    start, end = f.start, f.end
    if a.opens and to_min(a.opens) < start and start == to_min(DAY_START):
        start = max(to_min(a.opens), to_min(EARLY_START))  # a shrine open at sunrise still waits until 07:00
    if is_evening(a) and end >= to_min(DAY_END):
        end = to_min(EVENING_END)
    return start, end


def schedule(state: TripState) -> None:
    """Rebuild `state.itinerary`, `state.unscheduled` and `state.plan_note` from the current facts.

    Group activities are ones at least half the group asked for (or the agent's own extras): everyone
    goes, except whoever marked it not for me. Niche activities, which fewer asked for, are only for the
    people who asked.

    Shared pass, group activities: what the most travelers need goes first, then longer visits. Outdoor
    must-sees get the driest day in their city and other outdoor stops avoid likely rain; after that the
    least-loaded day wins, full days before arrival, travel and departure days. Items the user pinned to a
    day stay on that day. Evening venues go last on their day and may run until late.

    Split pass, niche activities and group ones that did not fit: placed for just those who asked,
    alongside a group activity none of them asked for; failing that, on their own while the others have
    free time.
    """
    frames = build_frames(state)
    everyone = [t.id for t in state.travelers]
    limits = PACE[state.request.pace]
    by_id = {a.id: a for a in state.attractions}
    pins = {i.ref_id: i.day for i in state.itinerary if i.pinned and i.kind == "attraction"}
    cursor = {f.day: f.start for f in frames}
    placed: dict[date, list[ItineraryItem]] = {f.day: [] for f in frames}  # the shared sequence per day
    splits: list[ItineraryItem] = []
    hosts: set[str] = set()  # group activities some travelers split off from
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
        earliest, latest = day_window(a, f)
        if start == f.start:  # nothing before it that day: an early opener can start before the usual day
            start = earliest
        start = max(start, to_min(a.opens)) if a.opens else start
        if limit == f.end:
            limit = latest
        closes = closing_min(a)
        if start + a.duration_minutes > min(limit, closes if closes is not None else limit):
            return "not enough free time while it is open"
        return start

    def fit_shared(a: Attraction, f: DayFrame, pinned: bool) -> int | str:
        after = cursor[f.day] + (travel_minutes(by_id[placed[f.day][-1].ref_id], a) if placed[f.day] else 0)
        start = open_at(a, f, after, f.end)
        if isinstance(start, str) or pinned or a.must_have or is_evening(a):  # evenings don't count toward the pace
            return start
        daytime = [i for i in placed[f.day] if not is_evening(by_id[i.ref_id])]
        used = sum(by_id[i.ref_id].duration_minutes for i in daytime)
        if len(daytime) >= limits["max_items"] or used + a.duration_minutes > limits["max_minutes"]:
            return f"days in {a.city} are already full for a {state.request.pace} pace"
        return start

    def leavable(i: ItineraryItem, a: Attraction, who: list[str]) -> bool:
        """For a must-do of theirs, `who` may skip a group activity none of them needs; the others still go."""
        if not a.must_have or i not in placed[i.day] or i.kind != "attraction":
            return False
        during = by_id[i.ref_id]
        return not set(who) & set(during.need_by) and bool(set(i.travelers) - set(who))

    def fit_alone(a: Attraction, f: DayFrame, who: list[str], leave: bool = False) -> int | None:
        """The earliest time on this day when everyone in `who` is free for `a`, whatever the others are doing.
        With `leave`, they may skip group activities none of them needs (a last resort, for a must-do)."""
        busy = sorted((i for i in [*placed[f.day], *splits, *f.fixed]
                       if i.day == f.day and set(i.travelers) & set(who) and not (leave and leavable(i, a, who))),
                      key=lambda i: i.start)
        if not a.must_have:  # wanted, not needed: each of them keeps to the pace
            for t in who:
                theirs = [i for i in busy if i.kind == "attraction" and t in i.travelers and not is_evening(by_id[i.ref_id])]
                if len(theirs) >= limits["max_items"]:
                    return None
        free_from, previous = f.start, None
        for nxt in [*busy, None]:
            hop = travel_minutes(previous, a) if previous else 0
            nxt_hop = travel_minutes(a, by_id[nxt.ref_id]) if nxt and nxt.ref_id in by_id else 30 if nxt else 0
            limit = min(f.end, to_min(nxt.start) - nxt_hop) if nxt else f.end
            start = open_at(a, f, free_from + hop, limit)
            if not isinstance(start, str):
                return start
            if nxt:
                free_from = max(free_from, to_min(nxt.end))
                previous = by_id.get(nxt.ref_id)
        return None

    def asked(a: Attraction) -> list[str]:
        return [t for t in everyone if t in a.need_by + a.want_by and t not in a.skip_by]

    def group_activity(a: Attraction) -> bool:
        return not (a.need_by or a.want_by) or 2 * len(asked(a)) >= len(everyone)

    def place_shared(a: Attraction, who: list[str]) -> str | None:
        """Put `a` on the shared sequence of a day for `who`; the reason it fits nowhere, or None."""
        pinned = a.id in pins
        days = [f for f in frames if (f.day == pins[a.id] if pinned else same_city(f.city, a.city))]
        days.sort(key=lambda f: (_rain_rank(state, a, f.day), len(placed[f.day]), bool(f.fixed), f.day))
        reason = f"no day in {a.city} on this trip"
        for f in days:
            start = fit_shared(a, f, pinned)
            if isinstance(start, str):
                reason = start
                continue
            new = item(a, f.day, start, who, pinned)
            placed[f.day].append(new)
            cursor[f.day] = to_min(new.end)
            return None
        return reason

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
        key=lambda a: (a.id not in pins, is_evening(a), -len(a.need_by), not a.must_have, -len(a.want_by),
                       -a.duration_minutes),
    )
    leftover: list[tuple[Attraction, str]] = []  # placed for just the people who asked, after the group's plan
    for a in todo:
        going = [t for t in everyone if t not in a.skip_by]  # whoever skips it is free meanwhile
        if not going:
            continue
        if not group_activity(a):
            leftover.append((a, ""))
        elif reason := place_shared(a, going):
            leftover.append((a, reason))

    for a, reason in leftover:
        # A group activity that didn't fit falls back to its must-do people, as before; a niche one is for
        # everyone who asked.
        who = asked(a) if not group_activity(a) else [t for t in everyone if t in (a.need_by or a.want_by)]
        # Somebody dragged it to a day: only that day.
        city_days = [f for f in frames if (f.day == pins[a.id] if a.id in pins else same_city(f.city, a.city))]
        slot = None
        if who and len(who) < len(everyone):
            for f in city_days:
                slot = fit_split(a, f, who)
                if slot:
                    start, host = slot
                    host.travelers = [t for t in host.travelers if t not in who]
                    host.cost_usd = by_id[host.ref_id].ticket_price_usd * len(host.travelers)
                    hosts.add(host.id)
                    splits.append(item(a, f.day, start, who, a.id in pins))
                    break
        if slot is None and not group_activity(a) and who:
            # Its own time, whenever all of them are free: other people can be doing something else meanwhile.
            days = sorted(city_days, key=lambda f: (_rain_rank(state, a, f.day), bool(f.fixed), f.day))
            # Everyone who asked, then (for a must-do) just those who need it; skipping a group activity is a last
            # resort. Whoever was only interested and can't make it is listed as missing out, not as the blocker.
            needers = [t for t in who if t in a.need_by]
            groups = [who] + ([needers] if a.must_have and needers and needers != who else [])
            found = next(((f, start, people) for people in groups for leave in (False, True) for f in days
                          if (start := fit_alone(a, f, people, leave)) is not None), None)
            if found:
                f, start, who = found
                new = item(a, f.day, start, who, a.id in pins)
                for left in placed[f.day]:  # group activities they skip for it, or can't reach in time: the others go
                    hop = travel_minutes(a, by_id[left.ref_id])
                    if (set(left.travelers) & set(who) and to_min(left.start) < to_min(new.end) + hop
                            and to_min(new.start) - hop < to_min(left.end)):
                        left.travelers = [t for t in left.travelers if t not in who]
                        left.cost_usd = by_id[left.ref_id].ticket_price_usd * len(left.travelers)
                        hosts.add(left.id)
                splits.append(new)
                continue
            reason = reason or f"no day in {a.city} when {' and '.join(state.names(who))} are all free long enough"
        if slot is None:
            unscheduled.append(Unscheduled(attraction_id=a.id, name=a.name, reason=reason,
                                           wanted_by=a.need_by + [t for t in a.want_by if t not in a.need_by]))

    items = [i for f in frames for i in f.fixed] + [i for day in placed.values() for i in day] + splits
    state.itinerary = sorted(items, key=lambda i: (i.day, i.start))
    state.unscheduled = unscheduled
    state.plan_note = _plan_note(state, splits, hosts)


def _plan_note(state: TripState, splits: list[ItineraryItem], hosts: set[str]) -> str:
    if len(state.travelers) < 2 or not state.itinerary:
        return ""
    skipped = {a.id: a.skip_by for a in state.attractions}
    everyone = {t.id for t in state.travelers}

    def when(i: ItineraryItem) -> str:
        return f"{i.day:%a %b} {i.day.day}"

    def who(ids: list[str]) -> str:
        return " and ".join(state.names(ids))

    moments = []
    for i in state.itinerary:
        if i.kind != "attraction" or i in splits:
            continue
        skip = [t for t in skipped.get(i.ref_id, []) if t not in i.travelers]
        if i.id in hosts or set(i.travelers) | set(skip) == everyone:  # a group activity
            if skip:
                moments.append(f"{who(skip)} skip{'s' * (len(skip) == 1)} {i.title} on {when(i)}")
        else:  # a niche one, in its own time slot
            moments.append(f"{who(i.travelers)} go{'es' * (len(i.travelers) == 1)} to {i.title} on {when(i)}")
    moments += [f"{who(s.travelers)} split{'s' * (len(s.travelers) == 1)} off for {s.title} on {when(s)}"
                for s in splits]
    if not moments:
        return "One shared itinerary: everything everyone asked for fits together."
    paths = {tuple(i.id for i in state.itinerary if t.id in i.travelers) for t in state.travelers}
    return f"{len(paths)} itineraries that regroup: {'; '.join(moments)}."
