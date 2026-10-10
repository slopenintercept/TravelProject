"""The finish screen: one step per thing to book, with a link that already carries the trip's details.

Where a provider accepts the details in its URL, the link opens with them filled in
(`filled` says which). Where it doesn't (ticket and rail sites), the step links to the
right page and `todo` says exactly what to enter. Nothing here books or pays: the user
finishes on the provider's site.
"""

from __future__ import annotations

import base64
from datetime import date
from typing import Literal
from urllib.parse import quote, urlsplit

from pydantic import BaseModel

from .geo import same_city
from .models import FlightOption, LodgingOption, TripState
from .scheduler import stay_plan

FLIGHTS_URL = "https://www.google.com/travel/flights?q={query}&hl=en&gl=us&curr=USD"
HOTEL_PAGE = "/travel/hotels/entity/"


class BookingStep(BaseModel):
    id: str
    category: Literal["flights", "lodging", "attractions", "transport"]
    traveler: str | None = None  # whose booking this is (traveler id); None for shared tickets and transport
    who: list[str] = []  # names of the people this is for
    title: str
    when: str
    provider: str = ""
    filled: list[str] = []  # details the link already carries into the provider's page
    todo: str = ""  # what is left to choose or enter there
    price_usd: float = 0
    url: str | None = None  # None: nothing to book
    # What the link is: opens with the details filled in, a booking page, or a page on how to buy.
    link: Literal["filled", "booking", "info"] = "info"


def _people(n: int, noun: str = "traveler") -> str:
    return f"{n} {noun}{'s' * (n != 1)}"


def _span(a: date, b: date) -> str:
    return f"{a:%a %b} {a.day} – {b:%a %b} {b.day}"


def _host(url: str) -> str:
    return urlsplit(url).netloc.removeprefix("www.")


def flight_link(flight: FlightOption, depart: date, return_: date, travelers: int) -> str:
    """Google Flights opened on this route, these dates, this airline and this many travelers."""
    carrier = flight.airline.split(" and ")[0].split(".")[0]
    query = f"{carrier} flights to {flight.destination} from {flight.origin} on {depart} through {return_}"
    if travelers > 1:
        query += f" for {travelers} adults"
    return FLIGHTS_URL.format(query=quote(query))


def _varint(n: int) -> bytes:
    out = b""
    while True:
        low, n = n & 0x7F, n >> 7
        out += bytes([low | (0x80 if n else 0)])
        if not n:
            return out


def _wrap(field: int, payload: bytes) -> bytes:
    return _varint(field << 3 | 2) + _varint(len(payload)) + payload


def hotel_dates_param(check_in: date, check_out: date) -> str:
    """Google Hotels' `ts` URL parameter for a stay: the same date block its own search links carry.

    The parameter is undocumented. If Google stops honouring it, the link still opens the
    right hotel, just on its default dates.
    """
    def day(d: date) -> bytes:
        return b"\x08" + _varint(d.year) + b"\x10" + _varint(d.month) + b"\x18" + _varint(d.day)

    stay = _wrap(1, day(check_in)) + _wrap(2, day(check_out)) + b"\x18" + _varint((check_out - check_in).days)
    return base64.urlsafe_b64encode(b"\x08\x01" + _wrap(3, _wrap(2, _wrap(2, stay)))).decode().rstrip("=")


def stay_link(room: LodgingOption) -> str:
    """The room's own page with the stay dates set. Airbnb links already carry dates and guests."""
    if room.kind == "hotel" and HOTEL_PAGE in room.booking_url:
        page = room.booking_url.split("?")[0]
        return f"{page}?ts={hotel_dates_param(room.check_in, room.check_out)}&hl=en&gl=us&curr=USD"
    return room.booking_url


