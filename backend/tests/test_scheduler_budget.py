from datetime import date

from tripwright.budget import apply_swaps, compute_budget, optimize_budget
from tripwright.scheduler import build_frames, schedule, to_time
from tripwright.validate import replan


def day_of(state, ref_id):
    return next(i.day for i in state.itinerary if i.ref_id == ref_id)


def test_frames_follow_flights_and_stays(state):
    frames = {f.day: f for f in build_frames(state)}
    assert [f.city for f in frames.values()] == ["Tokyo"] * 3 + ["Kyoto"] * 2 + ["Tokyo"] * 2
    assert to_time(frames[date(2026, 11, 11)].start).isoformat() == "17:55:00"  # lands 15:25 + 150 min
    assert to_time(frames[date(2026, 11, 14)].start).isoformat() == "12:00:00"  # Shinkansen morning
    assert to_time(frames[date(2026, 11, 17)].end).isoformat() == "13:30:00"  # 17:30 flight - 3h - 60 min


def test_outdoor_must_have_gets_the_driest_day(state):
    schedule(state)
    # Tokyo days with a full window: Nov 12 (70% rain), Nov 13 (10%), Nov 16 (40%).
    assert day_of(state, "a_disney") == date(2026, 11, 13)


def test_pace_limits_items_per_day(state):
    state.request.pace = "relaxed"
    for a in state.attractions:
        a.must_have, a.duration_minutes = False, 60
    schedule(state)
    per_day = {}
    for i in state.itinerary:
        if i.kind == "attraction":
            per_day[i.day] = per_day.get(i.day, 0) + 1
    assert max(per_day.values()) <= 2


def test_pinned_item_stays_on_its_day(state):
    schedule(state)
    sensoji = next(i for i in state.itinerary if i.ref_id == "a_sensoji")
    sensoji.day, sensoji.pinned = date(2026, 11, 16), True
    schedule(state)
    assert day_of(state, "a_sensoji") == date(2026, 11, 16)


def test_closed_weekday_is_avoided_or_reported(state):
    kinkaku = state.attractions[-1]
    kinkaku.closed_weekdays = [date(2026, 11, 14).weekday()]
    schedule(state)
    assert day_of(state, "a_kinkaku") == date(2026, 11, 15)

    kinkaku.closed_weekdays = list(range(7))
    schedule(state)
    assert [u.attraction_id for u in state.unscheduled] == ["a_kinkaku"]


def test_optimizer_is_quiet_when_within_budget(state):
    assert optimize_budget(state, state.travelers[0]) is None


def test_optimizer_prefers_the_fewest_swaps(state):
    alex = state.travelers[0]
    alex.budget_usd = 2100  # plan is 2192; one swap (cheaper flight, -150) fits
    replan(state)
    proposal = state.budget_proposals["p1"]
    assert [(s.category, s.to_id) for s in proposal.swaps] == [("flights", "f2")]
    assert proposal.fits

    apply_swaps(alex, proposal)
    replan(state)
    assert compute_budget(state, alex).remaining_usd >= 0
    assert state.violations == [] and state.budget_proposals == {}


def test_optimizer_skips_a_swap_that_barely_saves_anything(state):
    # 2192 planned, 2050 allowed. Two cheaper rooms (-120, -50) fit in two changes, so the
    # optimizer leaves the flight alone rather than also swapping it to save $2.
    alex = state.travelers[0]
    alex.flights.options[1].price_usd = 1248
    alex.budget_usd = 2050
    replan(state)
    proposal = optimize_budget(state, alex)
    assert proposal.fits
    assert [(s.category, s.action) for s in proposal.swaps] == [("lodging", "swap"), ("lodging", "swap")]


def test_optimizer_leaves_shared_attractions_alone_and_says_when_it_cannot_fit(state):
    alex = state.travelers[0]
    alex.budget_usd = 1840  # cheapest flight and rooms still leave 1872
    replan(state)
    proposal = optimize_budget(state, alex)
    assert {s.category for s in proposal.swaps} == {"flights", "lodging"}
    assert proposal.fits is False and proposal.new_total_usd == 1872


def test_full_days_fill_before_arrival_and_departure_days(state):
    schedule(state)
    # Tokyo has two full days (Nov 12, 13) and three partial ones; both full days get used first.
    tokyo_days = {i.day for i in state.itinerary if i.kind == "attraction" and i.city == "Tokyo"}
    assert {date(2026, 11, 12), date(2026, 11, 13)} <= tokyo_days
