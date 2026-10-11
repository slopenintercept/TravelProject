"""The Strands @tools the specialist agents call.

Each specialist run gets its own Toolbox bound to a RunContext. Tools hand the model
a short text table; the full structured results stay in the context, keyed by id.
The agent then answers with ids and reasoning, and Python joins those ids back to the
real prices, times, source URLs and evidence snapshots. The model never retypes a price
or a URL: the endpoint writes about 100 characters a second, so short answers are fast ones.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from strands import tool

from .models import FlightOption, LodgingOption, Source, Traveler, TripState
from .tools import browser, flights, lodging, places, research


@dataclass
class RunContext:
    agent: str
    state: TripState
    traveler: Traveler | None = None  # set when the agent is planning one person's flight or lodging
    flights: dict[str, FlightOption] = field(default_factory=dict)
    rooms: dict[str, LodgingOption] = field(default_factory=dict)
    windows: dict[str, dict] = field(default_factory=dict)  # start date -> outlook
    sources: dict[str, Source] = field(default_factory=dict)  # every URL a tool actually read

    def add_source(self, url: str, title: str, evidence_url: str, fetched_at: str | None) -> Source:
        self.sources[_url_key(url)] = Source(url=url, title=title, evidence_url=evidence_url, fetched_at=fetched_at)
        return self.sources[_url_key(url)]

    def cite(self, url: str) -> str:
        """The short id (s1, s2, ...) the tools show for a source, so agents cite it without retyping its URL."""
        return f"s{list(self.sources).index(_url_key(url)) + 1}"

    def source(self, ref: str) -> Source | None:
        """A source by the short id an agent cited, or by its URL."""
        if cited := re.fullmatch(r"s(\d+)", ref.strip(" []").lower()):
            return next((s for i, s in enumerate(self.sources.values(), 1) if i == int(cited[1])), None)
        return self.sources.get(_url_key(ref))


def _url_key(url: str) -> str:
    """The same page cited as http/https, with or without www or a trailing slash, is one source."""
    return re.sub(r"^https?://(www\.)?", "", url.strip().lower()).rstrip("/")


def _clock(iso: str | None) -> str:
    return f"{iso[5:10]} {iso[11:16]}" if iso else "?"


class Toolbox:
    def __init__(self, ctx: RunContext) -> None:
        self.ctx = ctx

    async def _flights(self, origin: str, destination: str, depart: date, return_: date) -> list[FlightOption]:
        result = await flights.search_flights(origin, destination, depart, return_)
        source = self.ctx.add_source(result["url"], "Google Flights", result["evidence_url"], result["fetched_at"])
        found = []
        for raw in result["options"]:
            option = FlightOption(**{**raw, "id": f"f{len(self.ctx.flights) + 1}"}, booking_url=result["url"], source=source)
            self.ctx.flights[option.id] = option
            found.append(option)
        return found

    @tool
    async def search_flights(self, origin: str, destination: str, depart_date: str, return_date: str) -> str:
        """Search Google Flights for round-trip flights. Prices are round-trip totals per traveler.

        Args:
            origin: Origin airport IATA code, e.g. MCI.
            destination: Destination city or airport, e.g. Tokyo.
            depart_date: Day you leave the origin, YYYY-MM-DD.
            return_date: Day you leave the destination, YYYY-MM-DD.
        """
        depart, back = date.fromisoformat(depart_date), date.fromisoformat(return_date)
        try:
            found = await self._flights(origin, destination, depart, back)
        except Exception as e:
            # Google Flights doesn't answer some airport codes (SEA) that it answers by city name (Seattle).
            home = self.ctx.traveler.origin if self.ctx.traveler else self.ctx.state.request.origin
            if home.strip().lower() == origin.strip().lower():
                return f"Flight search failed: {e}"
            try:
                found = await self._flights(home, destination, depart, back)
            except Exception:
                return f"Flight search failed: {e}"
        lines = [
            f"{o.id} | {o.airline} | ${o.price_usd:.0f} | leaves {_clock(o.depart_at.isoformat())}, "
            f"lands {o.destination} {_clock(o.arrive_at.isoformat())} | {o.duration_minutes // 60}h{o.duration_minutes % 60:02d} | "
            f"{o.stops} stop(s) {', '.join(o.layovers)} | flight home leaves {_clock(o.return_depart_at and o.return_depart_at.isoformat())}"
            for o in found
        ]
        return "\n".join(lines) or "No flights found for those dates."

    @tool
    async def window_outlook(self, start_date: str) -> str:
        """Check one candidate trip window: typical weather and the cheapest round-trip fare.

        Args:
            start_date: Day you would leave home, YYYY-MM-DD.
        """
        state = self.ctx.state
        try:
            start = date.fromisoformat(start_date)
            end = date.fromordinal(start.toordinal() + state.request.days)
            city = state.route.segments[0].city if state.route else state.request.destination
            weather = await places.climate(city, start, end)
            self.ctx.add_source(weather["url"], "Open-Meteo historical weather", weather["evidence_url"], None)
            outlook = {"end": end.isoformat(), "weather": weather, "fare": None}
            try:
                fares = await self._flights(state.request.origin, city, start, end)
                outlook["fare"] = min((o.price_usd for o in fares), default=None)
            except Exception as e:
                outlook["fare_error"] = str(e)
        except Exception as e:
            return f"Could not check {start_date}: {e}"
        self.ctx.windows[start_date] = outlook
        fare = f"${outlook['fare']:.0f}" if outlook["fare"] else "unknown"
        return (f"{start_date} to {end}: {city} averages {weather['avg_high_c']}C/{weather['avg_low_c']}C with "
                f"{weather['rainy_days']} rainy days; cheapest round-trip fare {fare}.")

    async def _rooms(self, result: dict, title: str, lat_lon) -> str:
        source = self.ctx.add_source(result["url"], title, result["evidence_url"], result["fetched_at"])
        lines = []
        for raw in result["options"]:
            raw = {k: v for k, v in raw.items() if k not in ("reviews", "price_per_night_usd")} | {
                "location_note": f"{raw['reviews']:,} reviews, ${raw['price_per_night_usd']:.0f}/night"}
            room = LodgingOption(**raw, lat=lat_lon and lat_lon[0], lon=lat_lon and lat_lon[1], source=source)
            self.ctx.rooms[room.id] = room
            lines.append(f"{room.id} | {room.name} | {room.kind} | ${room.price_total_usd:.0f} total "
                         f"({room.location_note}) | rated {room.rating}")
        return "\n".join(lines) or "Nothing found under that price."

    @tool
    async def search_hotels(self, city: str, area: str, check_in: str, check_out: str, max_nightly_usd: float) -> str:
        """Search Google Hotels for hotels in one neighborhood. Call once per stay.

        Args:
            city: City name, e.g. Tokyo.
            area: Neighborhood to stay in, e.g. Asakusa.
            check_in: YYYY-MM-DD.
            check_out: YYYY-MM-DD.
            max_nightly_usd: Highest nightly price to include.
        """
        try:
            result = await lodging.search_hotels(city, area, date.fromisoformat(check_in), date.fromisoformat(check_out),
                                                 1, max_nightly_usd)
            return await self._rooms(result, "Google Hotels", await places.geocode(f"{area}, {city}"))
        except Exception as e:
            return f"Hotel search failed: {e}"

    @tool
    async def search_airbnb(self, city: str, check_in: str, check_out: str, max_nightly_usd: float) -> str:
        """Search Airbnb for stays in a city. Call once per stay.

        Args:
            city: City name, e.g. Kyoto.
            check_in: YYYY-MM-DD.
            check_out: YYYY-MM-DD.
            max_nightly_usd: Highest nightly price to include.
        """
        try:
            result = await lodging.search_airbnb(city, date.fromisoformat(check_in), date.fromisoformat(check_out),
                                                 1, max_nightly_usd)
            return await self._rooms(result, "Airbnb", None)
        except Exception as e:
            return f"Airbnb search failed: {e}"

    @tool
    async def web_research(self, query: str) -> str:
        """Search the web for travel research. Prefer official tourism sites, travel guides and traveler forums.

        Each result starts with its source id, like [s3]. Cite a source by that id, never by its URL.

        Args:
            query: What to look up, e.g. "hotel or Airbnb in Tokyo for first-time visitors".
        """
        try:
            results = await research.search(query)
        except Exception as e:
            return f"Search failed: {e}"
        for r in results:
            self.ctx.add_source(r["url"], r["title"], r["evidence_url"], r["fetched_at"])
        return "\n\n".join(f"[{self.ctx.cite(r['url'])}] {r['title']}\nURL: {r['url']}\n{r['excerpt']}"
                             for r in results) or "No results."

    @tool
    async def read_source(self, url: str) -> str:
        """Read the text of one web page found by web_research. The result starts with the page's source id.

        Args:
            url: The page URL.
        """
        try:
            page = await research.read(url)
        except Exception as e:
            return f"Could not read {url}: {e}"
        self.ctx.add_source(page["url"], page["url"], page["evidence_url"], page["fetched_at"])
        return f"[{self.ctx.cite(page['url'])}]\n{page['text']}"

    @tool
    async def browse_page(self, url: str) -> str:
        """Open a page in a headless browser and read it. A screenshot is saved as evidence.

        Use for official ticket pages, opening hours and closure notices. The result starts with the
        page's source id.

        Args:
            url: The page URL.
        """
        try:
            page = await browser.read_page(url)
        except browser.Blocked as e:
            return f"Blocked: {e}. Do not retry this site; use another source."
        except Exception as e:
            return f"Could not open {url}: {e}"
        self.ctx.add_source(page["url"], page["title"], page["evidence_url"], page["fetched_at"])
        return f"[{self.ctx.cite(page['url'])}] {page['title']}\n{page['text']}"
