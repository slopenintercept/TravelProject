from datetime import date, time

from tripwright.models import ItineraryItem
from tripwright.scheduler import schedule
from tripwright.validate import replan, validate_itinerary


def codes(state):
    return {v.code for v in validate_itinerary(state)}


def item(state, ref_id):
    return next(i for i in state.itinerary if i.ref_id == ref_id)


def test_scheduled_plan_is_valid(state):
    replan(state)
    assert state.violations == []
    assert state.unscheduled == []
    assert state.budgets["p1"].spent_usd == 1250 + 330 + 200 + 90 + 60 + 28 + 4 + 95 + 95 + 40


def test_overlap(state):
    schedule(state)
    a, b = item(state, "a_sensoji"), item(state, "a_teamlab")
    b.day, b.start, b.end = a.day, a.start, a.end
    assert "OVERLAP" in codes(state)


def test_travel_time_between_stops(state):
    schedule(state)
    a, b = item(state, "a_sensoji"), item(state, "a_teamlab")
    b.day, b.start, b.end = a.day, a.end, time(a.end.hour + 2, a.end.minute)
    assert "TRAVEL_TIME" in codes(state)


def test_opening_hours_and_closed_day(state):
    schedule(state)
    kinkaku = item(state, "a_kinkaku")
    kinkaku.start, kinkaku.end = time(17, 30), time(18, 45)
    assert "OPENING_HOURS" in codes(state)

    state.attractions[-1].closed_weekdays = [kinkaku.day.weekday()]
    assert "CLOSED_DAY" in codes(state)


def test_conflict_with_arrival_and_departure(state):
    schedule(state)
    sensoji = item(state, "a_sensoji")
    sensoji.day, sensoji.start, sensoji.end = date(2026, 11, 11), time(14, 0), time(15, 30)
    assert "FLIGHT_CONFLICT" in codes(state)

    # Flight home is 17:30: leave for the airport by 13:30.
    sensoji.day, sensoji.start, sensoji.end = date(2026, 11, 17), time(13, 0), time(14, 30)
    assert "FLIGHT_CONFLICT" in codes(state)


def test_conflict_with_intercity_travel(state):
    schedule(state)
    kinkaku = item(state, "a_kinkaku")
    # Nov 14 morning is the Shinkansen to Kyoto (09:00 + 135 min ride + 45 min overhead).
    kinkaku.day, kinkaku.start, kinkaku.end = date(2026, 11, 14), time(9, 30), time(10, 45)
    assert "TRAVEL_CONFLICT" in codes(state)


def test_wrong_city(state):
    schedule(state)
    kinkaku = item(state, "a_kinkaku")
    kinkaku.day = date(2026, 11, 12)  # a Tokyo day
    assert "WRONG_CITY" in codes(state)


def test_lodging_must_cover_the_trip(state):
    stays = state.travelers[0].lodging.stays
    stays[0].check_in = date(2026, 11, 12)
    assert {"CHECKIN_MISMATCH", "LODGING_DATES"} <= codes(state)
    stays[0].check_in = date(2026, 11, 11)
    stays[1].check_in = date(2026, 11, 15)
    assert "LODGING_GAP" in codes(state)


def test_must_have_missing(state):
    schedule(state)
    state.itinerary = [i for i in state.itinerary if i.ref_id != "a_disney"]
    assert "MUST_HAVE_MISSING" in codes(state)


def test_over_budget(state):
    state.travelers[0].budget_usd = 2000
    replan(state)
    assert "OVER_BUDGET" in {v.code for v in state.violations}


def test_unknown_item_dates_are_rejected(state):
    schedule(state)
    state.itinerary.append(ItineraryItem(
        id="x", day=date(2026, 11, 20), start=time(10), end=time(11), kind="attraction",
        title="After the trip", city="Tokyo", ref_id="a_sensoji",
    ))
    assert "FLIGHT_CONFLICT" in codes(state)
