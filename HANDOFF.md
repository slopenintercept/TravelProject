# Tripwright handoff

Updated 2026-10-10 (late evening) for continuing in a new chat. Read `README.md` and `DEMO.md` for the product and architecture; this file covers state, decisions and what is left.

## What it is

Tripwright is an agentic group trip planner for Hack Midwest.

- **Agents:** Strands Agents SDK (Python) 1.59.0, talking to the Akamai workshop inference endpoint (OpenAI-compatible, model `hackathon-chat`).
- **Backend:** FastAPI in `backend/tripwright/`. SQLite locally (`data/tripwright.db`), Postgres when `DATABASE_URL` is set.
- **Frontend:** Vite + React + TypeScript in `frontend/`, served by the backend from `frontend/dist`.
- **Live data:** scripted Playwright tools for Google Flights, Google Hotels and Airbnb; Tavily for research; Open-Meteo for weather.

Two people commit to the repo: Amandeep Toor (the user) and Brandon Laing (teammate, works on Windows).

## User flow

1. The host fills in the trip (origin, destination, days, budget). There are no need/want text fields any more.
2. Agents propose a route and date windows, and an ideas agent lists 15 to 25 places. The host picks dates.
3. The host shares the invite link. Each traveler joins on their own link (`#<tripId>/<travelerId>`) with their origin and budget, then marks the places must do, interested or not for me. They can add a place or ask for more like their picks. No login; the `X-Traveler` header says who is acting.
4. While people join, a draft plan sketches the days from everyone's picks (`draft.py`).
5. The host starts planning: one flight agent per traveler, plus lodging, attractions, transport and weather.
6. Each traveler confirms their own flight and rooms (stage `choosing`). The days are scheduled on the first confirm and re-planned on each later one: scheduler, per-traveler budget, `validate_itinerary`.
7. Review screen: each traveler approves, swaps or removes their own cards. The Itinerary tab is a calendar with drag, swap and Remove. "Finish" lists every booking with links that already carry dates, route and guests.

## Decisions the user has made

- Flights, lodging and **transport** are individual per traveler; attractions are planned as a group after everyone has stated preferences.
- **Nobody else's budget may influence a traveler's hotel.** Travelers can stay in different places.
- **Transport is each traveler's own choice and cost**, shown and chosen like flights and lodging. Nothing is split across the group; a rental car is paid in full by whoever adds it.
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

```bash
cd backend && .venv/bin/python -m tripwright.scenario
```

