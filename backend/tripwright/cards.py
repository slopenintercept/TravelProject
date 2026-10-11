"""Review-screen cards: every decision with its price and reasoning.

Flights and stays are per traveler; attractions and transport are shared by the group.
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
    # "flight:<traveler>", "stay:<traveler>:<n>", "attraction:<id>", "leg:<id>",
    # or the most-travelers-pick cards "lodging" / "transport"
    id: str
    category: Literal["flights", "lodging", "attractions", "transport"]
    kind: Literal["item", "default"] = "item"  # "default" is the most-travelers-pick card
    traveler: str | None = None  # whose flight or stay this is (traveler id); None for shared cards
    title: str
    detail: str = ""
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


def _default(card_id: str, category: str, choice: CommonChoice, note: str, switch_label: str, flag: Flag | None) -> Card:
    return Card(
        id=card_id, category=category, kind="default",
        title=f"Most travelers here pick: {choice.choice}",
        detail=", ".join(choice.details), reasoning=f"Because {choice.because.removeprefix('because ').rstrip('.')}. {note}".strip(),
        sources=choice.sources, switch_label=switch_label, flag=flag,
    )


def review_cards(state: TripState) -> list[Card]:
    cards: list[Card] = []
    everyone = [t.id for t in state.travelers]

    def status(card_id: str, included: bool = True) -> str:
        return "removed" if not included else state.approvals.get(card_id, "proposed")

    for t in state.travelers:
        if not t.flights:
            continue
        f, card_id = t.flights.selected, f"flight:{t.id}"
        cards.append(Card(
            id=card_id, category="flights", traveler=t.id, title=f"{f.airline}: {f.origin} to {f.destination}",
            detail=f"Leaves {_clock(f.depart_at)} · lands {_clock(f.arrive_at)} · "
                   f"{f.duration_minutes // 60}h {f.duration_minutes % 60:02d}m · "
                   f"{'nonstop' if not f.stops else f'{f.stops} stop' + 's' * (f.stops > 1)} · "
                   f"flight home leaves {_clock(f.return_depart_at)}",
            price_usd=f.price_usd, reasoning=f.tradeoff, sources=[f.source],
            booking_url=flight_link(f, state.dates.start, state.dates.end, 1) if state.dates else f.booking_url,
            status=status(card_id), flag=state.flags.get(card_id),
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
                detail=f"{stay.check_in:%b %d} to {stay.check_out:%b %d} · {room.nights} night{'s' * (room.nights > 1)} · "
                       f"{room.neighborhood or room.kind} · rated {room.rating or 'n/a'} · {room.location_note}",
                price_usd=room.price_total_usd, reasoning=stay.reasoning, sources=[room.source],
                booking_url=stay_link(room), status=status(card_id), flag=state.flags.get("lodging"),
                alternatives=[
                    Alternative(id=o.id, title=o.name, detail=f"rated {o.rating or 'n/a'} · {o.location_note}",
                                price_usd=o.price_total_usd)
                    for o in stay.options if o.id != room.id
                ],
            ))

    on_plan = {i.ref_id: i.travelers for i in state.itinerary if i.kind == "attraction"}
    for a in state.attractions:
        hours = f"{a.opens:%H:%M} to {a.closes:%H:%M}" if a.opens and a.closes else "open all day"
        going = on_plan.get(a.id) or [t for t in everyone if t not in a.skip_by]
        cards.append(Card(
            id=f"attraction:{a.id}", category="attractions", title=a.name,
            detail=f"{a.city} · {hours} · about {a.duration_minutes // 60}h {a.duration_minutes % 60:02d}m"
                   f"{' · ' + a.availability_note if a.availability_note else ''}",
            price_usd=a.ticket_price_usd * len(going), reasoning=a.why, sources=[a.source],
            booking_url=a.booking_url, status=status(f"attraction:{a.id}", a.included), must_have=a.must_have,
            flag=state.flags.get("attractions"), need_by=state.names(a.need_by), want_by=state.names(a.want_by),
            skip_by=state.names(a.skip_by), going=state.names(on_plan.get(a.id, [])),
        ))

    if state.transport:
        choice = state.transport.common_choice
        note = state.transport.rideshare_note
        if state.transport_override:
            note += " You added a rental car."
        cards.append(_default("transport", "transport", choice, note,
                              "Remove the rental car" if state.transport_override else "Add a rental car",
                              state.flags.get("transport")))
        for leg in state.transport.legs:
            route = f"{leg.from_place} to {leg.to_place}" if leg.from_place and leg.to_place else leg.kind.replace("_", " ")
            cards.append(Card(
                id=f"leg:{leg.id}", category="transport", title=f"{leg.mode}: {route}",
                detail=f"{leg.duration_minutes} min" if leg.duration_minutes else "",
                price_usd=leg.price_usd * (len(everyone) if leg.per_person else 1), reasoning=leg.notes,
                sources=[leg.source], booking_url=leg.booking_url, status=status(f"leg:{leg.id}", leg.included),
                must_have=leg.kind == "intercity", flag=state.flags.get("transport"),
            ))
    return cards
