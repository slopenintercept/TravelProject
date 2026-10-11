"""Review-screen cards: every decision with its price and reasoning.

Flights, stays and transport are per traveler; attractions are shared by the group.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .booking import flight_link, stay_link
from .models import CommonChoice, Flag, Source, TripState


class Alternative(BaseModel):
    id: str
    title: str
    detail: str
    price_usd: float


class Card(BaseModel):
    # "flight:<traveler>", "stay:<traveler>:<n>", "attraction:<id>", "leg:<traveler>:<id>",
    # or the most-travelers-pick cards "lodging" / "transport"
    id: str
    category: Literal["flights", "lodging", "attractions", "transport"]
    kind: Literal["item", "default"] = "item"  # "default" is the most-travelers-pick card
    traveler: str | None = None  # whose flight, stay or leg this is (traveler id); None for shared cards
    title: str
    detail: str = ""  # short facts joined by " · "; the review screen shows each as a tag
    note: str = ""  # a sentence too long for a tag, shown as plain text under them
    price_usd: float = 0
    reasoning: str = ""
    sources: list[Source] = []
    booking_url: str | None = None
    status: Literal["proposed", "approved", "removed"] = "proposed"
    must_have: bool = False
    flag: Flag | None = None
    alternatives: list[Alternative] = []
    switch_label: str | None = None  # one-click switch to the alternative default
    # Attractions only: names of who needs it, who wants it, who skips it, and who is going.
    need_by: list[str] = []
    want_by: list[str] = []
    skip_by: list[str] = []
    going: list[str] = []


def _clock(dt) -> str:
    return f"{dt:%a %b %d, %H:%M}" if dt else "time to confirm"


def _duration(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    return " ".join(filter(None, [f"{hours}H" if hours else "", f"{mins}M" if mins else ""]))


def _rating(rating: float | None) -> str:
    return f"{rating} Rating" if rating else "No rating"


def _note(location_note: str) -> str:
    """A searched room's note is "560 reviews, $97/night": two facts, so two tags."""
    return location_note.replace(", ", " · ").title()


def _default(card_id: str, category: str, choice: CommonChoice, note: str, switch_label: str | None, flag: Flag | None) -> Card:
    return Card(
        id=card_id, category=category, kind="default",
        title=f"Most travelers here pick: {choice.choice}",
        detail=", ".join(choice.details), reasoning=f"Because {choice.because.removeprefix('because ').rstrip('.')}. {note}".strip(),
        sources=choice.sources, switch_label=switch_label, flag=flag,
    )


