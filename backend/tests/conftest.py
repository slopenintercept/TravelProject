import os
import tempfile
from datetime import date, datetime, time

# Tests get their own database and evidence folder; set before tripwright.config is imported.
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="tripwright-test-")

import pytest  # noqa: E402

from tripwright.models import (  # noqa: E402
    Attraction, CommonChoice, DayWeather, FlightOption, FlightPlan, LodgingOption, LodgingPlan,
    LodgingStay, RoutePlan, RouteSegment, Source, TransportLeg, TransportPlan, Traveler, TripDates,
    TripRequest, TripState,
)

SRC = Source(url="https://example.com/source", evidence_url="https://example.com/evidence.png")


def flight(id, price, airline="United"):
    return FlightOption(
        id=id, airline=airline, origin="MCI", destination="NRT",
        depart_at=datetime(2026, 11, 10, 6, 0), arrive_at=datetime(2026, 11, 11, 15, 25),
        return_depart_at=datetime(2026, 11, 17, 17, 30), return_arrive_at=datetime(2026, 11, 17, 18, 40),
        duration_minutes=1165, stops=1, price_usd=price, booking_url="https://example.com/book", source=SRC,
    )


def room(id, city, check_in, check_out, price, name=None):
    return LodgingOption(
        id=id, city=city, name=name or f"{city} Hotel {id}", kind="hotel", check_in=check_in,
        check_out=check_out, price_total_usd=price, booking_url="https://example.com/room", source=SRC,
    )


def attraction(id, name, city, lat, lon, **kw):
    kw.setdefault("need_by", ["p1"] if kw.get("must_have") else [])
    return Attraction(id=id, name=name, city=city, lat=lat, lon=lon, source=SRC, **kw)


@pytest.fixture
def state():
    """The demo scenario with just the host: Kansas City to Japan, Tokyo 3 nights, Kyoto 2, Tokyo 1."""
    d = lambda day: date(2026, 11, day)  # noqa: E731
    stays = [
        LodgingStay(city="Tokyo", check_in=d(11), check_out=d(14), selected_id="t1",
                    options=[room("t1", "Tokyo", d(11), d(14), 330), room("t2", "Tokyo", d(11), d(14), 210)]),
        LodgingStay(city="Kyoto", check_in=d(14), check_out=d(16), selected_id="k1",
                    options=[room("k1", "Kyoto", d(14), d(16), 200), room("k2", "Kyoto", d(14), d(16), 150)]),
        LodgingStay(city="Tokyo", check_in=d(16), check_out=d(17), selected_id="n1",
                    options=[room("n1", "Tokyo", d(16), d(17), 90)]),
    ]
    choice = CommonChoice(choice="hotel", because="small rooms, great locations", alternative="airbnb")
    request = TripRequest(name="Alex", origin="Kansas City", destination="Japan", days=7, budget_usd=2500,
                          need=["Tokyo Disneyland", "Kyoto"])
    host = Traveler(
        id="p1", host=True, name="Alex", origin="Kansas City", budget_usd=2500, need=["Tokyo Disneyland", "Kyoto"],
        flights=FlightPlan(options=[flight("f1", 1250), flight("f2", 1100, "ANA"), flight("f3", 1400, "Delta")],
                           selected_id="f1"),
        lodging=LodgingPlan(common_choice=choice, stays=stays),
    )
    return TripState(
        id="trip_test", request=request, travelers=[host], lodging=host.lodging.model_copy(deep=True),
        route=RoutePlan(segments=[RouteSegment(city="Tokyo", nights=3), RouteSegment(city="Kyoto", nights=2),
                                  RouteSegment(city="Tokyo", nights=1)], arrival_day_offset=1),
        dates=TripDates(start=d(10), arrival=d(11), end=d(17)),
        attractions=[
            attraction("a_disney", "Tokyo Disneyland", "Tokyo", 35.6329, 139.8804, must_have=True,
                       duration_minutes=540, ticket_price_usd=60, opens=time(9), closes=time(21), outdoor=True),
            attraction("a_sensoji", "Senso-ji", "Tokyo", 35.7148, 139.7967, duration_minutes=90),
            attraction("a_teamlab", "teamLab Planets", "Tokyo", 35.6492, 139.7898, duration_minutes=120,
                       ticket_price_usd=28, opens=time(9), closes=time(22)),
            attraction("a_fushimi", "Fushimi Inari Taisha", "Kyoto", 34.9671, 135.7727, must_have=True,
                       duration_minutes=150, outdoor=True),
            attraction("a_kinkaku", "Kinkaku-ji", "Kyoto", 35.0394, 135.7292, duration_minutes=75,
                       ticket_price_usd=4, opens=time(9), closes=time(17)),
        ],
        transport=TransportPlan(
            common_choice=CommonChoice(choice="trains", because="fast and frequent", alternative="rental car"),
            legs=[
                TransportLeg(id="l_shink", kind="intercity", from_place="Tokyo", to_place="Kyoto",
                             mode="Shinkansen", duration_minutes=135, price_usd=95, source=SRC),
                TransportLeg(id="l_back", kind="intercity", from_place="Kyoto", to_place="Tokyo",
                             mode="Shinkansen", duration_minutes=135, price_usd=95, source=SRC),
                TransportLeg(id="l_nex", kind="airport_transfer", from_place="NRT", to_place="Tokyo",
                             mode="Narita Express", duration_minutes=60, price_usd=40, source=SRC),
            ],
        ),
        weather=[DayWeather(day=d(day), city="Tokyo", precip_prob=p, source=SRC)
                 for day, p in [(11, 20), (12, 70), (13, 10), (14, 30), (15, 5), (16, 40), (17, 20)]],
    )


@pytest.fixture
def group(state):
    """The same trip with a second traveler, Sam from Chicago, who needs different things."""
    host = state.travelers[0]
    sam = host.model_copy(deep=True, update={"id": "p2", "host": False, "name": "Sam", "origin": "Chicago",
                                              "budget_usd": 3000, "need": ["Ghibli Museum"], "want": ["teamLab Planets"]})
    state.travelers.append(sam)
    state.attractions[2].want_by = ["p2"]  # teamLab Planets
    return state
