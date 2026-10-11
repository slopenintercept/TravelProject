"""Travel-time estimates between stops.

There is no free transit-routing API for Japan, so this is a deterministic estimate:
great-circle distance with a detour factor at door-to-door urban transit speed.
Intercity hops use the Transport agent's researched durations instead (see scheduler).
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

DEFAULT_HOP_MIN = 30  # used when either stop has no coordinates
DAY_TRIP_KM = 40  # farther than this is a day trip (Hakone from Tokyo): its duration includes getting there
DETOUR_FACTOR = 1.4
TRANSIT_KMH = 22
FIXED_OVERHEAD_MIN = 10


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def travel_minutes(a, b) -> int:
    """Minutes to get from stop `a` to stop `b` (anything with .lat/.lon)."""
    if None in (a.lat, a.lon, b.lat, b.lon):
        return DEFAULT_HOP_MIN
    if haversine_km(a.lat, a.lon, b.lat, b.lon) > DAY_TRIP_KM:
        return DEFAULT_HOP_MIN  # a day trip: the train out and back is part of its own duration
    km = haversine_km(a.lat, a.lon, b.lat, b.lon) * DETOUR_FACTOR
    return max(FIXED_OVERHEAD_MIN, round(km / TRANSIT_KMH * 60) + FIXED_OVERHEAD_MIN)


def same_city(a: str, b: str) -> bool:
    return a.strip().lower() == b.strip().lower()
