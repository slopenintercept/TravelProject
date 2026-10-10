"""Geocoding (OpenStreetMap Nominatim) and weather (Open-Meteo). Both free, no key, no LLM."""

from __future__ import annotations

import json
from datetime import date, timedelta

import httpx

from .. import evidence
from ..recorded import NotRecorded, cached

NOMINATIM = "https://nominatim.openstreetmap.org/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_HORIZON_DAYS = 15
CLIMATE_YEARS = 3
RAINY_MM = 1.0
HEADERS = {"User-Agent": "Tripwright/0.1 (Hack Midwest demo)"}
MONTH = 30 * 24 * 3600


async def _get(url: str, params: dict) -> dict | list:
    async with httpx.AsyncClient(timeout=30, headers=HEADERS) as http:
        response = await http.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def geocode(place: str) -> tuple[float, float] | None:
    async def fetch():
        hits = await _get(NOMINATIM, {"q": place, "format": "json", "limit": 1})
        return [float(hits[0]["lat"]), float(hits[0]["lon"])] if hits else []

    try:
        hit = await cached(f"geocode:{place}".lower(), fetch, ttl_s=12 * MONTH, fuzzy=False)
    except NotRecorded:  # DEMO_MODE: an unknown place has no coordinates rather than wrong ones
        return None
    return (hit[0], hit[1]) if hit else None


async def _climate(city: str, start: date, end: date) -> dict:
    """Daily highs, lows and rain for the same calendar dates in each of the last few years."""
    lat, lon = await geocode(city)
    years = []
    for back in range(1, CLIMATE_YEARS + 1):
        s, e = start.replace(year=start.year - back), end.replace(year=end.year - back)
        while e >= date.today():  # the archive only has the past
            s, e = s.replace(year=s.year - 1), e.replace(year=e.year - 1)
        data = await _get(ARCHIVE, {
            "latitude": lat, "longitude": lon, "start_date": s, "end_date": e, "timezone": "auto",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        })
        years.append(data["daily"])
    evidence_url = await evidence.save(f"climate {city} {start}", json.dumps(years, indent=1).encode(), "txt")
    return {"years": years, "evidence_url": evidence_url,
            "url": f"https://open-meteo.com/en/docs/historical-weather-api?latitude={lat}&longitude={lon}"}


async def climate(city: str, start: date, end: date) -> dict:
    """Typical weather for a date window: average high/low and rainy days, from history."""
    raw = await cached(f"climate:{city}:{start}:{end}".lower(), lambda: _climate(city, start, end), ttl_s=MONTH)
    highs = [t for y in raw["years"] for t in y["temperature_2m_max"] if t is not None]
    lows = [t for y in raw["years"] for t in y["temperature_2m_min"] if t is not None]
    rainy = [sum((mm or 0) >= RAINY_MM for mm in y["precipitation_sum"]) for y in raw["years"]]
    days = min((end - start).days + 1, len(raw["years"][0]["time"]))
    by_day = [
        {
            "high_c": round(sum(y["temperature_2m_max"][i] or 0 for y in raw["years"]) / len(raw["years"]), 1),
            "low_c": round(sum(y["temperature_2m_min"][i] or 0 for y in raw["years"]) / len(raw["years"]), 1),
            "precip_prob": round(100 * sum((y["precipitation_sum"][i] or 0) >= RAINY_MM for y in raw["years"]) / len(raw["years"])),
        }
        for i in range(days)
    ]
    return {
        "avg_high_c": round(sum(highs) / len(highs), 1), "avg_low_c": round(sum(lows) / len(lows), 1),
        "rainy_days": round(sum(rainy) / len(rainy)), "by_day": by_day,
        "url": raw["url"], "evidence_url": raw["evidence_url"],
    }


async def daily_weather(city: str, start: date, end: date) -> list[dict]:
    """Per-day outlook: the live forecast when the dates are close enough, else climate history."""
    if (end - date.today()).days <= FORECAST_HORIZON_DAYS and start >= date.today():
        async def fetch():
            lat, lon = await geocode(city)
            data = await _get(FORECAST, {
                "latitude": lat, "longitude": lon, "start_date": start, "end_date": end, "timezone": "auto",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            })
            url = await evidence.save(f"forecast {city} {start}", json.dumps(data, indent=1).encode(), "txt")
            return {"daily": data["daily"], "evidence_url": url,
                    "url": f"https://open-meteo.com/en/docs?latitude={lat}&longitude={lon}"}

        raw = await cached(f"forecast:{city}:{start}:{end}".lower(), fetch, ttl_s=3 * 3600)
        d = raw["daily"]
        rows = [{"high_c": d["temperature_2m_max"][i], "low_c": d["temperature_2m_min"][i],
                 "precip_prob": d["precipitation_probability_max"][i]} for i in range(len(d["time"]))]
        kind, source = "forecast", raw
    else:
        source = await climate(city, start, end)
        rows, kind = source["by_day"], "climate"
    return [
        {**row, "day": (start + timedelta(days=i)).isoformat(), "city": city, "kind": kind,
         "url": source["url"], "evidence_url": source["evidence_url"]}
        for i, row in enumerate(rows)
    ]
