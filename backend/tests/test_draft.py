"""The draft plan: everyone's picks sketched onto the days before flights and hotels are found."""

import asyncio

from tripwright import api, draft
from tripwright.scenario import friend_trip

CITIES = {"Tokyo": (35.68, 139.69), "Kyoto": (35.01, 135.77), "Hakone": (35.23, 139.02), "Nara": (34.68, 135.80),
          "Kamakura": (35.32, 139.55)}


def located(state):
    """The friend trip with every place located, as `locate` would leave it, without the network."""
    for idea in state.ideas:
        idea.lat, idea.lon = CITIES[idea.city]
    return {city: CITIES[city] for city in ("Tokyo", "Kyoto")}


def going(sketch, name):
    return [i.travelers for i in sketch.itinerary if i.title == name]


def test_day_trips_are_visited_from_the_nearest_city_on_the_route():
    state = friend_trip()
    sketch = draft.sketch(state, located(state))
    assert {i.city for i in sketch.itinerary if i.kind == "attraction"} <= {"Tokyo", "Kyoto"}
    hakone = next(i for i in sketch.itinerary if i.title == "Hakone day trip")
    assert hakone.city == "Tokyo" and (hakone.end.hour * 60 + hakone.end.minute) - (hakone.start.hour * 60 + hakone.start.minute) == 480


def test_pairs_go_together_and_skips_are_respected():
    state = friend_trip()
    sketch = draft.sketch(state, located(state))
    ghibli, disney, golden_gai = (going(sketch, n) for n in ("Ghibli Museum", "Tokyo DisneySea", "Shinjuku Golden Gai"))
    assert ghibli and all({"p2", "p4"} <= set(who) for who in ghibli)  # Maya and Priya both go
    assert disney and all({"p6", "p7"} <= set(who) and "p5" not in who for who in disney)  # Chris skips it
    assert golden_gai and all("p4" not in who for who in golden_gai)  # Priya marked it not for me
    assert sketch.built_at is not None and not state.itinerary  # the real itinerary is untouched


def test_niche_places_are_just_for_who_asked_and_bars_are_at_night():
    state = friend_trip()
    sketch = draft.sketch(state, located(state))
    assert [sorted(who) for who in going(sketch, "Ghibli Museum")] == [["p2", "p4"]]  # Maya and Priya only
    assert [sorted(who) for who in going(sketch, "Hakone day trip")] == [["p3", "p5"]]  # Jordan and Chris
    bars = [i for i in sketch.itinerary if i.title in ("Shinjuku Golden Gai", "Karaoke night in Shinjuku")]
    assert bars and all(i.start.hour >= 18 for i in bars)


def test_a_day_trip_does_not_count_the_ride_twice():
    from types import SimpleNamespace as Stop
    from tripwright.geo import DEFAULT_HOP_MIN, travel_minutes
    tsukiji, hakone = Stop(lat=35.665, lon=139.770), Stop(lat=35.23, lon=139.02)
    assert travel_minutes(tsukiji, hakone) == DEFAULT_HOP_MIN  # its 8-hour day already includes the train
    assert travel_minutes(tsukiji, Stop(lat=35.6595, lon=139.7005)) < 60  # across town is still a transit ride


def test_places_nobody_asked_for_stay_off_the_draft():
    state = friend_trip()
    sketch = draft.sketch(state, located(state))
    assert not going(sketch, "Kamakura day trip")  # on the list, but nobody marked it


async def test_saves_close_together_build_one_draft(monkeypatch):
    state = friend_trip()
    built = []

    async def build(s):
        built.append(s.id)
    monkeypatch.setattr(api, "DRAFT_DELAY_S", 0.05)
    monkeypatch.setattr(api.draft, "build_draft", build)
    for _ in range(3):  # three people save their picks within a moment
        api._redraft(state)
    await asyncio.sleep(0.2)
    assert built == [state.id]
