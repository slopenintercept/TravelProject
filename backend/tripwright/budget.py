"""Budget math and the swap optimizer, per traveler. Deterministic: no LLM calls in here.

Each traveler's budget covers their own flight and lodging, tickets for the
attractions they attend, and their share of transport.
"""

from __future__ import annotations

from itertools import product

from .models import BudgetSummary, Swap, SwapProposal, Traveler, TripState

# Share of a traveler's budget each category is allotted before any results come in.
SHARES = {"flights": 0.50, "lodging": 0.28, "attractions": 0.10, "transport": 0.12}


def allotted(traveler: Traveler) -> dict[str, float]:
    return {c: round(traveler.budget_usd * s, 2) for c, s in SHARES.items()}


def category_costs(state: TripState, traveler: Traveler) -> dict[str, float]:
    visits = [i for i in state.itinerary if i.kind == "attraction"]
    if visits:  # once there is a schedule, a traveler pays only for what they attend
        going = {i.ref_id for i in visits if traveler.id in i.travelers}
        tickets = sum(a.ticket_price_usd for a in state.attractions if a.id in going)
    else:
        tickets = sum(a.ticket_price_usd for a in state.attractions if a.included)
    return {
        "flights": traveler.flights.selected.price_usd if traveler.flights else 0.0,
        "lodging": sum(s.selected.price_total_usd for s in traveler.lodging.stays) if traveler.lodging else 0.0,
        "attractions": tickets,
        "transport": sum(
            leg.price_usd if leg.per_person else leg.price_usd / len(state.travelers)
            for leg in (state.transport.legs if state.transport else [])
            if leg.included
        ),
    }


def compute_budget(state: TripState, traveler: Traveler) -> BudgetSummary:
    costs = {c: round(v, 2) for c, v in category_costs(state, traveler).items()}
    spent = round(sum(costs.values()), 2)
    return BudgetSummary(
        total_usd=traveler.budget_usd, by_category=costs, allotted=allotted(traveler),
        spent_usd=spent, remaining_usd=round(traveler.budget_usd - spent, 2),
    )


def optimize_budget(state: TripState, traveler: Traveler) -> SwapProposal | None:
    """If a traveler is over budget, propose the fewest swaps of their own flight and rooms that fit.

    Tries every flight x lodging combination: fewest swaps first, then the lowest total.
    Shared attractions are left alone, so nobody's must-sees are dropped for one person's
    budget. Returns None when the plan already fits, and `fits=False` when no swap is enough.
    """
    costs = category_costs(state, traveler)
    total, budget = sum(costs.values()), traveler.budget_usd
    if total <= budget or not traveler.flights or not traveler.lodging:
        return None

    shared = costs["attractions"] + costs["transport"]
    stays = traveler.lodging.stays
    candidates = []
    for flight, *rooms in product(traveler.flights.options, *(s.options for s in stays)):
        cost = shared + flight.price_usd + sum(r.price_total_usd for r in rooms)
        swaps = (flight.id != traveler.flights.selected_id) + sum(r.id != s.selected_id for r, s in zip(rooms, stays))
        candidates.append((cost > budget, swaps, cost, flight, rooms))
    fitting = [c for c in candidates if not c[0]]
    # Fewest swaps that fit; if nothing fits, the cheapest combination gets as close as possible.
    over, _, cost, flight, rooms = (min(fitting, key=lambda c: c[1:3]) if fitting
                                    else min(candidates, key=lambda c: (c[2], c[1])))

    proposal: list[Swap] = []
    current = traveler.flights.selected
    if flight.id != current.id:
        proposal.append(Swap(
            category="flights", action="swap", from_id=current.id, to_id=flight.id,
            title=f"Fly {flight.airline} instead of {current.airline}",
            saves_usd=round(current.price_usd - flight.price_usd, 2),
        ))
    for room, stay in zip(rooms, stays):
        if room.id != stay.selected_id:
            proposal.append(Swap(
                category="lodging", action="swap", from_id=stay.selected_id, to_id=room.id,
                title=f"{stay.city}: stay at {room.name} instead of {stay.selected.name}",
                saves_usd=round(stay.selected.price_total_usd - room.price_total_usd, 2),
            ))
    return SwapProposal(swaps=proposal, new_total_usd=round(cost, 2), fits=not over)


def apply_swaps(traveler: Traveler, proposal: SwapProposal) -> None:
    for swap in proposal.swaps:
        if swap.category == "flights":
            traveler.flights.selected_id = swap.to_id
        elif swap.category == "lodging":
            for stay in traveler.lodging.stays:
                if stay.selected_id == swap.from_id:
                    stay.selected_id = swap.to_id