def booking_steps(state: TripState) -> list[BookingStep]:
    """Each traveler's own flight and stays first, then the tickets and transport the group shares."""
    steps: list[BookingStep] = []
    everyone = [t.id for t in state.travelers]

    for t in state.travelers:
        if t.flights and state.dates:
            f, d = t.flights.selected, state.dates
            home = f" Then the {f.return_depart_at:%H:%M} flight home." if f.return_depart_at else ""
            steps.append(BookingStep(
                id=f"flight:{t.id}", category="flights", traveler=t.id, who=[t.name],
                title=f"{f.airline}: {f.origin} to {f.destination}",
                when=_span(d.start, d.end), provider="Google Flights",
                filled=[f"{t.origin} to {f.destination}", _span(d.start, d.end), _people(1),
                        f.airline.split(" and ")[0].split(".")[0]],
                todo=f"Choose the {f.depart_at:%H:%M} departure, landing {f.arrive_at:%a %b} {f.arrive_at.day} at {f.arrive_at:%H:%M}.{home}",
                price_usd=f.price_usd, url=flight_link(f, d.start, d.end, 1), link="filled",
            ))
        for i, stay in enumerate(t.lodging.stays if t.lodging else []):
            room = stay.selected
            nights = f"{room.nights} night{'s' * (room.nights != 1)}"
            hotel = room.kind == "hotel"
            steps.append(BookingStep(
                id=f"stay:{t.id}:{i}", category="lodging", traveler=t.id, who=[t.name],
                title=f"{stay.city}: {room.name}",
                when=_span(stay.check_in, stay.check_out), provider="Google Hotels" if hotel else "Airbnb",
                filled=[room.name, _span(stay.check_in, stay.check_out), nights] + ([] if hotel else [_people(1, "guest")]),
                todo="Pick a room and one of the booking sites listed." if hotel else "Check the total and reserve.",
                price_usd=room.price_total_usd, url=stay_link(room), link="filled",
            ))

    scheduled = {i.ref_id: i for i in state.itinerary if i.kind == "attraction"}
    for a in sorted((a for a in state.attractions if a.included and a.id in scheduled),
                    key=lambda a: (scheduled[a.id].day, scheduled[a.id].start)):
        item = scheduled[a.id]
        going = state.names(item.travelers)
        when = f"{item.day:%a %b} {item.day.day}, {item.start:%H:%M} – {item.end:%H:%M}"
        if a.ticket_price_usd > 0:
            url = a.booking_url or a.source.url
            steps.append(BookingStep(
                id=f"attraction:{a.id}", category="attractions", title=a.name, when=when, provider=_host(url), who=going,
                todo=f"Buy {_people(len(going), 'adult ticket')} for {item.day:%A, %B} {item.day.day}. {a.availability_note}".strip(),
                price_usd=a.ticket_price_usd * len(going), url=url, link="booking" if a.booking_url else "info",
            ))
        else:
            steps.append(BookingStep(id=f"attraction:{a.id}", category="attractions", title=a.name, when=when, who=going,
                                     todo=f"No ticket needed. {a.availability_note}".strip()))

    arrivals = [t.flights.selected.arrive_at.date() for t in state.travelers if t.flights]
    if state.transport and state.dates and state.route and arrivals:
        plan = stay_plan(state)
        hops = [b_in for (a, _, _), (b, b_in, _) in zip(plan, plan[1:]) if not same_city(a, b)]
        transfers = [min(arrivals), state.dates.end]
        n = len(everyone)
        for leg in state.transport.legs:
            if not leg.included:
                continue
            if leg.kind == "intercity":
                day = hops.pop(0) if hops else None
            elif leg.kind == "airport_transfer":
                day = transfers.pop(0) if transfers else None
            else:
                day = min(arrivals)
            route = f": {leg.from_place} to {leg.to_place}" if leg.from_place and leg.to_place else ""
            url = leg.booking_url or leg.source.url
            buy = _people(n, "ticket") if leg.per_person else "one booking"
            steps.append(BookingStep(
                id=f"leg:{leg.id}", category="transport", title=f"{leg.mode}{route}", who=state.names(everyone),
                when=f"{day:%a %b} {day.day}" if day else "", provider=_host(url),
                todo=f"Buy {buy}{f' for {day:%A, %B} {day.day}' if day and leg.kind != 'local_pass' else ' on arrival'}. {leg.notes}".strip(),
                price_usd=leg.price_usd * (n if leg.per_person else 1), url=url,
                link="booking" if leg.booking_url else "info",
            ))
    return steps
