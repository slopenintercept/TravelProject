"""validate_itinerary: the deterministic constraint checker.

Every change to a trip (agent result, review-screen swap, calendar drag) ends with
a call to this. It never calls an LLM.
"""

from __future__ import annotations

from .budget import compute_budget, optimize_budget
from .geo import same_city, travel_minutes
from .models import TripState, Violation
from .scheduler import build_frames, schedule, stay_plan, to_min


def validate_itinerary(state: TripState) -> list[Violation]:
    """Check the plan against everyone's flights, lodging, opening hours, travel times and budgets."""
    out: list[Violation] = []
    seen: set[tuple] = set()

    def report(code: str, message: str, item_ids: tuple[str, ...] = ()) -> None:
        if (code, item_ids or message) not in seen:  # a clash two travelers share is reported once
            seen.add((code, item_ids or message))
            out.append(Violation(code=code, message=message, item_ids=list(item_ids)))

    attractions = {a.id: a for a in state.attractions}
    frames = {f.day: f for f in build_frames(state)}
    group = len(state.travelers) > 1

    # Each traveler lands on the trip's arrival day and has a room for every night.
    plan = stay_plan(state) if state.dates and state.route else []
    for t in state.travelers:
        who = f"{t.name}: " if group else ""
        if t.flights and state.dates and t.flights.selected.arrive_at.date() != state.dates.arrival:
            report("ARRIVAL_MISMATCH", f"{who}the flight lands {t.flights.selected.arrive_at.date()}, "
                                       f"but the trip starts on the ground {state.dates.arrival}.")
        if not (t.lodging and t.lodging.stays and plan):
            continue
        stays = t.lodging.stays
        if stays[0].check_in != plan[0][1]:
            report("CHECKIN_MISMATCH", f"{who}first check-in is {stays[0].check_in} but the group arrives {plan[0][1]}.")
        if stays[-1].check_out != state.dates.end:
            report("CHECKOUT_MISMATCH", f"{who}last check-out is {stays[-1].check_out} but the flight home is {state.dates.end}.")
        for a, b in zip(stays, stays[1:]):
            if a.check_out != b.check_in:
                report("LODGING_GAP", f"{who}no lodging between {a.city} check-out ({a.check_out}) and {b.city} check-in ({b.check_in}).")
        for stay in stays:
            room = stay.selected
            if (room.check_in, room.check_out) != (stay.check_in, stay.check_out):
                report("LODGING_DATES", f"{who}{room.name} was priced for {room.check_in} to {room.check_out}, not the planned stay.")

    visits = [i for i in state.itinerary if i.kind == "attraction"]

    # Nobody can be in two places at once, and each person needs time to get between stops.
    for t in state.travelers:
        mine: dict = {}
        for item in visits:
            if t.id in item.travelers:
                mine.setdefault(item.day, []).append(item)
        for day, items in mine.items():
            items.sort(key=lambda i: i.start)
            latest = items[0]
            for prev, item in zip(items, items[1:]):
                if item.start < latest.end:
                    report("OVERLAP", f"{day:%a %b %d}: {latest.title} ({latest.start:%H:%M}-{latest.end:%H:%M}) "
                                      f"overlaps {item.title} (starts {item.start:%H:%M}).", (latest.id, item.id))
                elif prev.ref_id in attractions and item.ref_id in attractions:
                    need = travel_minutes(attractions[prev.ref_id], attractions[item.ref_id])
                    gap = to_min(item.start) - to_min(prev.end)
                    if gap < need:
                        report("TRAVEL_TIME", f"{day:%a %b %d}: {gap} min between {prev.title} and {item.title}, "
                                              f"but the trip takes about {need} min.", (prev.id, item.id))
                if item.end > latest.end:
                    latest = item

    for item in visits:
        day, frame = item.day, frames.get(item.day)
        if frame is None:
            report("FLIGHT_CONFLICT", f"{item.title} is on {day:%a %b %d}, outside the trip dates.", (item.id,))
            continue
        if to_min(item.start) < frame.start or to_min(item.end) > frame.end:
            kinds = {f.kind for f in frame.fixed}
            flight = bool(kinds & {"arrival", "departure"})
            blocker = "the flights" if flight else "intercity travel" if kinds else "the day's hours"
            report("FLIGHT_CONFLICT" if flight else "TRAVEL_CONFLICT" if kinds else "OUTSIDE_DAY",
                   f"{day:%a %b %d}: {item.title} ({item.start:%H:%M}-{item.end:%H:%M}) conflicts with {blocker}.", (item.id,))
        if not same_city(item.city, frame.city):
            report("WRONG_CITY", f"{day:%a %b %d}: {item.title} is in {item.city} but the group is in "
                                 f"{frame.city or 'no booked city'}.", (item.id,))
        a = attractions.get(item.ref_id)
        if a is None:
            continue
        if day.weekday() in a.closed_weekdays:
            report("CLOSED_DAY", f"{a.name} is closed on {day:%A}s.", (item.id,))
        if (a.opens and item.start < a.opens) or (a.closes and item.end > a.closes):
            hours = f"{a.opens:%H:%M}-{a.closes:%H:%M}" if a.opens and a.closes else "its opening hours"
            report("OPENING_HOURS", f"{day:%a %b %d}: {a.name} is scheduled {item.start:%H:%M}-{item.end:%H:%M}, "
                                    f"outside {hours}.", (item.id,))

    # Everything someone needs to see is on the plan, and they are the ones going.
    if state.itinerary:
        going = {i.ref_id: i.travelers for i in visits}
        for a in state.attractions:
            if not (a.must_have and a.included):
                continue
            missing = state.names([t for t in a.need_by if t not in going.get(a.id, [])])
            if a.id not in going:
                report("MUST_HAVE_MISSING", f"Must-see {a.name} is not on the itinerary.")
            elif missing:
                report("MUST_HAVE_MISSING", f"{' and '.join(missing)} need{'s' * (len(missing) == 1)} to see {a.name} but "
                                            f"{'is' if len(missing) == 1 else 'are'} not going.")

    for t in state.travelers:
        budget = compute_budget(state, t)
        if budget.remaining_usd < 0:
            who = f"{t.name}'s plan" if group else "Plan"
            report("OVER_BUDGET", f"{who} costs ${budget.spent_usd:,.0f}, ${-budget.remaining_usd:,.0f} over "
                                  f"the ${budget.total_usd:,.0f} budget.")
    return out


def rebudget(state: TripState) -> None:
    state.budgets = {t.id: compute_budget(state, t) for t in state.travelers}
    state.budget_proposals = {t.id: p for t in state.travelers if (p := optimize_budget(state, t))}


def replan(state: TripState) -> None:
    """Schedule -> budget -> validate. Run after every change to the trip."""
    schedule(state)
    rebudget(state)
    state.violations = validate_itinerary(state)
