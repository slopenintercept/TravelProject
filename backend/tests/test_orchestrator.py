"""The review loop, fallback, timeout and parallel dispatch, driven by a scripted model (no network)."""

import asyncio
import json
import time
from datetime import date

import pytest
from strands.models.model import Model

from tripwright import config, orchestrator, recorded, store
from tripwright.events import bus
from tripwright.models import RoutePlan, RouteSegment, Traveler, TripDates, TripRequest, TripState
from tripwright.tools import flights, places


class ScriptedModel(Model):
    """Plays back one scripted assistant turn per call: ('text', str) or ('tool', name, input)."""

    def __init__(self, turns, delay=0.0):
        self.turns, self.delay, self.seen = list(turns), delay, []

    def update_config(self, **config):
        pass

    def get_config(self):
        return {}

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError
        yield

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        self.seen.append(messages[-1])
        self.system_prompt = system_prompt
        await asyncio.sleep(self.delay)
        turn = self.turns.pop(0)
        yield {"messageStart": {"role": "assistant"}}
        for i, block in enumerate(turn):
            if block[0] == "text":
                yield {"contentBlockStart": {"start": {}}}
                yield {"contentBlockDelta": {"delta": {"text": block[1]}}}
            else:
                yield {"contentBlockStart": {"start": {"toolUse": {"name": block[1], "toolUseId": f"t{len(self.seen)}{i}"}}}}
                yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(block[2])}}}}
            yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "tool_use" if any(b[0] == "tool" for b in turn) else "end_turn"}}
        yield {"metadata": {"usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2}, "metrics": {"latencyMs": 1}}}


def flight_row(n, price, airline):
    return {
        "airline": airline, "origin": "MCI", "destination": "NRT", "depart_at": "2026-11-10T07:36:00",
        "arrive_at": "2026-11-11T15:15:00", "return_depart_at": "2026-11-17T17:40:00",
        "return_arrive_at": "2026-11-17T16:11:00", "duration_minutes": 999, "stops": 1, "layovers": [],
        "price_usd": price, "id": f"f{n}",
    }


SEARCH = ("tool", "search_flights", {"origin": "MCI", "destination": "Tokyo",
                                     "depart_date": "2026-11-10", "return_date": "2026-11-17"})


def picks(*ids):
    return ("tool", "FlightsOut", {"origin_airports": ["MCI"],
                                   "picks": [{"option_id": i, "tradeoff": f"{i} is a fair deal"} for i in ids]})


@pytest.fixture
def trip(monkeypatch):
    async def fake_search(origin, destination, depart, return_):
        return {"url": "https://www.google.com/travel/flights?q=test", "evidence_url": "/evidence/f.png",
                "fetched_at": "2026-10-10T12:00:00",
                "options": [flight_row(1, 1418, "United"), flight_row(2, 1300, "ANA"), flight_row(3, 1576, "JAL")]}

    async def fake_weather(city, start, end):
        return []

    monkeypatch.setattr(flights, "search_flights", fake_search)
    monkeypatch.setattr(places, "daily_weather", fake_weather)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "DEMO_MODE", False)
    monkeypatch.setattr(config, "RECORD_FIXTURES", False)
    monkeypatch.setattr(recorded, "saved", lambda key: None)
    unique = time.time_ns()  # saved results are keyed by origin, so each test gets its own
    origin = f"Testville {unique}"
    return TripState(
        id=f"trip_{unique}",
        request=TripRequest(name="Alex", origin=origin, destination="Japan", days=7, budget_usd=2500),
        travelers=[Traveler(id="p1", host=True, name="Alex", origin=origin, budget_usd=2500)],
        route=RoutePlan(segments=[RouteSegment(city="Tokyo", nights=6)], arrival_day_offset=1),
        dates=TripDates(start=date(2026, 11, 10), arrival=date(2026, 11, 11), end=date(2026, 11, 17)),
    )


def script(monkeypatch, *models):
    queue = list(models)
    monkeypatch.setattr(orchestrator, "make_model", lambda: queue.pop(0))


def statuses(trip, agent):
    return [e["status"] for e in bus(trip.id).history if e["type"] == "agent" and e["agent"] == agent]


async def test_rejected_result_is_sent_back_with_feedback_then_accepted(trip, monkeypatch):
    flight_agent = ScriptedModel([[("text", "Searching MCI to Tokyo."), SEARCH], [picks("f99")], [picks("f2", "f1", "f3")]])
    script(monkeypatch, flight_agent)

    await orchestrator.run(trip, orchestrator.planning_graph(["flight:p1"]), "planning")

    assert statuses(trip, "flight:p1") == ["working", "under_review", "sent_back", "working", "under_review", "accepted"]
    feedback = flight_agent.seen[-1]["content"][0]["text"]
    assert "f99 is not an id returned by search_flights" in feedback
    # Prices and evidence come from the tool result, not from anything the model typed.
    best = trip.travelers[0].flights.selected
    assert (best.airline, best.price_usd, best.tradeoff) == ("ANA", 1300, "f2 is a fair deal")
    assert best.source.evidence_url == "/evidence/f.png"
    assert trip.budgets["p1"].by_category["flights"] == 1300
    assert "flight:p1" not in trip.flags


async def test_llm_reviewer_can_send_a_result_back(trip, monkeypatch):
    monkeypatch.setattr(orchestrator.SPECS["flight"], "judged", True)  # flights are not judged; any specialist can be
    flight_agent = ScriptedModel([[SEARCH], [picks("f2", "f3")], [picks("f2", "f1", "f3")]])
    script(monkeypatch, flight_agent,
           ScriptedModel([[("tool", "Verdict", {"accept": False, "feedback": "offer three options, not two"})]]),
           ScriptedModel([[("tool", "Verdict", {"accept": True, "feedback": ""})]]))

    await orchestrator.run(trip, orchestrator.planning_graph(["flight:p1"]), "planning")

    assert statuses(trip, "flight:p1").count("sent_back") == 1
    assert "offer three options, not two" in flight_agent.seen[-1]["content"][0]["text"]
    assert [o.id for o in trip.travelers[0].flights.options] == ["f2", "f1", "f3"]


async def test_pick_over_its_budget_share_gives_way_to_the_cheapest_without_a_send_back(trip, monkeypatch):
    script(monkeypatch, ScriptedModel([[SEARCH], [picks("f3", "f1")]]))  # $1576 first; the budget share is $1250

    await orchestrator.run(trip, orchestrator.planning_graph(["flight:p1"]), "planning")

    assert "sent_back" not in statuses(trip, "flight:p1")
    plan = trip.travelers[0].flights
    assert [o.id for o in plan.options] == ["f2", "f3", "f1"] and plan.selected_id == "f2"  # f2 was never picked
    assert plan.selected.tradeoff == "The cheapest fare found for these dates."


async def test_route_is_ended_at_the_arrival_city_in_code_and_the_planner_knows_it_has_no_tools(trip, monkeypatch):
    planner = ScriptedModel([[("tool", "RouteOut", {"arrival_day_offset": 1, "segments": [
        {"city": "Tokyo", "nights": 4}, {"city": "Kyoto", "nights": 2}]})]])
    script(monkeypatch, planner)

    await orchestrator.run(trip, orchestrator.route_graph(), "route")

    assert statuses(trip, "route") == ["working", "under_review", "accepted"]
    assert [(s.city, s.nights) for s in trip.route.segments] == [("Tokyo", 3), ("Kyoto", 2), ("Tokyo", 1)]
    assert "no research tools" in planner.system_prompt


async def test_three_failures_fall_back_to_the_saved_result_and_flag_it(trip, monkeypatch):
    script(monkeypatch, ScriptedModel([[SEARCH], [picks("f2")]]))
    await orchestrator.run(trip, orchestrator.planning_graph(["flight:p1"]), "planning")
    saved = trip.travelers[0].flights.selected.depart_at

    # Same trip a week later; this time the agent keeps naming an option that doesn't exist.
    bus(trip.id).history.clear()
    trip.dates = TripDates(start=date(2026, 11, 17), arrival=date(2026, 11, 18), end=date(2026, 11, 24))
    script(monkeypatch, ScriptedModel([[picks("f99")], [picks("f99")], [picks("f99")]]))
    await orchestrator.run(trip, orchestrator.planning_graph(["flight:p1"]), "replan")

    assert statuses(trip, "flight:p1").count("sent_back") == 3
    assert statuses(trip, "flight:p1")[-1] == "fallback"
    assert trip.flags["flight:p1"].kind == "fallback"
    assert (trip.travelers[0].flights.selected.depart_at - saved).days == 7  # saved result re-dated to the new trip
    assert trip.travelers[0].flights.selected.source.fetched_at.isoformat() == "2026-10-10T12:00:00"  # evidence date untouched


async def test_slow_agent_times_out_without_blocking_the_others(trip, monkeypatch):
    monkeypatch.setattr(config, "AGENT_TIMEOUT_S", 0.3)
    script(monkeypatch, ScriptedModel([[SEARCH]], delay=5))

    started = time.monotonic()
    await orchestrator.run(trip, orchestrator.planning_graph(["flight:p1", "weather"]), "planning")

    assert time.monotonic() - started < 2
    assert trip.flags["flight:p1"].kind == "pending" and "timed out" in trip.flags["flight:p1"].reason
    assert trip.agents["weather"].status == "accepted"
    assert trip.agents["validate"].status == "accepted"


async def test_each_traveler_gets_their_own_flight_agent_and_they_run_in_parallel(trip, monkeypatch):
    trip.travelers.append(Traveler(id="p2", name="Sam", origin="Elsewhere", budget_usd=3000))
    monkeypatch.setattr(orchestrator, "make_model", lambda: ScriptedModel([[SEARCH], [picks("f2")]], delay=0.4))

    started = time.monotonic()
    await orchestrator.run(trip, orchestrator.planning_graph(["flight:p1", "flight:p2"]), "planning")

    assert time.monotonic() - started < 1.4  # two agents x two 0.4s model calls each would be 1.6s in series
    assert [t.flights.selected_id for t in trip.travelers] == ["f2", "f2"]
    assert {"flight:p1", "flight:p2"} <= set(trip.agents)
    assert set(trip.budgets) == {"p1", "p2"}


def test_no_inference_key_goes_straight_to_pending(trip, monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    asyncio.run(orchestrator.run(trip, orchestrator.planning_graph(["flight:p1"]), "planning"))
    assert statuses(trip, "flight:p1") == ["pending"]
    assert store.load_trip(trip.id).flags["flight:p1"].kind == "pending"

