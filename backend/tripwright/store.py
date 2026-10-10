"""Trip state, traveler profile and the tool-result cache, in Postgres (or SQLite locally)."""

from __future__ import annotations

import json
import time

from sqlalchemy import Column, Float, MetaData, String, Table, Text, create_engine, delete, select

from . import config
from .models import TravelerProfile, TripState

_url = config.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://").replace("postgres://", "postgresql+psycopg://")
engine = create_engine(_url, pool_pre_ping=True)
meta = MetaData()
trips = Table("trips", meta, Column("id", String, primary_key=True), Column("state", Text), Column("updated_at", Float))
cache = Table("cache", meta, Column("key", String, primary_key=True), Column("value", Text), Column("created_at", Float))
profiles = Table("profiles", meta, Column("id", String, primary_key=True), Column("data", Text))
meta.create_all(engine)


def _upsert(table: Table, key_col: str, key: str, **values) -> None:
    with engine.begin() as db:
        db.execute(delete(table).where(table.c[key_col] == key))
        db.execute(table.insert().values({key_col: key, **values}))


def save_trip(state: TripState) -> None:
    _upsert(trips, "id", state.id, state=state.model_dump_json(), updated_at=time.time())


def load_trip(trip_id: str) -> TripState | None:
    with engine.connect() as db:
        row = db.execute(select(trips.c.state).where(trips.c.id == trip_id)).first()
    return TripState.model_validate_json(row[0]) if row else None


def cache_get(key: str, max_age_s: float):
    with engine.connect() as db:
        row = db.execute(select(cache.c.value, cache.c.created_at).where(cache.c.key == key)).first()
    if row and time.time() - row[1] <= max_age_s:
        return json.loads(row[0])
    return None


def cache_set(key: str, value) -> None:
    _upsert(cache, "key", key, value=json.dumps(value, default=str), created_at=time.time())


def load_profile(profile_id: str = "default") -> TravelerProfile | None:
    with engine.connect() as db:
        row = db.execute(select(profiles.c.data).where(profiles.c.id == profile_id)).first()
    return TravelerProfile.model_validate_json(row[0]) if row else None


def save_profile(profile: TravelerProfile, profile_id: str = "default") -> None:
    _upsert(profiles, "id", profile_id, data=profile.model_dump_json())
