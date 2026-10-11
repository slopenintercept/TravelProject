"""One wrapper gives every tool caching, DEMO_MODE replay and fixture recording.

Live: results are cached in the database by key so repeated queries don't re-browse.
RECORD_FIXTURES=true: live results are also written to fixtures/recorded.json.
DEMO_MODE=true: tools never touch the network; they replay the recorded result for
the same key, or the closest recorded call to the same tool.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from pathlib import Path

from . import config, store

FIXTURES = Path(__file__).parent / "fixtures" / "recorded.json"
DEFAULT_TTL_S = 6 * 3600


class NotRecorded(Exception):
    pass


def _load() -> dict:
    return json.loads(FIXTURES.read_text(encoding="utf-8")) if FIXTURES.exists() else {}


def _words(key: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", key.lower()))


def saved(key: str):
    """The recorded result for exactly `key`, or None."""
    return _load().get(key)


def replay(key: str, fuzzy: bool):
    """The recorded result for `key`, else (if fuzzy) the most similar recorded call to the same tool."""
    recorded = _load()
    if key in recorded:
        return recorded[key]
    if not fuzzy:
        raise NotRecorded(f"No recorded result for {key}.")
    tool = key.split(":", 1)[0]
    candidates = [k for k in recorded if k.split(":", 1)[0] == tool]
    if not candidates:
        raise NotRecorded(f"No recorded result for {tool}. Record one with RECORD_FIXTURES=true.")
    return recorded[max(candidates, key=lambda k: len(_words(k) & _words(key)))]


def record(key: str, value) -> None:
    recorded = _load()
    recorded[key] = value
    FIXTURES.parent.mkdir(exist_ok=True)
    FIXTURES.write_text(json.dumps(recorded, indent=1, default=str, ensure_ascii=False), encoding="utf-8")


async def cached(key: str, fetch: Callable[[], Awaitable], ttl_s: float = DEFAULT_TTL_S, fuzzy: bool = True):
    if config.DEMO_MODE:
        return replay(key, fuzzy)
    hit = store.cache_get(key, ttl_s)
    if hit is not None:
        if config.RECORD_FIXTURES:
            record(key, hit)
        return hit
    value = await fetch()
    store.cache_set(key, value)
    if config.RECORD_FIXTURES:
        record(key, value)
    return value
