"""Scripted lodging searches. Deterministic Playwright: no LLM calls.

Hotels come from Google Hotels: Booking.com answers plain headless Chromium with a
block page, and the rule is to switch provider rather than get around it. Airbnb
loads normally.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import quote

from ..recorded import cached
from . import browser

MAX_OPTIONS = 8
MIN_REVIEWS = 30  # skip listings too new to judge

HOTELS_URL = "https://www.google.com/travel/search?q={query}&hl=en&gl=us&curr=USD"
HOTEL_CARDS = """() => {
  const cards = [...document.querySelectorAll('c-wiz')].filter(c => c.querySelector('h2') && /\\$\\d/.test(c.innerText));
  return cards.filter(c => !cards.some(o => o !== c && c.contains(o))).map(c => ({
    name: c.querySelector('h2').innerText,
    labels: [...c.querySelectorAll('[aria-label]')].map(e => e.getAttribute('aria-label')),
    href: (c.querySelector('a[href]') || {}).href || '',
  }));
}"""
# The dates the results are priced for, read back from the page, e.g. ["Tue, Jan 19", "Fri, Jan 22"].
HOTEL_DATES = """() => ['Check-in', 'Check-out'].map(label =>
  (document.querySelector(`input[aria-label="${label}"]`) || {}).value || '')"""
HOTEL_PRICE = re.compile(r"Prices starting from \$([\d,]+)")
HOTEL_RATING = re.compile(r"([\d.]+) out of 5 stars from ([\d.,KM]+) reviews")

AIRBNB_URL = "https://www.airbnb.com/s/{place}/homes?checkin={check_in}&checkout={check_out}&adults={guests}&currency=USD"
AIRBNB_CARD = "[data-testid='card-container']"
AIRBNB_CARDS = """els => els.map(c => ({
  text: c.innerText,
  title: (c.querySelector("[data-testid='listing-card-title']") || {}).innerText || '',
  name: (c.querySelector("[data-testid='listing-card-name']") || {}).innerText || '',
  href: (c.querySelector("a[href*='/rooms/']") || {}).href || '',
}))"""
AIRBNB_PRICE = re.compile(r"\$([\d,]+)\s+for\s+(\d+)\s+nights?")
AIRBNB_RATING = re.compile(r"([\d.]+) out of 5 average rating,\s*([\d,]+) reviews")


def _count(text: str) -> int:
    scale = {"K": 1_000, "M": 1_000_000}.get(text[-1], 1)
    return int(float(text.rstrip("KM").replace(",", "")) * scale)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def parse_hotel(card: dict, nights: int) -> dict | None:
    labels = " | ".join(card["labels"])
    price, rating = HOTEL_PRICE.search(labels), HOTEL_RATING.search(labels)
    if not price or not rating or _count(rating[2]) < MIN_REVIEWS:
        return None
    nightly = float(price[1].replace(",", ""))
    return {
        "name": card["name"], "kind": "hotel", "rating": float(rating[1]), "reviews": _count(rating[2]),
        "price_per_night_usd": nightly, "price_total_usd": round(nightly * nights, 2), "booking_url": card["href"],
    }


def parse_airbnb(card: dict, nights: int) -> dict | None:
    text = re.sub(r"\s+", " ", card["text"])
    price, rating = AIRBNB_PRICE.search(text), AIRBNB_RATING.search(text)
    if not price or not card["href"] or int(price[2]) != nights:
        return None
    if rating and int(rating[2].replace(",", "")) < MIN_REVIEWS:
        return None
    total = float(price[1].replace(",", ""))
    return {
        "name": f"{card['title']}: {card['name']}".strip(": "), "kind": "airbnb",
        "rating": float(rating[1]) if rating else None, "reviews": int(rating[2].replace(",", "")) if rating else 0,
        "price_per_night_usd": round(total / nights, 2), "price_total_usd": total,
        "booking_url": card["href"].split("&search_mode")[0],
    }


async def search_hotels(city: str, area: str, check_in: date, check_out: date, guests: int, max_nightly_usd: float) -> dict:
    """Hotels in `area` of `city` for the stay.

    Google Hotels ignores a guest count in the query and prices for its default of two
    adults, so the nightly "from" price is right for one or two travelers.
    """
    nights = (check_out - check_in).days
    place = f"{area} {city}".strip()

    async def fetch() -> dict:
        url = HOTELS_URL.format(query=quote(f"hotels in {place} from {check_in} to {check_out} for {guests} adults"))
        async with browser.session() as page:
            await browser.open_page(page, url, "c-wiz h2")
            shown = await page.evaluate(HOTEL_DATES)
            wanted = [f"{d:%a, %b} {d.day}" for d in (check_in, check_out)]
            if all(shown) and shown != wanted:
                raise RuntimeError(f"Google Hotels priced {shown[0]} to {shown[1]}, not the dates asked for")
            cards = await page.evaluate(HOTEL_CARDS)
            evidence_url = await browser.snapshot(page, f"hotels {place} {check_in}")
        options = [o for o in (parse_hotel(c, nights) for c in cards) if o]
        return {"url": url, "evidence_url": evidence_url, "fetched_at": datetime.now().isoformat(), "options": options}

    result = await cached(f"hotels:{place}:{check_in}:{check_out}:{guests}".lower(), fetch)
    return _finish(result, f"h-{_slug(place)}", city, area, check_in, check_out, max_nightly_usd)


async def search_airbnb(city: str, check_in: date, check_out: date, guests: int, max_nightly_usd: float) -> dict:
    """Airbnb stays in `city` for the dates."""
    nights = (check_out - check_in).days

    async def fetch() -> dict:
        url = AIRBNB_URL.format(place=quote(city), check_in=check_in, check_out=check_out, guests=guests)
        async with browser.session() as page:
            await browser.open_page(page, url, AIRBNB_CARD)
            cards = await page.eval_on_selector_all(AIRBNB_CARD, AIRBNB_CARDS)
            evidence_url = await browser.snapshot(page, f"airbnb {city} {check_in}")
        options = [o for o in (parse_airbnb(c, nights) for c in cards) if o]
        return {"url": url, "evidence_url": evidence_url, "fetched_at": datetime.now().isoformat(), "options": options}

    result = await cached(f"airbnb:{city}:{check_in}:{check_out}:{guests}".lower(), fetch)
    return _finish(result, f"a-{_slug(city)}", city, "", check_in, check_out, max_nightly_usd)


def _finish(result: dict, prefix: str, city: str, area: str, check_in: date, check_out: date, max_nightly: float) -> dict:
    """Apply the price cap, keep the best-rated few, and stamp ids, city and dates."""
    options = [o for o in result["options"] if not max_nightly or o["price_per_night_usd"] <= max_nightly]
    options = sorted(options, key=lambda o: -(o["rating"] or 0))[:MAX_OPTIONS]
    for i, option in enumerate(options, 1):
        # The check-in date keeps ids unique when a route visits the same city twice.
        option.update(id=f"{prefix}-{check_in:%m%d}-{i}", city=city, neighborhood=area,
                      check_in=check_in.isoformat(), check_out=check_out.isoformat())
    return {**result, "options": options}
