from datetime import date
from urllib.parse import unquote

from tripwright.booking import booking_steps, flight_link, hotel_dates_param, stay_link
from tripwright.validate import replan


def test_flight_link_carries_route_dates_airline_and_travelers(state):
    link = unquote(flight_link(state.travelers[0].flights.selected, date(2026, 11, 10), date(2026, 11, 17), 2))
    assert "United flights to NRT from MCI on 2026-11-10 through 2026-11-17 for 2 adults" in link


def test_hotel_link_opens_the_hotel_page_on_the_stay_dates(state):
    # The date block for Nov 11 to 14, as checked against live Google Hotels pages.
    assert hotel_dates_param(date(2026, 11, 11), date(2026, 11, 14)) == "CAEaGBIWEhQKBwjqDxALGAsSBwjqDxALGA4YAw"
    room = state.travelers[0].lodging.stays[0].selected
    room.booking_url = "https://www.google.com/travel/hotels/entity/ChoIabc?q=hotels+in+Tokyo&ved=xyz"
    assert stay_link(room) == ("https://www.google.com/travel/hotels/entity/ChoIabc"
                               "?ts=CAEaGBIWEhQKBwjqDxALGAsSBwjqDxALGA4YAw&hl=en&gl=us&curr=USD")

    room.kind, room.booking_url = "airbnb", "https://www.airbnb.com/rooms/1?adults=1&check_in=2026-11-11&check_out=2026-11-14"
    assert stay_link(room) == room.booking_url  # Airbnb's own link already has dates and guests


def test_steps_cover_everything_on_the_plan_in_booking_order(state):
    replan(state)
    steps = booking_steps(state)
    assert [s.category for s in steps] == ["flights"] + ["lodging"] * 3 + ["attractions"] * 5 + ["transport"] * 3

    flight = steps[0]
    assert flight.filled == ["Kansas City to NRT", "Tue Nov 10 – Tue Nov 17", "1 traveler", "United"]
    assert "06:00 departure" in flight.todo and "17:30 flight home" in flight.todo

    by_title = {s.title: s for s in steps}
    assert by_title["Tokyo Disneyland"].url and "1 adult ticket" in by_title["Tokyo Disneyland"].todo
    assert by_title["Senso-ji"].url is None and by_title["Senso-ji"].todo.startswith("No ticket needed")
    # Each leg is dated from the plan: the Shinkansen on the day the stay changes city.
    assert by_title["Shinkansen: Tokyo to Kyoto"].when == "Sat Nov 14"
    assert by_title["Shinkansen: Kyoto to Tokyo"].when == "Mon Nov 16"
    assert by_title["Narita Express: NRT to Tokyo"].when == "Wed Nov 11"


def test_removed_and_unscheduled_items_are_left_out(state):
    state.attractions[1].included = False  # Senso-ji
    replan(state)
    assert "Senso-ji" not in {s.title for s in booking_steps(state)}
