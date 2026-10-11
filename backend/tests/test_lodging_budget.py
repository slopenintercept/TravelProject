"""Lodging when no room fits the budget: the cheapest central room is taken and flagged, not refused."""

import asyncio
from datetime import date

import pytest

from tripwright.specialists import LodgingOut, Rejected, StayPick, assign_rooms, build_lodging
from tripwright.toolbox import RunContext, Toolbox
from tripwright.tools import places
from tripwright.tools.lodging import MAX_OPTIONS, _finish

TOKYO = (35.6812, 139.7671)


def page(*rooms):
    """A fetched search page: (nightly price, rating) per room."""
    return {"url": "https://example.com/hotels", "evidence_url": "https://example.com/hotels.png", "fetched_at": None,
            "options": [{"name": f"Hotel {price}", "kind": "hotel", "rating": rating, "reviews": 100,
                         "price_per_night_usd": price, "price_total_usd": price,
                         "booking_url": "https://example.com/room"} for price, rating in rooms]}


def finish(result, cap):
    return _finish(result, "h-asakusatokyo", "Tokyo", "Asakusa", date(2026, 12, 30), date(2026, 12, 31), cap)


def test_search_with_nothing_under_the_cap_returns_the_cheapest_rooms():
    found = finish(page((97, 4.5), (75, 3.9), (121, 4.8), (85, 4.1), (80, 4.0)), 44)["options"]
    assert [o["price_per_night_usd"] for o in found] == [75, 80, 85]


def test_search_with_rooms_under_the_cap_returns_only_those_and_keeps_the_cheapest():
    # Ten rooms fit; the cheapest is the worst rated, so a cut by rating alone would drop it.
    fits = [(30, 3.0)] + [(40 + i, 4.0 + i / 10) for i in range(9)]
    found = finish(page(*fits, (60, 4.9), (75, 5.0)), 50)["options"]
    prices = [o["price_per_night_usd"] for o in found]
    assert len(found) == MAX_OPTIONS and max(prices) <= 50 and 30 in prices


def test_search_result_says_when_every_room_is_over_the_cap(group):
    tools = Toolbox(RunContext(agent="lodging", state=group))
    over = asyncio.run(tools._rooms(finish(page((75, 3.9), (97, 4.5)), 44), "Google Hotels", TOKYO, 44, "Asakusa"))
    assert over.splitlines()[0] == "Nothing at or under $44 a night in Asakusa. The cheapest found:"
    assert "$75/night" in over.splitlines()[1]
    under = asyncio.run(tools._rooms(finish(page((40, 3.9), (97, 4.5)), 44), "Google Hotels", TOKYO, 44, "Asakusa"))
    assert under.startswith("h-asakusatokyo-1230-1 | Hotel 40")


@pytest.fixture
def searched(group, monkeypatch):
    """The lodging agent's run after one search per stay, on budgets no room found comes near."""
    async def geocode(place):
        return TOKYO
    monkeypatch.setattr(places, "geocode", geocode)
    for t in group.travelers:
        t.budget_usd = 600  # about $28 a night for lodging; the cheapest rooms are $70, $75 and $90
    ctx = RunContext(agent="lodging", state=group)
    ctx.add_source("https://example.com/guide", "Guide", "https://example.com/guide.png", None)
    for stay in group.lodging.stays:
        for option in stay.options:
            ctx.rooms[option.id] = option.model_copy(update={"lat": TOKYO[0], "lon": TOKYO[1]})
    out = LodgingOut(most_travelers_pick="hotel", because="rooms are small but central", neighborhoods=["Asakusa"],
                     source_ids=["s1"], stays=[StayPick(stay=i, option_id=id, reasoning="Near the station.")
                                               for i, id in enumerate(["t2", "k2", "n1"], 1)])
    return ctx, out


def test_a_stay_with_nothing_in_budget_is_accepted_and_flagged_over_budget(group, searched):
    group.lodging = asyncio.run(build_lodging(group, *searched))
    assign_rooms(group)
    sam = group.traveler("p2").lodging.stays
    assert [s.selected.id for s in sam] == ["t2", "k2", "n1"]  # the cheapest room of each stay
    assert sam[2].reasoning == ("Cheapest option found at $90 a night; that is over Sam's lodging budget "
                                "of about $28 a night.")


def test_a_room_far_from_the_centre_is_still_rejected(group, searched):
    ctx, out = searched
    ctx.rooms["n1"].lat, ctx.rooms["n1"].lon = 35.7003, 139.4803  # Kokubunji, about 26 km west
    with pytest.raises(Rejected, match="too far from central Tokyo"):
        asyncio.run(build_lodging(group, ctx, out))