- The last command creates a ready-made seven-traveler Japan trip and prints its links, for trying the flow as an eighth traveler. No agents run until the host starts planning.
- Keys live in `.env` at the project root (gitignored). Never print or commit them.
- `DEMO_MODE=true` replays `backend/tripwright/fixtures/recorded.json` with no network or keys.
- `RECORD_FIXTURES=true` records live calls into the fixtures.
- Claude preview configs in `.claude/launch.json`: `tripwright` (port 8000), `tripwright-8001` (same app on port 8001, for when another chat holds 8000) and `tripwright-windows` (Brandon's paths).

## Where things are

| File | What it holds |
|---|---|
| `backend/tripwright/api.py` | Routes, the `X-Traveler` check on who may change what, server-sent events |
| `backend/tripwright/orchestrator.py` | Strands graphs, `SpecialistNode` (attempt, deterministic check, LLM judge, retry, fallback), user-flow functions, `decide` |
| `backend/tripwright/specialists.py` | Each agent's task prompt, output schema and `build_*` check; `assign_rooms`, `assign_legs` |
| `backend/tripwright/toolbox.py` | `@tool` functions and the per-run `RunContext`; tools show sources as short ids (`[s3]`) |
| `backend/tripwright/tools/` | Playwright flight and lodging scrapers, places, research |
| `backend/tripwright/draft.py` | The draft plan shown while travelers join |
| `backend/tripwright/scenario.py` | The ready-made seven-traveler trip |
| `backend/tripwright/scheduler.py` | Group day frames, shared pass, split-off pass |
| `backend/tripwright/budget.py` | Per-traveler budget shares, costs, swap optimizer |
| `backend/tripwright/validate.py` | `validate_itinerary` and `replan` |
| `backend/tripwright/cards.py`, `booking.py` | Review cards and Finish-screen links |
| `backend/tripwright/recorded.py` | Cache, demo replay, fixture recording |
| `frontend/src/components/` | `TripForm`, `Timeframe`, `Gathering`, `Join`, `Picks`, `DraftPlan`, `Choose`, `Review`, `Itinerary`, `CalendarGrid`, `Finish`, `AgentPanel`, `BudgetBar` |
| `docs/superpowers/` | Brandon's design specs and plans for picks and for choosing flights and stays first |

Pattern used throughout: the LLM picks ids, Python holds the facts. Tools keep full results in `RunContext`; agents answer with option ids and source ids; `build_*` joins them back and raises `Rejected(problems)` to send the agent back.

## Git

- Remote: `https://github.com/slopenintercept/TravelProject.git` (public).
- Current branch: `combine-picks-and-group-trips`, pushed. It holds everything: Brandon's picks, per-person links and draft plan, merged with the user's `group-trips-live-run`.
- `group-trips-live-run` is pushed at `b370be3` and is fully contained in the current branch.
- `main` is at `e26e27e` (Brandon's picks design spec). Nothing has been merged into it; the user has not asked for that.
- `agents-faster` is a local-only branch at `0326c82`, the same change as `b370be3`.
- GitHub push protection once blocked a push because a third-party Mapbox token sat inside scraped page text. It was redacted, not bypassed, and `tools/research.py` now strips such tokens.

## What changed today, newest first

- `2e4606f` The lodging reviewer is told each traveler pays only for their own room. It had been rejecting correct plans (6 of 10 live with the old wording, 0 of 10 with the new).
- `7fc99a7` (Brandon, commit message is just "e") Draft plan, the ready-made scenario, the calendar grid on the Itinerary tab, a retry route for agents that timed out or fell back.
- `0fc740e` Brandon merged `group-trips-live-run` into his picks work. Transport cards and "Add a rental car" can only be changed by the traveler they belong to.
- `fc4478f` (Brandon) Per-person links, the ideas agent and picks, choosing flights and stays before the days are scheduled.
- `b370be3`, `f00377d` Faster agents: source ids instead of retyped URLs, word limits, fewer avoidable send-backs. Flights are no longer judged by the reviewer model.
- `3b96b6c` Transport is each traveler's own (details below).
- `9c7fdc6` Remove button on itinerary attractions nobody marked as a need.
- `8b5d124` Each traveler's hotel is picked on their own budget alone.

### How per-traveler transport works

- One transport agent prices the legs once and returns up to 2 alternatives per leg. `assign_legs` gives each traveler their own copy in `Traveler.legs`.
- Each traveler can remove a leg, swap it for an alternative, or add a rental car. Card ids are `leg:<traveler>:<leg>`; the rental-car switch is `transport:<traveler>`.
- Budget counts the full price of every leg a traveler keeps. Intercity legs cannot be removed.
- Adding a rental car to a plan that already covers the route adds only the car, so nobody else's legs change. Without that rule the agent re-planned every leg around the car.
- The group's schedule uses the slowest way its travelers have chosen for each ride.
- Removed legs stay removed when transport is planned again, as long as the route is described the same way.

## Work in progress, not committed

`backend/tests/test_orchestrator.py` has an uncommitted new test, `test_attractions_are_planned_by_an_agent_per_city_at_once_and_reviewed_as_one_list`, which fails because the feature is not written yet: one attractions agent per city, run in parallel and reviewed as one list. It was being edited in another session when this file was updated; that session owns it. Without that test, 107 tests pass.

## Not done or not verified

- **Hosting on Akamai is blocked on the user.** They asked for it on 2026-10-10. It needs `deploy/.venv/bin/linode-cli configure` run by the user (it asks for their Linode sign-in); `linode-cli` is installed in `deploy/.venv` (gitignored). After that: create an SSH key (none exists in `~/.ssh`; the script takes `SSH_KEY=`), run `deploy/provision.sh`, then `deploy/deploy.sh`. The Docker build and the Postgres path have never been run. The hosted site would be plain `http://<ip>:8000` with no login, and `.env` is copied to the server.
- Split-offs have only happened in tests, never in a live run.
- "Best" hotel is by rating only, with price as the tie-break. A 4.9 from 394 reviews beat hotels with thousands.
- Transport: airport transfers assume everyone lands at the same airport. Nothing picks a cheaper leg for a smaller budget, and the over-budget swap suggestions cover flights and rooms only. An overnight bus is scheduled as a daytime ride. Alternatives the agent returns without a source or a believable price are dropped, so a leg can have no Swap button.
- Trips planned before per-traveler transport have no legs, so their Transport section is empty until transport is planned again.
- The build function still rejects a lodging result if no option fits the lowest budget. That keeps a room available for that traveler; it does not affect anyone else's room.
- The group's day is bounded by the last arrival and the first departure.
- A cold group run took about 4 to 5 minutes before the speed-ups; `b370be3` measured planning at 174s. The endpoint allows 60 requests a minute.
- The ideas list has no recorded fixture until someone plans the demo trip once with `RECORD_FIXTURES=true`.
- The hotel date parameter in Google Hotels links is undocumented.
- Travel times are estimates; food is not budgeted; no monitor agent.
- The public repo's fixtures contain screenshots and text excerpts of third-party pages.

## Gotchas

- The endpoint rejects an empty `tools` array; context is 32k tokens, output at most 4,096.
- The server does not reload on code changes. Restart it after editing the backend, and rebuild the frontend after editing `frontend/src`.
- Another chat's preview server can hold port 8000 and keep serving old code; Claude cannot stop a server another chat started. Use `tripwright-8001` or ask the user to restart it.
- To test without touching a real trip, copy it: load it with `store.load_trip`, change `state.id`, and save.
- Booking.com blocks headless browsers, so hotels come from Google Hotels.
- `tavily_search` in strands-agents-tools prints a deprecation warning; it still works.
- `load_dotenv` does not override shell variables, so flags set in the shell win over `.env`.
- The user's global `CLAUDE.md` rules apply: state assumptions, keep code minimal, make surgical changes, verify against a concrete check.
