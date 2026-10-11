"""The saved profile carries stated preferences into the next trip, not the last host's description."""

from tripwright import orchestrator, store
from tripwright.models import TravelerProfile, TripRequest
from tripwright.specialists import brief

ALEX = "Alex is a solo traveler from Kansas City planning a 7-day balanced-pace trip to Japan on a $2,500 budget."


def test_a_new_trip_keeps_the_stated_preferences_but_not_the_last_hosts_summary():
    store.save_profile(TravelerProfile(home="Kansas City", interests=["theme parks"], summary=ALEX,
                                       stated_preferences=[orchestrator.PREF["airbnb"]]))
    state = orchestrator.new_trip(TripRequest(name="Deep", origin="Kansas", destination="Japan", days=7,
                                              budget_usd=3000))
    told = brief(state)
    assert "Alex" not in told and "Kansas City" not in told
    assert "- Deep: flying from Kansas" in told
    assert orchestrator.PREF["airbnb"] in told
    assert state.lodging_override == "airbnb"


def test_the_brief_has_no_host_line_before_anything_is_known_about_the_host():
    store.save_profile(TravelerProfile(summary=ALEX))
    state = orchestrator.new_trip(TripRequest(name="Deep", origin="Kansas", destination="Japan", days=7,
                                              budget_usd=3000))
    assert "Host:" not in brief(state)
