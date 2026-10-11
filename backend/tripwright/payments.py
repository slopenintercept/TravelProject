"""Paying together: each traveler approves their own share, and nobody is charged unless everyone is in.

Approving places a hold on a test card for that traveler's share of the trip. When every traveler has a
hold, all of them are charged at once; if anyone backs out first, every hold is released. Deterministic:
no LLM calls in here.

With STRIPE_SECRET_KEY set, each hold is a Stripe test-mode PaymentIntent (authorize now, capture later).
Without it the holds are kept in the trip only. Either way no real card is used and no money moves.
"""

from __future__ import annotations

import stripe

from . import config
from .models import Payment, TripState

# The cards a traveler can pick: the label shown, and Stripe's test payment method for it.
CARDS = {
    "visa": ("Visa ···· 4242", "pm_card_visa"),
    "mastercard": ("Mastercard ···· 4444", "pm_card_mastercard"),
    "declined": ("Visa ···· 0002", "pm_card_visa_chargeDeclined"),  # always refused
}


def _intents():
    """Stripe's PaymentIntents in test mode, or None to keep the holds in the app."""
    key = config.STRIPE_SECRET_KEY
    if not key:
        return None
    if not key.startswith(("sk_test_", "rk_test_")):
        raise ValueError("STRIPE_SECRET_KEY is not a test key. Tripwright never moves real money.")
    return stripe.StripeClient(key).v1.payment_intents


def _paid(state: TripState) -> bool:
    return any(p.status == "captured" for p in state.payments.values())


def approve(state: TripState, traveler_id: str, card: str) -> str:
    """Place a hold for this traveler's share. Once every traveler has one, charge them all.
    Returns what happened, for the traveler who asked."""
    if state.stage != "review" or traveler_id not in state.budgets:
        raise ValueError("The trip isn't planned yet")
    if _paid(state):
        raise ValueError("This trip is already paid")
    if (current := state.payments.get(traveler_id)) and current.status == "held":
        raise ValueError("Your share is already on hold")
    traveler, amount = state.traveler(traveler_id), state.budgets[traveler_id].spent_usd
    if amount <= 0:
        raise ValueError("There is nothing to pay for yet")

    label, method = CARDS[card]
    payment = Payment(card=label, amount_usd=amount, status="held")
    intents = _intents()
    if intents:
        try:
            payment.ref = intents.create(params={
                "amount": round(amount * 100), "currency": "usd", "capture_method": "manual", "confirm": True,
                "payment_method": method, "automatic_payment_methods": {"enabled": True, "allow_redirects": "never"},
                "description": f"Tripwright: {traveler.name}'s share of {state.request.destination}",
                "metadata": {"trip": state.id, "traveler": traveler.name},
            }).id
        except stripe.CardError:
            payment.status = "declined"
    elif card == "declined":
        payment.status = "declined"
    state.payments[traveler_id] = payment
    if payment.status == "declined":
        return f"{label} was declined, so no hold was placed. Try another card."

    holds = [state.payments.get(t.id) for t in state.travelers]
    waiting = [t.name for t, p in zip(state.travelers, holds) if p is None or p.status != "held"]
    if waiting:
        approve = "approves" if len(waiting) == 1 else "approve"
        return f"${amount:,.0f} is on hold. Nobody is charged until {' and '.join(waiting)} {approve}."
    for hold in holds:  # everyone is in
        if intents and hold.ref:
            intents.capture(hold.ref)
        hold.status = "captured"
    return "Everyone is in. Every card was charged." if len(holds) > 1 else "Your card was charged."


def back_out(state: TripState, traveler_id: str) -> str:
    """A traveler backs out before the trip is paid: every hold is released, so nobody is charged."""
    if _paid(state):
        raise ValueError("This trip is already paid")
    holds = [p for p in state.payments.values() if p.status == "held"]
    if not holds:
        raise ValueError("There are no holds to release")
    intents = _intents()
    for hold in holds:
        if intents and hold.ref:
            intents.cancel(hold.ref)
        hold.status = "released"
    return f"{state.traveler(traveler_id).name} backed out. Every hold was released and nobody was charged."