def review_cards(state: TripState) -> list[Card]:
    cards: list[Card] = []
    everyone = [t.id for t in state.travelers]

    def status(card_id: str, included: bool = True, chosen: str = "approved") -> str:
        """An approval is for the flight or room chosen at the time (`chosen` is its id). When another one is
        chosen, by a swap, a budget fix, a new confirm or a new search, the card is back to proposed."""
        if not included:
            return "removed"
        return "approved" if state.approvals.get(card_id) == chosen else "proposed"

    for t in state.travelers:
        if not t.flights:
            continue
        f, card_id = t.flights.selected, f"flight:{t.id}"
        cards.append(Card(
            id=card_id, category="flights", traveler=t.id, title=f"{f.airline}: {f.origin} to {f.destination}",
            detail=f"Leaves {_clock(f.depart_at)} · Lands {_clock(f.arrive_at)} · "
                   f"{_duration(f.duration_minutes)} · "
                   f"{'Nonstop' if not f.stops else f'{f.stops} Stop' + 's' * (f.stops > 1)} · "
                   f"Flies home {_clock(f.return_depart_at)}",
            price_usd=f.price_usd, reasoning=f.tradeoff, sources=[f.source],
            booking_url=flight_link(f, state.dates.start, state.dates.end, 1) if state.dates else f.booking_url,
            status=status(card_id, chosen=f.id), flag=state.flags.get(card_id),
            alternatives=[
                Alternative(id=o.id, title=f"{o.airline}, lands {_clock(o.arrive_at)}", detail=o.tradeoff,
                            price_usd=o.price_usd)
                for o in t.flights.options if o.id != f.id
            ],
        ))

    if state.lodging:
        choice = state.lodging.common_choice
        current = state.lodging_override or choice.choice
        other = "hotel" if current == "airbnb" else "airbnb"
        note = f"You switched to {current}." if current != choice.choice else ""
        cards.append(_default("lodging", "lodging", choice, note,
                              f"Switch to {'a hotel' if other == 'hotel' else 'Airbnb'}", state.flags.get("lodging")))
    for t in state.travelers:
        for i, stay in enumerate(t.lodging.stays if t.lodging else []):
            room, card_id = stay.selected, f"stay:{t.id}:{i}"
            cards.append(Card(
                id=card_id, category="lodging", traveler=t.id, title=f"{stay.city}: {room.name}",
                detail=f"{stay.check_in:%b %d} to {stay.check_out:%b %d} · {room.nights} Night{'s' * (room.nights > 1)} · "
                       f"{room.neighborhood or room.kind.capitalize()} · {_rating(room.rating)} · {_note(room.location_note)}",
                price_usd=room.price_total_usd, reasoning=stay.reasoning, sources=[room.source],
                booking_url=stay_link(room), status=status(card_id, chosen=room.id), flag=state.flags.get("lodging"),
                alternatives=[
                    Alternative(id=o.id, title=o.name, detail=f"{_rating(o.rating)} · {_note(o.location_note)}",
                                price_usd=o.price_total_usd)
                    for o in stay.options if o.id != room.id
                ],
            ))

    on_plan = {i.ref_id: i.travelers for i in state.itinerary if i.kind == "attraction"}
    for a in state.attractions:
        hours = f"Open {a.opens:%H:%M} to {a.closes:%H:%M}" if a.opens and a.closes else "Open all day"
        going = on_plan.get(a.id) or [t for t in everyone if t not in a.skip_by]
        cards.append(Card(
            id=f"attraction:{a.id}", category="attractions", title=a.name,
            detail=f"{a.city} · {hours} · {_duration(a.duration_minutes)}", note=a.availability_note,
            price_usd=a.ticket_price_usd * len(going), reasoning=a.why, sources=[a.source],
            booking_url=a.booking_url, status=status(f"attraction:{a.id}", a.included), must_have=a.must_have,
            flag=state.flags.get("attractions"), need_by=state.names(a.need_by), want_by=state.names(a.want_by),
            skip_by=state.names(a.skip_by), going=state.names(on_plan.get(a.id, [])),
        ))

    if state.transport:
        cards.append(_default("transport", "transport", state.transport.common_choice, state.transport.rideshare_note,
                              None, state.flags.get("transport")))
    for t in state.travelers:
        for leg in t.legs:
            if leg.kind == "rental_car" and not leg.included:
                continue  # only shown to a traveler who asked for one
            route = f"{leg.from_place} to {leg.to_place}" if leg.from_place and leg.to_place else leg.kind.replace("_", " ")
            card_id = f"leg:{t.id}:{leg.id}"
            cards.append(Card(
                id=card_id, category="transport", traveler=t.id, title=f"{leg.mode}: {route}",
                detail=_duration(leg.duration_minutes),
                price_usd=leg.price_usd, reasoning=leg.notes,
                sources=[leg.source], booking_url=leg.booking_url, status=status(card_id, leg.included),
                must_have=leg.kind == "intercity", flag=state.flags.get("transport"),
                alternatives=[
                    Alternative(id=o.id, title=o.mode, price_usd=o.price_usd,
                                detail=" · ".join(filter(None, [_duration(o.duration_minutes), o.notes])))
                    for o in leg.alternatives
                ],
            ))
    return cards
