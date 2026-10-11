"""The seeded friend trip: a strong shared core, and pairs who need the same side outing."""

from tripwright.scenario import friend_trip
from tripwright.specialists import wishes


def test_friend_trip_has_a_core_and_pairs_that_split_off():
    state = friend_trip()
    assert state.stage == "gathering" and len(state.travelers) == 7 and state.travelers[0].host
    need = {text: ids for _, text, ids, _, _ in wishes(state)}
    assert len(need["Fushimi Inari Taisha"]) >= 5  # nearly everyone's must-do
    assert need["Ghibli Museum"] == ["p2", "p4"]  # Maya and Priya
    assert need["Hakone day trip"] == ["p3", "p5"]  # Jordan and Chris
    assert need["Tokyo DisneySea"] == ["p6", "p7"]  # Taylor and Sam
    assert need["Sumo morning practice"] == ["p1"]  # Alex alone
