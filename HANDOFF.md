# Tripwright handoff

Written 2026-10-10 for continuing in a new chat. Read `README.md` and `DEMO.md` for the product and architecture; this file covers state, decisions and what is left.

## What it is

Tripwright is an agentic group trip planner for Hack Midwest.

- **Agents:** Strands Agents SDK (Python) 1.59.0, talking to the Akamai workshop inference endpoint (OpenAI-compatible, model `hackathon-chat`).
- **Backend:** FastAPI in `backend/tripwright/`. SQLite locally (`data/tripwright.db`), Postgres when `DATABASE_URL` is set.
- **Frontend:** Vite + React + TypeScript in `frontend/`, served by the backend from `frontend/dist`.
- **Live data:** scripted Playwright tools for Google Flights, Google Hotels and Airbnb; Tavily for research; Open-Meteo for weather.

## User flow

1. The host fills in the trip (destination, days, origin, budget, need/want attractions).
2. Agents propose a route and date windows; the host picks dates.
3. The host shares an invite link (`#<tripId>/join`); each traveler adds their origin, budget and need/want attractions. No login.
4. "Everyone's in" starts planning: one flight agent per traveler, one lodging agent, one attractions agent for the group, transport, weather.
5. Deterministic steps follow: scheduler, per-traveler budget, `validate_itinerary`.
6. Review screen: approve, swap or switch each card. "Finish" (bottom right) lists every booking with links that already carry dates, route and guests.

## Decisions the user has made

- Flights and lodging are **individual per traveler**; attractions are planned **as a group** after everyone has stated preferences.
- **Nobody else's budget may influence a traveler's hotel.** Travelers can stay in different places.
- Aim for the fewest itineraries that meet the most preferences: one shared itinerary if possible, with short split-offs that regroup.
- No source or "evidence" links in the UI.
- Agents never enter payment details or passwords, never create accounts, and never bypass bot detection or CAPTCHAs. "Booking" means handing the user a link.

## How to run

```bash
cd backend && .venv/bin/python -m uvicorn tripwright.api:app --port 8000
```

```bash
cd backend && .venv/bin/python -m pytest -q
```

```bash
cd frontend && npm run build
```

- Keys live in `.env` at the project root (gitignored). Never print or commit them.
- `DEMO_MODE=true` replays `backend/tripwright/fixtures/recorded.json` with no network or keys.
- `RECORD_FIXTURES=true` records live calls into the fixtures.
- The Claude preview config is `tripwright` in `.claude/launch.json`.

## Where things are

| File | What it holds |
|---|---|
| `backend/tripwright/orchestrator.py` | Strands graphs, `SpecialistNode` (attempt, deterministic check, LLM judge, retry, fallback), user-flow functions |
| `backend/tripwright/specialists.py` | Each agent's task prompt, output schema and `build_*` check; `assign_rooms` |
| `backend/tripwright/toolbox.py` | `@tool` functions and the per-run `RunContext` |
| `backend/tripwright/tools/` | Playwright flight and lodging scrapers, places, research |
| `backend/tripwright/scheduler.py` | Group day frames, shared pass, split-off pass |
| `backend/tripwright/budget.py` | Per-traveler budget shares, costs, swap optimizer |
| `backend/tripwright/validate.py` | `validate_itinerary` and `replan` |
| `backend/tripwright/cards.py`, `booking.py` | Review cards and Finish-screen links |
| `backend/tripwright/recorded.py` | Cache, demo replay, fixture recording |
| `frontend/src/components/` | `TripForm`, `Timeframe`, `Gathering`, `Join`, `Review`, `Itinerary`, `Finish`, `AgentPanel`, `BudgetBar` |

Pattern used throughout: the LLM picks ids, Python holds the facts. Tools keep full results in `RunContext`; agents answer with option ids; `build_*` joins them back and raises `Rejected(problems)` to send the agent back.

## Git

- Remote: `https://github.com/slopenintercept/TravelProject.git` (public).
- `main` is at the user's initial commit `90bf33c`.
- Branch `group-trips-live-run` is pushed at `bd4e867`. It is not merged into `main`; the user has not asked for that yet.
- GitHub push protection once blocked a push because a third-party Mapbox token sat inside scraped page text. It was redacted, not bypassed, and `tools/research.py` now strips such tokens.

## Uncommitted work (latest change)

Two files are modified and not committed: `backend/tripwright/specialists.py` and `backend/tests/test_group.py`.

The user asked why Alex's budget showed up on Sam's hotel card. Cause: one lodging agent wrote one sentence per stay about the group's tightest budget, and that sentence and pick were copied to every traveler who could afford it. The fix:

- `assign_rooms` now gives each traveler the best-rated option within **their own** nightly budget (cheapest found if nothing fits). No other traveler's budget is involved.
- Each card's reasoning opens with that traveler's own budget; the agent's description is appended only when the room is the agent's pick.
- The lodging prompt tells the agent to search up to the highest budget, offer alternatives at different prices, and leave budgets and names out of its reasoning.
- The test checks that changing one traveler's budget moves only that traveler's room.

Verified: 43 tests pass, and a live lodging re-run on a copy of `trip_9de4fc7d` was accepted with no cross-budget text and no violations. Not verified: the review screen in the browser after this change. Trips planned before the change keep their old sentences until lodging is re-run.

## Not done or not verified

- Akamai deploy (`deploy/provision.sh`, `deploy/deploy.sh`, `Dockerfile`, `compose.yaml`) has never been run. It is billable and needs the user's explicit go-ahead.
- Split-offs have only happened in tests, never in a live run.
- "Best" hotel is by rating only, with price as the tie-break.
- The build function still rejects a lodging result if no option fits the lowest budget. That keeps a room available for that traveler; it does not affect anyone else's room.
- The group's day is bounded by the last arrival and the first departure.
- A cold group run takes about 4 to 5 minutes; the endpoint allows 60 requests a minute.
- The hotel date parameter in Google Hotels links is undocumented.
- Travel times are estimates; food is not budgeted; no monitor agent.
- The public repo's fixtures contain screenshots and text excerpts of third-party pages.

## Gotchas

- The endpoint rejects an empty `tools` array; context is 32k tokens, output at most 4,096.
- Booking.com blocks headless browsers, so hotels come from Google Hotels.
- `tavily_search` in strands-agents-tools prints a deprecation warning; it still works.
- `load_dotenv` does not override shell variables, so flags set in the shell win over `.env`.
- The user's global `CLAUDE.md` rules apply: state assumptions, keep code minimal, make surgical changes, verify against a concrete check.
