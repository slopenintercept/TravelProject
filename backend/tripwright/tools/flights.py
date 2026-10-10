"""Scripted Google Flights search. Deterministic Playwright: no LLM calls.

Builds the search URL from structured inputs, loads it headlessly and parses the
result rows. Google puts a full sentence in each row's aria-label, which is far more
stable than its generated class names, so that sentence is what we parse.
"""

from __future__ import annotations

import asyncio
import re
from datetime import date, datetime
from urllib.parse import quote

from playwright.async_api import TimeoutError as PlaywrightTimeout

from ..recorded import cached
from . import browser

SEARCH_URL = "https://www.google.com/travel/flights?q={query}&hl=en&gl=us&curr=USD"
ROW = "[aria-label^='From '][aria-label*='Total duration']"
MAX_OPTIONS = 12

LABEL = re.compile(
    r"From (?P<price>[\d,]+) US dollars.*?"
    r"(?P<stops>Nonstop|\d+ stops?) flight with (?P<airline>.+?)\.\s*"
    r"Leaves (?P<origin>.+?) at (?P<dep_time>\d{1,2}:\d{2} [AP]M) on (?P<dep_date>\w+, \w+ \d{1,2}) and "
    r"arrives at (?P<destination>.+?) at (?P<arr_time>\d{1,2}:\d{2} [AP]M) on (?P<arr_date>\w+, \w+ \d{1,2})\.\s*"
    r"Total duration (?:(?P<hours>\d+) hr)?\s*(?:(?P<minutes>\d+) min)?"
)
LAYOVER = re.compile(r"is a ((?:\d+ hr)?\s*(?:\d+ min)?) (?:overnight )?layover at (.+?)(?: in [^.]+)?\.")


def _when(day_text: str, time_text: str, around: date) -> datetime:
    """'Tuesday, November 10' + '6:45 AM' -> datetime; the label has no year."""
    parsed = datetime.strptime(f"{day_text.split(', ')[1]} {around.year} {time_text}", "%B %d %Y %I:%M %p")
    if parsed.month < around.month - 6:  # December search landing in January
        parsed = parsed.replace(year=around.year + 1)
    return parsed


def parse_label(label: str, around: date) -> dict | None:
    """Turn one result row's aria-label sentence into a flight dict."""
    label = re.sub(r"\s+", " ", label.replace(" ", " ").replace("\xa0", " "))
    m = LABEL.search(label)
    if not m:
        return None
    return {
        "airline": m["airline"],
        "origin": m["origin"],
        "destination": m["destination"],
        "depart_at": _when(m["dep_date"], m["dep_time"], around).isoformat(),
        "arrive_at": _when(m["arr_date"], m["arr_time"], around).isoformat(),
        "duration_minutes": int(m["hours"] or 0) * 60 + int(m["minutes"] or 0),
        "stops": 0 if m["stops"] == "Nonstop" else int(m["stops"].split()[0]),
        "layovers": [f"{place} ({wait.strip()})" for wait, place in LAYOVER.findall(label)],
        "price_usd": float(m["price"].replace(",", "")),
    }


async def _search(query: str, around: date, label: str) -> dict:
    url = SEARCH_URL.format(query=quote(query))
    for attempt in (1, 2):  # Google's results sometimes fail to render headless; one retry is enough
        try:
            async with browser.session() as page:
                await browser.open_page(page, url, ROW)
                labels = await page.eval_on_selector_all(ROW, "els => els.map(e => e.getAttribute('aria-label'))")
                evidence_url = await browser.snapshot(page, label)
            break
        except PlaywrightTimeout:
            if attempt == 2:
                raise
    options, seen = [], set()
    for text in labels:
        option = parse_label(text, around)
        key = option and (option["airline"], option["depart_at"], option["price_usd"])
        if option and key not in seen:
            seen.add(key)
            options.append(option)
    return {"url": url, "evidence_url": evidence_url, "fetched_at": datetime.now().isoformat(), "options": options}


async def search_flights(origin: str, destination: str, depart: date, return_: date) -> dict:
    """Round-trip options with total price, each paired with a return leg on the same airline.

    The first search gives outbound legs with round-trip totals. Return-leg times come
    from a second search in the reverse direction, matched by airline; they show the
    typical return on that carrier and are confirmed on the provider's checkout page.
    """

    async def fetch() -> dict:
        out, back = await asyncio.gather(
            _search(f"Flights to {destination} from {origin} on {depart} through {return_}", depart,
                    f"flights {origin} {destination} {depart}"),
            _search(f"Flights to {origin} from {destination} on {return_} one way", return_,
                    f"flights return {destination} {origin} {return_}"),
        )
        for i, option in enumerate(out["options"][:MAX_OPTIONS], 1):
            option["id"] = f"f{i}"
            carrier = option["airline"].split(" and ")[0]
            match = min(
                (r for r in back["options"] if carrier in r["airline"]),
                key=lambda r: r["duration_minutes"], default=None,
            )
            option["return_depart_at"] = match and match["depart_at"]
            option["return_arrive_at"] = match and match["arrive_at"]
        out["options"] = out["options"][:MAX_OPTIONS]
        out["return_evidence_url"] = back["evidence_url"]
        return out

    return await cached(f"flights:{origin}:{destination}:{depart}:{return_}".lower(), fetch)
