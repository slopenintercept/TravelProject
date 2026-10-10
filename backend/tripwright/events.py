"""Per-trip event bus behind the live agent activity panel (served as SSE)."""

from __future__ import annotations

import asyncio
import time

from .models import AgentStatus, TripState


class Bus:
    def __init__(self) -> None:
        self.history: list[dict] = []
        self.listeners: set[asyncio.Queue] = set()

    def emit(self, type: str, **data) -> None:
        event = {"type": type, "ts": time.time(), **data}
        self.history.append(event)
        for queue in self.listeners:
            queue.put_nowait(event)

    def status(self, state: TripState, agent: str, status: str, message: str = "", attempt: int = 0, found: str = "") -> None:
        """Record an agent's status on the trip and tell the UI."""
        previous = state.agents.get(agent)
        state.agents[agent] = AgentStatus(
            agent=agent, status=status, attempt=attempt or (previous.attempt if previous else 0),
            message=message, found=found or (previous.found if previous else ""),
        )
        self.emit("agent", **state.agents[agent].model_dump())

    async def stream(self):
        """Replay what already happened, then follow live."""
        queue: asyncio.Queue = asyncio.Queue()
        for event in self.history:
            queue.put_nowait(event)
        self.listeners.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self.listeners.discard(queue)


_buses: dict[str, Bus] = {}


def bus(trip_id: str) -> Bus:
    return _buses.setdefault(trip_id, Bus())
