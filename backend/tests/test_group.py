"""Group trips: individual flights, lodging and budgets; attractions planned together, with split-offs."""

import asyncio
from datetime import date, datetime, time

import pytest

from tripwright import orchestrator
from tripwright.booking import booking_steps
from tripwright.cards import review_cards
from tripwright.models import Source, TravelerIn, TripRequest
from tripwright.scheduler import build_frames, to_time
from tripwright.specialists import AttractionOut, AttractionsOut, Rejected, build_attractions, wishes
from tripwright.toolbox import RunContext
from tripwright.tools import flights, places
from tripwright.validate import replan

from conftest import attraction


def going(state, ref_id):
    return next(i.travelers for i in state.itinerary if i.ref_id == ref_id)


def test_group_day_starts_after_the_last_arrival_and_ends_before_the_first_flight_home(group):
    sam = group.travelers[1].flights.selected
    sam.arrive_at = datetime(2026, 11, 11, 17, 0)  # Alex lands 15:25
    sam.return_depart_at = datetime(2026, 11, 17, 15, 0)  # Alex leaves 17:30
    frames = {f.day: f for f in build_frames(group)}
    assert to_time(frames[date(2026, 11, 11)].start).isoformat() == "19:30:00"  # 17:00 + 150 min
    assert to_time(frames[date(2026, 11, 17)].end).isoformat() == "11:00:00"  # 15:00 - 3h - 60 min


def test_everything_fits_one_shared_itinerary_when_it_can(group):
    group.attractions.append(attraction("a_ghibli", "Ghibli Museum", "Tokyo", 35.6962, 139.5704, must_have=True,
                                        need_by=["p2"], duration_minutes=150, ticket_price_usd=7))
    replan(group)
    assert group.violations == [] and group.unscheduled == []
    assert all(i.travelers == ["p1", "p2"] for i in group.itinerary)
    assert group.plan_note.startswith("One shared itinerary")


def test_traveler_splits_off_for_a_need_that_does_not_fit_and_regroups(group):
    # Ghibli only opens on Fridays, the day Alex's Disneyland visit takes (it is the driest Tokyo day).
    friday = date(2026, 11, 13).weekday()
    group.attractions.append(attraction(
        "a_ghibli", "Ghibli Museum", "Tokyo", 35.6962, 139.5704, must_have=True, need_by=["p2"], duration_minutes=150,
        ticket_price_usd=7, opens=time(10), closes=time(18), closed_weekdays=[d for d in range(7) if d != friday]))
    replan(group)

    assert group.violations == [] and group.unscheduled == []
    assert going(group, "a_ghibli") == ["p2"]  # Sam goes alone...
    assert going(group, "a_disney") == ["p1"]  # ...while Alex is at Disneyland, which Sam never asked for
    ghibli = next(i for i in group.itinerary if i.ref_id == "a_ghibli")
    disney = next(i for i in group.itinerary if i.ref_id == "a_disney")
    assert ghibli.day == disney.day and disney.start <= ghibli.start and ghibli.end <= disney.end
    assert group.plan_note == "2 itineraries that regroup: Sam splits off for Ghibli Museum on Fri Nov 13."
    # Everything else is still shared.
    assert all(i.travelers == ["p1", "p2"] for i in group.itinerary if i.ref_id not in ("a_ghibli", "a_disney"))


def test_each_traveler_pays_for_their_own_flight_room_and_the_tickets_they_use(group):
    friday = date(2026, 11, 13).weekday()
    group.attractions.append(attraction(
        "a_ghibli", "Ghibli Museum", "Tokyo", 35.6962, 139.5704, must_have=True, need_by=["p2"], duration_minutes=150,
        ticket_price_usd=7, opens=time(10), closes=time(18), closed_weekdays=[d for d in range(7) if d != friday]))
    group.travelers[1].flights.selected_id = "f2"  # Sam flies ANA at 1100
    replan(group)
    alex, sam = group.budgets["p1"], group.budgets["p2"]
    assert alex.by_category == {"flights": 1250, "lodging": 620, "attractions": 60 + 28 + 4, "transport": 230}
    assert sam.by_category == {"flights": 1100, "lodging": 620, "attractions": 7 + 28 + 4, "transport": 230}
    assert (alex.total_usd, sam.total_usd) == (2500, 3000)


def test_someone_who_needs_an_attraction_must_be_going(group):
    replan(group)
    disney = next(i for i in group.itinerary if i.ref_id == "a_disney")
    group.attractions[0].need_by = ["p1", "p2"]
    disney.travelers = ["p1"]
    from tripwright.validate import validate_itinerary
    assert "Sam needs to see Tokyo Disneyland but is not going." in [v.message for v in validate_itinerary(group)]


def test_cards_and_booking_steps_are_per_traveler_for_flights_and_stays(group):
    replan(group)
    cards = {c.id: c for c in review_cards(group)}
    assert {"flight:p1", "flight:p2", "stay:p1:0", "stay:p2:2", "lodging", "transport"} <= set(cards)
    assert cards["flight:p2"].traveler == "p2"
    disney = next(c for c in cards.values() if c.title == "Tokyo Disneyland")
    assert (disney.need_by, disney.going, disney.price_usd) == (["Alex"], ["Alex", "Sam"], 120)

    steps = booking_steps(group)
    assert [s.who for s in steps if s.category == "flights"] == [["Alex"], ["Sam"]]
    tickets = next(s for s in steps if s.title == "Tokyo Disneyland")
    assert tickets.who == ["Alex", "Sam"] and "2 adult tickets" in tickets.todo and tickets.price_usd == 120


