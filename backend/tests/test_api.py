"""Each traveler acts as themselves (the X-Traveler header from their own trip link)."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from tripwright import api, store
from tripwright.cards import review_cards
from tripwright.models import AgentStatus, Idea

client = TestClient(api.app)


@pytest.fixture
def trip(group):
    group.stage = "review"
    api._live[group.id] = group
    yield group
    api._live.pop(group.id, None)


def post(trip, path, body, traveler=None):
    headers = {"X-Traveler": traveler} if traveler else {}
    return client.post(f"/api/trips/{trip.id}{path}", json=body, headers=headers)


def status(trip, card_id):
    return next(card.status for card in review_cards(trip) if card.id == card_id)


def put(trip, path, body, traveler=None):
    headers = {"X-Traveler": traveler} if traveler else {}
    return client.put(f"/api/trips/{trip.id}{path}", json=body, headers=headers)


def test_each_traveler_approves_only_their_own_flight_and_stays(trip):
    assert post(trip, "/decisions", {"action": "approve", "card": "flight:p2"}, "p2").status_code == 200
    assert post(trip, "/decisions", {"action": "approve", "card": "stay:p2:0"}, "p2").status_code == 200
    assert set(trip.approvals) == {"flight:p2", "stay:p2:0"}
    assert status(trip, "flight:p2") == status(trip, "stay:p2:0") == "approved"
    assert status(trip, "flight:p1") == "proposed"

    for card in ("flight:p1", "stay:p1:0"):  # Sam can't decide for Alex, and the host can't decide for Sam
        assert post(trip, "/decisions", {"action": "approve", "card": card}, "p2").status_code == 403
    assert post(trip, "/decisions", {"action": "approve", "card": "flight:p2"}, "p1").status_code == 403
    assert post(trip, "/budget/apply", {"traveler": "p1"}, "p2").status_code == 403


def test_an_approval_is_withdrawn_when_another_flight_or_room_is_chosen(trip):
    sam = trip.traveler("p2")
    for card in ("flight:p2", "stay:p2:0"):
        assert post(trip, "/decisions", {"action": "approve", "card": card}, "p2").status_code == 200
    # Not through the card's own Swap: a budget fix, a new confirm and a new search all set the choice directly.
    other_flight = next(o.id for o in sam.flights.options if o.id != sam.flights.selected_id)
    sam.flights.selected_id = other_flight
    assert status(trip, "flight:p2") == "proposed" and status(trip, "stay:p2:0") == "approved"
    assert post(trip, "/decisions", {"action": "approve", "card": "flight:p2"}, "p2").status_code == 200
    assert trip.approvals["flight:p2"] == other_flight and status(trip, "flight:p2") == "approved"


def test_shared_choices_are_anyones_on_the_trip(trip):
    assert post(trip, "/decisions", {"action": "approve", "card": "attraction:a_disney"}, "p2").status_code == 200
    assert status(trip, "attraction:a_disney") == "approved"


def test_requests_need_someone_on_the_trip(trip):
    assert post(trip, "/decisions", {"action": "approve", "card": "attraction:a_disney"}).status_code == 403
    assert post(trip, "/decisions", {"action": "approve", "card": "attraction:a_disney"}, "p9").status_code == 403


def test_only_the_host_sets_dates_starts_planning_and_removes_people(trip):
    trip.stage = "gathering"
    assert post(trip, "/dates", {"start": "2030-01-01"}, "p2").status_code == 403
    assert post(trip, "/plan", None, "p2").status_code == 403
    assert client.delete(f"/api/trips/{trip.id}/travelers/p1", headers={"X-Traveler": "p2"}).status_code == 403
    # ...but anyone can leave.
    assert client.delete(f"/api/trips/{trip.id}/travelers/p2", headers={"X-Traveler": "p2"}).status_code == 200
    assert [t.id for t in trip.travelers] == ["p1"]


def test_joining_returns_the_new_travelers_id(trip):
    trip.stage = "gathering"
    joined = post(trip, "/travelers", {"name": "Jo", "origin": "Dallas", "budget_usd": 2000, "need": [], "want": []})
    assert joined.status_code == 200 and joined.json()["you"] == "p3"


# --- picks on the shared ideas list ---------------------------------------------

@pytest.fixture
def picking(trip):
    trip.stage = "gathering"
    trip.ideas = [Idea(id="i1", name="Tokyo Disneyland", city="Tokyo"), Idea(id="i2", name="Kinkaku-ji", city="Kyoto")]
    return trip


def test_each_traveler_saves_only_their_own_picks(picking):
    ok = put(picking, "/travelers/p2/picks", {"need": ["tokyo disneyland"], "skip": ["Kinkaku-ji"]}, "p2")
    sam = picking.traveler("p2")
    assert ok.status_code == 200
    assert (sam.need, sam.want, sam.skip, sam.picked) == (["Tokyo Disneyland"], [], ["Kinkaku-ji"], True)
    assert put(picking, "/travelers/p2/picks", {"need": []}, "p1").status_code == 403


def test_picks_must_be_on_the_list_and_marked_once(picking):
    assert "Mt Fuji is not on the list" in put(picking, "/travelers/p2/picks", {"want": ["Mt Fuji"]}, "p2").json()["detail"]
    twice = put(picking, "/travelers/p2/picks", {"need": ["Kinkaku-ji"], "skip": ["kinkaku-ji"]}, "p2")
    assert "Kinkaku-ji is marked more than once" in twice.json()["detail"]


def test_picks_with_an_empty_list_still_count_as_picked(picking):
    picking.ideas = []
    assert put(picking, "/travelers/p2/picks", {}, "p2").status_code == 200 and picking.traveler("p2").picked


def test_anyone_on_the_trip_adds_a_place_once(picking):
    assert post(picking, "/ideas", {"name": "Ghibli Museum", "city": "Tokyo"}, "p2").status_code == 200
    added = picking.ideas[-1]
    assert (added.name, added.city, added.added_by, added.category) == ("Ghibli Museum", "Tokyo", "p2", "Added by the group")
    assert post(picking, "/ideas", {"name": "tokyo  DISNEYLAND"}, "p1").json()["detail"] == "tokyo  DISNEYLAND is already on the list"
    assert post(picking, "/ideas", {"name": "Somewhere"}).status_code == 403


def test_suggest_more_saves_your_marks_and_finds_more_in_the_background(picking, monkeypatch):
    asked = []

    def suggest_more(state, traveler_id):
        asked.append(traveler_id)
        return asyncio.sleep(0)
    monkeypatch.setattr(api.orchestrator, "suggest_more", suggest_more)
    done = post(picking, "/ideas/more", {"need": ["Tokyo Disneyland"], "skip": ["Kinkaku-ji"]}, "p2")
    sam = picking.traveler("p2")
    assert done.status_code == 200 and asked == ["p2"]
    assert (sam.need, sam.skip, sam.picked) == (["Tokyo Disneyland"], ["Kinkaku-ji"], False)  # still on the picks screen


def test_suggest_more_once_at_a_time_and_only_before_planning(picking):
    picking.agents["more_ideas:p2"] = AgentStatus(agent="more_ideas:p2", status="working")
    assert post(picking, "/ideas/more", {}, "p2").json()["detail"] == "Already finding more places for you"
    assert post(picking, "/ideas/more", {}).status_code == 403
    picking.stage = "planning"
    assert post(picking, "/ideas/more", {}, "p1").status_code == 400


def test_marks_stay_open_while_more_places_are_found(picking):
    picking.agents["more_ideas:p2"] = AgentStatus(agent="more_ideas:p2", status="working")
    assert put(picking, "/travelers/p1/picks", {"want": ["Kinkaku-ji"]}, "p1").status_code == 200


# --- choosing your flight and rooms --------------------------------------------

@pytest.fixture
def choosing(trip):
    trip.stage = "choosing"
    for agent in ("flight:p1", "flight:p2", "lodging"):
        trip.agents[agent] = AgentStatus(agent=agent, status="accepted")
    return trip


def choose(trip, traveler, flight="f2", stays=("t2", "k2", "n1"), acting=None):
    return put(trip, f"/travelers/{traveler}/choices", {"flight_id": flight, "stay_ids": list(stays)}, acting or traveler)


def test_only_you_choose_your_flight_and_rooms(choosing):
    assert choose(choosing, "p2", acting="p1").status_code == 403
    assert "not one of your options" in choose(choosing, "p2", flight="f9").json()["detail"]


def test_choosing_waits_for_planning_and_for_your_options(choosing):
    choosing.agents["flight:p2"] = AgentStatus(agent="flight:p2", status="working")
    assert choose(choosing, "p2").json()["detail"] == "Your options are still being found"
    del choosing.agents["flight:p2"]  # research has only just started
    assert choose(choosing, "p2").json()["detail"] == "Your options are still being found"
    choosing.stage = "gathering"
    assert choose(choosing, "p2").json()["detail"] == "Planning hasn't started yet"


def test_the_first_choice_plans_the_days(choosing):
    done = choose(choosing, "p2")
    assert done.status_code == 200 and choosing.stage == "review" and choosing.itinerary
    assert choosing.traveler("p2").confirmed and not choosing.traveler("p1").confirmed


def test_each_later_choice_replans_the_days(choosing):
    choose(choosing, "p2")
    assert choosing.budgets["p2"].by_category["flights"] == 1100  # ANA
    assert choose(choosing, "p2", flight="f3").status_code == 200  # changed their mind
    assert choosing.stage == "review" and choosing.budgets["p2"].by_category["flights"] == 1400


def test_a_choice_during_research_waits_for_it_to_finish(choosing, monkeypatch):
    class Busy:
        def locked(self):
            return True
    monkeypatch.setattr(api, "_lock", lambda trip_id: Busy())
    assert choose(choosing, "p2").status_code == 200
    assert choosing.traveler("p2").confirmed and choosing.stage == "choosing" and not choosing.itinerary


def test_agents_cut_off_by_a_restart_are_marked_stopped(trip):
    trip.stage = "timeframe"
    trip.agents["ideas"] = AgentStatus(agent="ideas", status="working", attempt=2)
    trip.agents["route"] = AgentStatus(agent="route", status="accepted")
    store.save_trip(trip)
    api._live.pop(trip.id)  # the server restarted

    state = client.get(f"/api/trips/{trip.id}").json()["state"]
    assert state["agents"]["ideas"]["status"] == "failed"
    assert state["agents"]["ideas"]["message"] == "Stopped when the server restarted"
    assert state["agents"]["route"]["status"] == "accepted"
    assert state["stage"] == "awaiting_dates"  # the host can pick dates and carry on
    assert post(trip, "/ideas", {"name": "Ghibli Museum"}, "p1").status_code == 200  # no longer waiting on ideas


def test_picks_wait_for_the_ideas_agent_and_stop_at_planning(picking):
    picking.agents["ideas"] = AgentStatus(agent="ideas", status="working")
    assert post(picking, "/ideas", {"name": "X"}, "p1").json()["detail"] == "Agents are still finding places"
    assert put(picking, "/travelers/p1/picks", {}, "p1").json()["detail"] == "Agents are still finding places"
    picking.agents["ideas"].status = "accepted"
    picking.stage = "review"
    assert put(picking, "/travelers/p1/picks", {}, "p1").json()["detail"] == "Planning has already started for this trip"
    assert post(picking, "/ideas", {"name": "X"}, "p1").status_code == 400
