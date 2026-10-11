# Choose Flights and Stays Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each traveler confirms their flight and rooms before activities are scheduled; scheduling happens on the first confirm and re-runs on each later one.

**Architecture:** `plan_trip` runs the research agents without the scheduler and leaves the trip in a new `choosing` stage. A per-traveler confirm endpoint stores the choices and, once research is done, runs the existing scheduling-only re-plan and moves the trip to `review`.

**Tech Stack:** FastAPI, Pydantic 2, Strands Graph, pytest; React 19 + TypeScript.

**Spec:** `docs/superpowers/specs/2026-10-10-choose-flights-and-stays-design.md`

## Global Constraints

- Do not commit (user's instruction).
- Error messages are verbatim from the spec.
- Existing tests keep passing, except `test_planning_always_replans_the_route_from_everyones_picks`, whose expected stages change to `["route", "research"]` and final stage `choosing`.

## Review Focus

1. A traveler confirms while research is still running → the choice is kept and scheduling happens when research ends. Test in Task 1.
2. A traveler with no flight options (agent pending) confirms → allowed with `flight_id = None`. Test in Task 1.
3. Confirming twice (changing your mind on the Choose screen before others) → second confirm overwrites and re-schedules. Test in Task 2.
4. The research lock makes the whole trip "busy" for minutes → the Choose screen must not disable on `view.busy`. Checked in Task 3's browser run.
5. A trip already in `review` from before this change (nobody `confirmed`) → everyone sees their Choose screen once; confirming re-schedules. Covered by the API test of a confirm in `review`.

---

### Task 1: Orchestrator — research-only run and confirm_choices

**Files:** `backend/tripwright/models.py`, `backend/tripwright/orchestrator.py`; tests in `backend/tests/test_group.py`.

**Interfaces — Produces:** `Traveler.confirmed`; stage `"choosing"`; `planning_graph(specialists, schedule=True)`; `confirm_choices(state, traveler_id, flight_id, stay_ids) -> None`; `options_ready(state, traveler_id) -> bool`; `schedule_choices(state) -> None` (runs `planning_graph([])` as stage `"schedule"` and sets stage `review`).

- [ ] Tests: plan with nobody confirmed → stages `["route", "research"]`, stage `choosing`; plan where a traveler is confirmed before research ends → stages `["route", "research", "schedule"]`, stage `review`; `confirm_choices` errors (three messages) and success (selected ids set, `confirmed`); `flight_id=None` allowed when the traveler has no flights.
- [ ] Run → fail. Implement. Run full suite → pass.

### Task 2: API — confirm endpoint

**Files:** `backend/tripwright/api.py`; tests in `backend/tests/test_api.py`.

**Interfaces — Consumes:** Task 1. **Produces:** `PUT /api/trips/{id}/travelers/{traveler_id}/choices`, body `ChoicesIn(flight_id: str | None = None, stay_ids: list[str] = [])`.

- [ ] Tests: 403 for someone else; 400 in `gathering`; 400 while `flight:p2` is working; confirm in `choosing` with the lock free → stage `review`, itinerary built; a second traveler's confirm in `review` → still `review`, re-scheduled with their flight; confirm while the lock is held → saved, stage stays `choosing`.
- [ ] Run → fail. Implement. Run full suite → pass.

### Task 3: Frontend — Choose screen and routing

**Files:** create `frontend/src/components/Choose.tsx`; modify `types.ts`, `api.ts`, `useTrip.ts` (expose `sending`), `App.tsx`, `styles.css`.

- [ ] `Choose({ state, you, sending, onConfirm })`: flight radio list, one radio list per stay, running total vs `you.budget_usd`, confirm button disabled only while `sending`.
- [ ] Routing per the spec's flow; `review` with `!you.confirmed` shows Choose with the "already planned" note.
- [ ] Type-check, build, browser run with two travelers.