def test_wishes_merge_what_everyone_asked_for(group):
    group.travelers[1].need.append("tokyo disneyland")  # Sam, in different capitals
    assert wishes(group) == [
        ("w1", "Tokyo Disneyland", ["p1", "p2"], []),
        ("w2", "Kyoto", ["p1"], []),
        ("w3", "Ghibli Museum", ["p2"], []),
        ("w4", "teamLab Planets", [], ["p2"]),
    ]


def found(name, city, wish_ids, url="https://example.com/a"):
    return AttractionOut(name=name, city=city, wish_ids=wish_ids, why="", duration_minutes=90, ticket_price_usd=5,
                         opens="09:00", closes="17:00", closed_weekdays=[], outdoor=False, availability_note="",
                         source_url=url, booking_url="")


async def test_attractions_agent_result_is_tied_back_to_who_asked(group, monkeypatch):
    async def no_geocode(place):
        return None
    monkeypatch.setattr(places, "geocode", no_geocode)
    ctx = RunContext(agent="attractions", state=group)
    ctx.sources["example.com/a"] = Source(url="https://example.com/a")

    plan = await build_attractions(group, ctx, AttractionsOut(attractions=[
        found("Tokyo Disneyland", "Tokyo", ["w1"]), found("Fushimi Inari", "Kyoto", ["w2"]),
        found("Ghibli Museum", "Tokyo", ["w3"]), found("teamLab Planets", "Tokyo", ["w4"]),
        found("Senso-ji", "Tokyo", []), found("Made-up place", "Tokyo", [], url="https://nowhere.example"),
    ]))
    by_name = {a.name: a for a in plan}
    assert (by_name["Ghibli Museum"].need_by, by_name["Ghibli Museum"].must_have) == (["p2"], True)
    assert (by_name["teamLab Planets"].want_by, by_name["teamLab Planets"].must_have) == (["p2"], False)
    assert by_name["Senso-ji"].need_by == [] and "Made-up place" not in by_name  # unsourced extras are dropped

    with pytest.raises(Rejected, match='w3 "Ghibli Museum" is needed by Sam but no attraction covers it'):
        await build_attractions(group, ctx, AttractionsOut(attractions=[
            found("Tokyo Disneyland", "Tokyo", ["w1"]), found("Fushimi Inari", "Kyoto", ["w2"])]))


def test_host_creates_the_trip_and_others_join_until_planning_starts(monkeypatch):
    async def flights_land_the_next_day(origin, destination, depart, return_):
        return {"options": [{"arrive_at": "2026-12-02T15:00:00"}, {"arrive_at": "2026-12-02T18:00:00"},
                            {"arrive_at": "2026-12-03T06:00:00"}]}
    monkeypatch.setattr(flights, "search_flights", flights_land_the_next_day)
    state = orchestrator.new_trip(TripRequest(name="Alex", origin="Kansas City", destination="Japan", days=7,
                                              budget_usd=2500, need=["Tokyo Disneyland"]))
    assert [(t.id, t.name, t.host) for t in state.travelers] == [("p1", "Alex", True)]

    asyncio.run(orchestrator.choose_dates(state, date(2026, 12, 1)))
    assert state.stage == "gathering" and (state.dates.arrival, state.dates.end) == (date(2026, 12, 2), date(2026, 12, 8))

    sam = orchestrator.join(state, TravelerIn(name="Sam", origin="Chicago", budget_usd=3000, need=["Ghibli Museum"]))
    jo = orchestrator.join(state, TravelerIn(name="Jo", origin="Dallas", budget_usd=2000))
    assert (sam.id, jo.id) == ("p2", "p3")
    assert orchestrator.research_nodes(state) == [
        "flight:p1", "flight:p2", "flight:p3", "lodging", "attractions", "transport", "weather"]

    orchestrator.leave(state, "p2")
    assert [t.name for t in state.travelers] == ["Alex", "Jo"]
    with pytest.raises(ValueError, match="host"):
        orchestrator.leave(state, "p1")


def test_each_traveler_gets_a_room_that_fits_their_own_budget(group):
    from tripwright.specialists import assign_rooms
    alex, sam = group.travelers
    alex.budget_usd, sam.budget_usd = 2500, 1500  # about $117 and $70 a night for lodging
    assign_rooms(group)
    # Tokyo, 3 nights: the agent's pick is $110 a night; the cheaper room is $70.
    assert alex.lodging.stays[0].selected.name == "Tokyo Hotel t1"
    assert sam.lodging.stays[0].selected.name == "Tokyo Hotel t2"
    assert "within Sam's lodging budget of about $70 a night" in sam.lodging.stays[0].reasoning
    # Kyoto, 2 nights: both rooms ($100 and $75 a night) are over Sam's budget, so Sam gets the cheapest.
    assert sam.lodging.stays[1].selected.name == "Kyoto Hotel k2" and "over Sam's lodging budget" in sam.lodging.stays[1].reasoning
