"""The demo trip replays the recorded run on a server that plans every other trip live."""

import asyncio
import socket

import httpx
import pytest

from tripwright import api, config, draft, orchestrator, recorded

DEMO = {"name": "Alex", "origin": "Kansas City", "destination": "Japan", "days": 7, "budget_usd": 2500}


@pytest.fixture
def server(monkeypatch):
    """A server with a key and no DEMO_MODE, like the hosted one. `left` lists every attempt to reach a model or
    the network, which then fails."""
    left = []

    def leave(what):
        def attempt(*args, **kwargs):
            left.append(what)
            raise RuntimeError(f"{what} was reached")
        return attempt

    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "DEMO_MODE", False)
    monkeypatch.setattr(config, "RECORD_FIXTURES", False)
    monkeypatch.setattr(orchestrator, "make_model", leave("model"))
    monkeypatch.setattr(draft, "make_model", leave("model"))
    monkeypatch.setattr(socket.socket, "connect", leave("network"))
    monkeypatch.setattr(orchestrator, "REPLAY_S", dict.fromkeys(orchestrator.REPLAY_S, 0))
    monkeypatch.setattr(api, "DRAFT_DELAY_S", 0)
    return left


async def settled(client, trip_id):
    """The trip once nothing is running for it."""
    while True:
        view = (await client.get(f"/api/trips/{trip_id}")).json()
        if not view["busy"] and not api._tasks:
            return view["state"]
        await asyncio.sleep(0.01)


async def start(client, **request):
    created = await client.post("/api/trips", json=DEMO | request)
    return await settled(client, created.json()["state"]["id"])


async def test_a_recorded_trip_runs_to_review_on_recordings_alone(server):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://test") as client:
        state = await start(client, recorded=True)
        trip, host = f"/api/trips/{state['id']}", {"X-Traveler": "p1"}
        assert len(state["ideas"]) == 24 and len(state["windows"]) == 3

        await client.post(f"{trip}/dates", json={"start": state["windows"][0]["start"]}, headers=host)
        await client.post(f"{trip}/travelers", json={"name": "Sam", "origin": "Chicago", "budget_usd": 3000})
        await client.post(f"{trip}/travelers", json={"name": "Jo", "origin": "Dallas", "budget_usd": 2200})
        state = await settled(client, state["id"])
        assert state["draft"] and all(i["lat"] is not None for i in state["ideas"])  # every place has a pin

        await client.post(f"{trip}/plan", headers=host)
        state = await settled(client, state["id"])
        for t in state["travelers"]:
            assert len(t["flights"]["options"]) == 3 and len(t["lodging"]["stays"]) == 3
            chosen = {"flight_id": t["flights"]["options"][0]["id"],
                      "stay_ids": [s["options"][0]["id"] for s in t["lodging"]["stays"]]}
            await client.put(f"{trip}/travelers/{t['id']}/choices", json=chosen, headers={"X-Traveler": t["id"]})
        state = await settled(client, state["id"])

    assert state["stage"] == "review" and state["flags"] == {}
    assert (len(state["attractions"]), len(state["transport"]["legs"]), len(state["weather"])) == (9, 5, 7)
    live = api._live[state["id"]]
    for name in ["route", "profile", "timeframe", "ideas", *orchestrator.research_nodes(live)]:
        assert live.agents[name].status == "accepted", name
    assert server == []  # no model was asked and nothing went to the network


async def test_an_ordinary_trip_on_the_same_server_plans_live(server):
    async def fetch():
        return "fetched"

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://test") as client:
        demo = await start(client, recorded=True)
        assert server == []
        ordinary = await start(client)  # the same form, not marked as recorded

        assert "model" in server  # its agents went to the model
        assert api._live[ordinary["id"]].agents["route"].message != "Recorded result"
        # A tool call replays for whichever trip the last request was for.
        assert await recorded.cached("geocode:tokyo, japan", fetch) == "fetched"
        await client.get(f"/api/trips/{demo['id']}")
        assert await recorded.cached("geocode:tokyo, japan", fetch) != "fetched"
