"""Paying together: a hold on each traveler's share, charged only when everyone is in."""

from types import SimpleNamespace

import pytest
import stripe
from fastapi.testclient import TestClient

from tripwright import api, payments
from tripwright.budget import compute_budget

client = TestClient(api.app)


@pytest.fixture
def trip(group):
    """Alex and Sam at review, each with a share to pay."""
    group.stage = "review"
    group.budgets = {t.id: compute_budget(group, t) for t in group.travelers}
    api._live[group.id] = group
    yield group
    api._live.pop(group.id, None)


def statuses(trip):
    return {traveler: p.status for traveler, p in trip.payments.items()}


def test_a_hold_charges_nobody_until_everyone_is_in(trip):
    payments.approve(trip, "p1", "visa")
    assert statuses(trip) == {"p1": "held"}
    assert trip.payments["p1"].amount_usd == trip.budgets["p1"].spent_usd
    assert trip.payments["p1"].card == "Visa ···· 4242"

    assert payments.approve(trip, "p2", "mastercard") == "Everyone is in. Every card was charged."
    assert statuses(trip) == {"p1": "captured", "p2": "captured"}


def test_a_declined_card_places_no_hold_and_can_be_retried(trip):
    payments.approve(trip, "p1", "visa")
    assert "declined" in payments.approve(trip, "p2", "declined")
    assert statuses(trip) == {"p1": "held", "p2": "declined"}  # Alex is still not charged

    payments.approve(trip, "p2", "visa")
    assert statuses(trip) == {"p1": "captured", "p2": "captured"}


def test_backing_out_releases_every_hold(trip):
    payments.approve(trip, "p1", "visa")
    assert payments.back_out(trip, "p2").startswith("Sam backed out")  # Sam had no hold of their own
    assert statuses(trip) == {"p1": "released"}

    payments.approve(trip, "p1", "visa")  # and the group can start again
    assert statuses(trip) == {"p1": "held"}


def test_nothing_changes_once_the_trip_is_paid(trip):
    payments.approve(trip, "p1", "visa")
    with pytest.raises(ValueError, match="already on hold"):
        payments.approve(trip, "p1", "mastercard")
    payments.approve(trip, "p2", "visa")
    for change in (lambda: payments.approve(trip, "p1", "visa"), lambda: payments.back_out(trip, "p1")):
        with pytest.raises(ValueError, match="already paid"):
            change()


def test_there_is_nothing_to_approve_before_the_trip_is_planned(trip):
    trip.stage = "choosing"
    with pytest.raises(ValueError, match="isn't planned"):
        payments.approve(trip, "p1", "visa")
    with pytest.raises(ValueError, match="no holds"):
        payments.back_out(trip, "p1")


class FakeIntents:
    """Stands in for Stripe's PaymentIntents: records the calls and refuses the declining test card."""

    def __init__(self):
        self.calls = []

    def create(self, params):
        if params["payment_method"] == "pm_card_visa_chargeDeclined":
            raise stripe.CardError("Your card was declined.", None, "card_declined")
        self.calls.append(("create", params["amount"], params["capture_method"], params["payment_method"]))
        return SimpleNamespace(id=f"pi_{len(self.calls)}")

    def capture(self, intent):
        self.calls.append(("capture", intent))

    def cancel(self, intent):
        self.calls.append(("cancel", intent))


def test_with_a_stripe_key_each_hold_is_an_uncaptured_payment(trip, monkeypatch):
    intents = FakeIntents()
    monkeypatch.setattr(payments, "_intents", lambda: intents)
    cents = round(trip.budgets["p1"].spent_usd * 100)

    payments.approve(trip, "p1", "visa")
    assert intents.calls == [("create", cents, "manual", "pm_card_visa")] and trip.payments["p1"].ref == "pi_1"
    payments.approve(trip, "p2", "declined")
    assert statuses(trip) == {"p1": "held", "p2": "declined"} and len(intents.calls) == 1

    payments.back_out(trip, "p2")
    assert intents.calls[-1] == ("cancel", "pi_1")

    payments.approve(trip, "p1", "visa")
    payments.approve(trip, "p2", "mastercard")
    assert intents.calls[-2:] == [("capture", "pi_3"), ("capture", "pi_4")]


def test_only_a_stripe_test_key_is_accepted(trip, monkeypatch):
    monkeypatch.setattr(payments.config, "STRIPE_SECRET_KEY", "sk_live_abc")
    with pytest.raises(ValueError, match="not a test key"):
        payments.approve(trip, "p1", "visa")
    assert trip.payments == {}


def test_each_traveler_approves_as_themselves(trip):
    pay = lambda card, traveler=None: client.post(  # noqa: E731
        f"/api/trips/{trip.id}/payments", json={"card": card}, headers={"X-Traveler": traveler} if traveler else {})
    assert pay("visa").status_code == 403  # nobody in particular
    assert pay("amex", "p2").status_code == 422  # not one of the test cards

    held = pay("visa", "p2")
    assert held.status_code == 200 and "until Alex approves." in held.json()["message"]
    assert held.json()["state"]["payments"]["p2"]["status"] == "held"

    released = client.delete(f"/api/trips/{trip.id}/payments", headers={"X-Traveler": "p1"})
    assert released.status_code == 200 and statuses(trip) == {"p2": "released"}
    assert client.delete(f"/api/trips/{trip.id}/payments", headers={"X-Traveler": "p1"}).status_code == 400
