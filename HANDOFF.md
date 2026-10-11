# Tripwright handoff

Updated 2026-10-11, early morning Central, for continuing in a new chat. If you only read one section, read "Start here". Read `README.md` and `DEMO.md` for the product and architecture; this file covers state, decisions and what is left.

## Start here

- **The app is live on Akamai** and the code on the server matches the committed app code. Details and commands are in "Hosting on Akamai".
- **Branch:** `combine-picks-and-group-trips` is where all work happens and is pushed. `main` was fast-forwarded to `ffe77ab` on 2026-10-11, so it has the redesign and the new README; only handoff updates made after that are missing from it (see Git).
- **The whole UI was rebuilt on 2026-10-11** to the design the user approved (see "The redesign"). It is committed, pushed and deployed. The user has not yet looked at the screens that had no mockup.
- Several chats share the folder: run `git status` first, commit only your own files, and never stash or revert someone else's.
- **Waiting on the user, none urgent:**
  1. Whether local runs should keep using the hosted database and bucket that `.env` now names, or go back to local files.
  2. Whether to give the hosted site a clean `https://` name. The user asked why the address is an IP with `:8000`, was offered a domain plus Caddy, and said to leave it for now.
  3. The full planning flow has not been run on the hosted site.
  4. Sign-off on the redesign choices listed under "The redesign".
- **Housekeeping left on the Mac:** Docker Desktop is running from a test build and can be quit. The "Linode sign-in" terminal tab from the earlier chat is finished and can be closed.

## What it is

Tripwright is an agentic group trip planner for Hack Midwest.

- **Agents:** Strands Agents SDK (Python) 1.59.0, talking to the Akamai workshop inference endpoint (OpenAI-compatible, model `hackathon-chat`).
- **Backend:** FastAPI in `backend/tripwright/`. SQLite locally (`data/tripwright.db`), Postgres when `DATABASE_URL` is set.
- **Frontend:** Vite + React + TypeScript in `frontend/`, served by the backend from `frontend/dist`.
- **Live data:** scripted Playwright tools for Google Flights, Google Hotels and Airbnb; Tavily for research; Open-Meteo for weather.

Two people commit to the repo: Amandeep Toor (the user) and Brandon Laing (teammate, works on Windows).

## User flow

1. The host fills in the trip (origin, destination, days, budget). There are no need/want text fields any more.
2. Agents propose a route and date windows, and an ideas agent lists about 16 places. The host picks dates.
3. The host shares the invite link (`#<tripId>/join`). Each traveler joins from it with their name, origin and budget, gets their own link (`#<tripId>/<travelerId>`), then marks the places must do, interested or not for me. They can add a place or ask for more like their picks. No login; the `X-Traveler` header says who is acting.
4. While people join, a draft plan sketches the days from everyone's picks (`draft.py`).
5. The host starts planning: one flight agent per traveler, one attractions agent per city on the route, plus lodging, transport and weather.
6. Each traveler confirms their own flight and rooms (stage `choosing`). The days are scheduled on the first confirm and re-planned on each later one: scheduler, per-traveler budget, `validate_itinerary`.
7. Review: the feed on the left asks each traveler for their decisions (must-sees that did not fit, their budget, their flight, stays and transport), and the board on the right holds their budget and a week calendar with drag, swap and take off. "Finish" lists every booking with links that already carry dates, route and guests.

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

- The last command creates a ready-made seven-traveler Japan trip and prints its links, for trying the flow as an eighth traveler. The script itself runs no agents. Opening the trip does: about ten seconds after it first loads, and again after each join, leave or saved picks, the draft plan is rebuilt, which with an inference key set runs the route planner and one orchestrator call for the note. The flight, lodging, attractions and transport agents wait until the host starts planning.
- Keys live in `.env` at the project root (gitignored). Never print or commit them.
- `DEMO_MODE=true` replays `backend/tripwright/fixtures/recorded.json` with no network or keys.
- `RECORD_FIXTURES=true` records live calls into the fixtures.
- Claude preview configs in `.claude/launch.json`: `tripwright` (port 8000), `tripwright-8001` and `tripwright-8002` (same app on ports 8001 and 8002, for when another chat holds the earlier ports), `tripwright-frontend` (Vite dev server on port 5173; it proxies `/api` to port 8000, or to whatever `TRIPWRIGHT_BACKEND` names), `design-mockups` (a static server on port 5180 for the `design/` folder) and `tripwright-windows` (Brandon's paths).

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
| `frontend/src/App.tsx`, `shell.ts` | The top bar and which screen a trip is on; the context every screen shares (trip, viewer, agents, the board's open tab) |
| `frontend/src/components/` | One per screen: `Start`, `Picks`, `Timeframe`, `Gathering`, `Join`, `Working`, `Choose`, `Review`, `Finish`. Shared: `Board` (plan or Agents tab), `Agents` (tags and the Agents tab), `Calendar`, `Days` (budget row and "Your days"), `DraftPlan`, `Route` |
| `frontend/src/styles.css` | The one stylesheet; the colour tokens are at the top |
| `design/` | The approved mockup (`direction-c-lilac.html`), the handoff the UI was built from (`REDESIGN-HANDOFF.md`), reference screenshots, and screenshots of the built app (`implemented/`) |
| `docs/superpowers/` | Brandon's design specs and plans for picks and for choosing flights and stays first |

Pattern used throughout: the LLM picks ids, Python holds the facts. Tools keep full results in `RunContext`; agents answer with option ids and source ids; `build_*` joins them back and raises `Rejected(problems)` to send the agent back.

## Git

- Remote: `https://github.com/slopenintercept/TravelProject.git` (public).
- Current branch: `combine-picks-and-group-trips`, pushed. It holds everything: Brandon's picks, per-person links and draft plan, merged with the user's `group-trips-live-run`.
- `main` was fast-forwarded to this branch several times on 2026-10-10 and again on 2026-10-11, each time because the user asked. The last time, early on 2026-10-11, left it at `ffe77ab`: the redesign, the approval fix, `design/` and the new docs are in it. A chat's own push to `main` is refused by its permission check ("merge without review"), so the user runs the command below themselves. Fast-forwarding is not a standing rule: commits made here are not in `main` until the user asks again.
- To fast-forward `main` without leaving this branch or touching the working folder: `git push origin origin/combine-picks-and-group-trips:refs/heads/main`, then `git fetch && git branch -f main origin/main`.
- `group-trips-live-run` is pushed at `b370be3` and is fully contained in the current branch.
- GitHub push protection once blocked a push because a third-party Mapbox token sat inside scraped page text. It was redacted, not bypassed, and `tools/research.py` now strips such tokens.

## What changed today, newest first

- The UI was rebuilt to the Direction C design (see "The redesign"), with a README and demo script to match.
- An approval now remembers which flight or room was approved (`TripState.approvals` holds its id), so choosing another one, by any route, puts the card back to proposed. The redesign brought the Approve buttons back, which made this matter.
- `889cd5e` The ideas agents are asked for 16 places, shared out by the nights in each city; the review still accepts 12 to 25.
- Tests are kept off the hosted database: `backend/tests/conftest.py` blanks `DATABASE_URL` and `OBJ_BUCKET` before the app's settings load (see Hosting for why).
- Hosted on Akamai (see Hosting). `deploy/provision.sh` got the temporary-key fix (`560ff83`).
- `b8b92f9` The ideas agent gives each place's reason in under 10 words.
- `2b9ae63` Review cards show their facts as short tags and the agent's reason in a "Why this pick" box (details below).
- `6a672ca` A Back button on every screen, fixed bottom-left. It undoes the last move in the app or reopens the previous step where that can still change, and never undoes the agents' work. It replaces "Back to review" in the Finish footer.
- `33ce425` Attractions are planned by one agent per city on the route, in parallel. Their lists are joined and checked and reviewed once, so there is still one lane, one result and one fallback. Live on the 7-traveler demo trip it was accepted first time in 127s.
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

### How review card tags work

- `cards.py` writes each card's `detail` as short facts joined by ` · `. `Review.tsx` splits on that to draw one tag per fact on the flight card and on the activity opened from the calendar; stays and legs show the same facts as one small line under the name. Keep each fact short: "4.5 Rating", "3 Nights", "10H", "Open 09:00 to 21:00", "Flies home Tue Dec 15, 16:25".
- Anything sentence-length goes in the card's `note` field, shown as a line of text under the tags on the opened activity. Only attractions use it so far, for the agent's booking advice (`availability_note`). That text is the agent's own wording, saved with the trip.
- The rating and duration wording is shared with the Swap list (`_rating`, `_duration`).
- The "Most travelers here pick" cards (`lodging` and `transport`, `kind="default"` in `cards.py`) are no longer drawn as cards of their own. Their title is the small caption on "Your stays" and "Getting around", and their reasoning is the "Why this pick" line on those two cards. Their `detail` is not shown. The Choose screen lists each option's facts as plain text, not tags.

## The redesign

Built on 2026-10-11 from `design/REDESIGN-HANDOFF.md`. Every screen is one layout: a 560px feed on the left where agents report and ask for decisions, and the plan (the board) on the right. Once you are a traveler on a trip, the board has a switch between the plan and an Agents tab; Start, Join and "Who are you?" show the plan with no switch. A headline about one agent's work carries a tag naming that agent: "What sounds good?" and its categories on Picks, the dates headline, every section on Review, "Your flight" and each stay on Choose, the draft plan until planning starts, the budget figure and "Your days". Clicking a tag opens that agent on the Agents tab. Other headlines have no tag: "Plan a trip.", "Who's coming?", "Choose your flight and stays", the agents-working headline (that screen lists one tag per agent under it), Join, "Who are you?" and the feed on Finish. The README has a table of what each step shows.

Choices made while building that the user has not confirmed:

- **No map.** The mockup's map placeholder became the route as city chips with nights.
- **Purple for marked places** (Must do, Interested), as mocked.
- **No attraction cards in the feed.** Clicking an activity on the calendar opens its card at the top of the feed. Places off the calendar are under "Left off your days".
- **"Swap it in"** opens a list of the activities the place could replace: same city, on a day it is open. The replaced one comes off the trip (that is what `swap_item` does).
- **Approve** is back on the flight and the stays, as mocked. It gates nothing.
- **"Getting around"** and **"Things to do"** sections were added to the Review feed (legs; the attractions agent's saved-result notice).
- The screens with no mockup (dates, who's coming, join, agents working, choose, finish) follow the handoff's recommended layouts.
- Fonts load from Google Fonts in `frontend/index.html`.

How it was checked:

- By hand in the browser against a second backend on a throwaway SQLite copy of two real trips, so no real trip was touched, plus one live run in `DEMO_MODE` from Start to Review.
- A review by six agents with two verifiers per finding: 29 findings, 27 confirmed (about 17 distinct, none severe), all fixed. The larger ones: the stale approval above, "Swap it in" offering swaps that could not work, the calendar not fitting at 1280px, a class name shared by the budget pill and the calendar's drop highlight, and failed transport or attractions research leaving no trace in the feed.

## Hosting on Akamai

Tripwright has been live since 2026-10-11 (early morning, Central) on the user's Akamai account, which carries a $300 Hack Midwest credit that expires at the end of 2026. Everything is in Seattle (`us-sea`) and labelled `tripwright-*`:

| Resource | What it is |
|---|---|
| `tripwright-app` | Linode `g6-standard-4` running the app in Docker (`/opt/tripwright`, `docker compose`) |
| `tripwright-fw` | Cloud Firewall: only ports 22 and 8000 come in |
| `tripwright-db` | Managed PostgreSQL 17, one small node; this Mac and the Linode are on its allow list |
| `tripwright-<8 chars>` bucket and `tripwright-key` | Object Storage for page snapshots, with a key limited to that bucket |

- **Address:** `http://<ip>:8000`, plain HTTP on the server's IP with no domain name. This file is in a public repo, so the IP is left out on purpose; get it with `deploy/.venv/bin/linode-cli linodes list --label tripwright-app`. Akamai also gives the server a hostname of the form `<ip-with-dashes>.ip.linodeusercontent.com`, which works on port 8000 too.
- **No login.** Anyone with the address can start trips and spend the inference and Tavily quota.
- **Deployed code:** commit `f1c413e` (the UI rebuild and the approval fix), redeployed on 2026-10-11 at about 04:04 with `deploy/deploy.sh` (health passed, and the JavaScript the server serves is byte for byte the local build). The server's request log was read over SSH first (`docker compose logs` in `/opt/tripwright`): the last request that started or changed anything was two hours earlier, at 02:04. Reading a trip's data from the hosted site was blocked for the chat, so the log is how to check. The deploy copies the working folder, uncommitted changes included, so check `git status` first.
- **The deploy does not delete files that were removed locally.** After the redesign the server's `frontend/src/components` still held the five old components (`AgentPanel`, `BudgetBar`, `CalendarGrid`, `Itinerary`, `TripForm`). They were checked to be byte for byte git's last copies and deleted by hand over SSH on 2026-10-11, because the user asked; the server's component list now matches the repo. `deploy.sh` itself is unchanged, so the next time a file is deleted here its old copy will stay on the server: harmless while it still compiles, a failed build on a file that is not in the repo once it does not. Having `deploy.sh` clear `backend/` and `frontend/` on the server before it copies would end that.
- **Redeploy:** `PATH="$PWD/deploy/.venv/bin:$PATH" SSH_KEY=~/.ssh/tripwright_ed25519 bash deploy/deploy.sh` from the project root. It reuses what exists, rebuilds the container and waits for `/api/health`.
- **Tools on this Mac:** `linode-cli` and `boto3` live in `deploy/.venv` (gitignored); the user signed the CLI in themselves. The deploy SSH key is `~/.ssh/tripwright_ed25519`, made for this and with no passphrase. `ssh -i ~/.ssh/tripwright_ed25519 root@<ip>` gets a shell.
- **`.env` changed at 23:47 on 2026-10-10.** `provision.sh` wrote `OBJ_*` and `DATABASE_URL` into the local `.env`, so any local server or script started after that uses the hosted Postgres and bucket, not `data/tripwright.db`. The local trips are still in the SQLite file; they are just not what a newly started server reads. The server on port 8000 was restarted at 00:20 on 2026-10-11 in a Terminal tab as `DATABASE_URL= .venv/bin/python -m uvicorn tripwright.api:app --port 8000`, so it stays on SQLite; started any other way (the `tripwright` preview configuration, for example) it would use the hosted Postgres. The user has been told and has not said whether to separate them.
- **Tests wrote into the hosted database for a few minutes.** With `DATABASE_URL` in `.env`, pytest ran against Postgres: it took over a minute, three timing tests failed, and it left about 60 throwaway trips there (ids like `trip_<19 digits>`, plus some ordinary-looking ids). `conftest.py` now prevents this and the suite is back to about 5 seconds. The leftover rows are harmless, since trips are only reached by id, and were not deleted: some ordinary-looking ids may be real trips.
- **Verified on the server:** health reports inference key, Tavily, PostgreSQL and Object Storage; the demo trip's first stage was accepted with live fares; flight and hotel page snapshots were taken by the server's own browsers and saved to the bucket. A test trip, `trip_7e281cec`, was left in the hosted database.
- **What went wrong on the way:** the user's first signup was refused by Akamai's fraud check; the Akamai booth gave them a different signup link, which worked. `linode-cli obj` could not make its own access key (the API answers 500 when no region is sent), so `provision.sh` now hands it a temporary key. The database's hostname took a few minutes to resolve after it was created.
- **Stop the billing:** `bash deploy/teardown.sh` deletes everything, including the database and snapshots. It asks for a typed "yes", and only the user should decide to run it.

## Work in progress, not committed

Nothing. `.claude/skills/` and `.claude/agents/` are on this Mac only and ignored by git on purpose: they are third-party tooling (20 MB, with a macOS binary) and the repo is public. `skills-lock.json` records the 23 skills listed in it.

## Not done or not verified

- Redesign: a real mouse drag on the calendar was not tried (the drag events were fired from a script, and the move and the refusal both worked). Phone widths were not checked; under 960px the panes stack. "Apply swaps", "Switch to Airbnb", "Add a rental car", "More like my picks", removing a traveler and the retry button were not clicked after the rebuild; their handlers are unchanged.
- In the `DEMO_MODE` test run the ideas agent was sent back once with `BadRequestError 400: No user query found in messages`, then timed out, so the picks list was empty. Not looked into.
- `DEMO.md` was updated for the new screen but has not been rehearsed against it.
- The hosted site has only been run through the first stage (route, profile, timeframe, ideas). Planning, choosing and review have not been run there.
- `deploy/teardown.sh` has not been run. Its `linode-cli obj rb` line will fail the way bucket creation did (see Hosting) until it is given a key the same way.
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
- Another chat's preview server can hold port 8000 and keep serving old code; `preview_stop` cannot stop a server another chat started. Use `tripwright-8001` or `tripwright-8002`, or ask the user before restarting it.
- One app server is running locally, on port 8000, restarted at 00:20 on 2026-10-11 from a Terminal tab with `DATABASE_URL=` in front, so it is on SQLite (see Hosting). It belongs to no chat's preview list and is stopped by killing whatever listens on the port. It serves `frontend/dist`, so it shows the rebuilt UI. The `design-mockups` static server may also be up, on port 5180. Nothing is listening on 8001 or 8002. Preview configs: `tripwright` (8000), `tripwright-8001`, `tripwright-8002`, `tripwright-frontend`, `design-mockups` (5180), `tripwright-windows`.
- Restarting a server kills any agent run in progress. Check that no trip is busy first (`GET /api/trips/<id>` returns `busy`).
- To test without touching a real trip, copy it: load it with `store.load_trip`, change `state.id`, and save.
- To click through the UI without touching any real data, start a second backend with `DATABASE_URL= OBJ_BUCKET= DATA_DIR=<a temporary folder>` on another port, save copies of trips into its SQLite file, and run `TRIPWRIGHT_BACKEND=http://localhost:<port> npm run dev -- --port 5174`. Check `/api/health` says `sqlite` first.
- After renaming or deleting a file under `frontend/src`, restart the Vite dev server; it kept serving the old module path.
- Booking.com blocks headless browsers, so hotels come from Google Hotels.
- `tavily_search` in strands-agents-tools prints a deprecation warning; it still works.
- `load_dotenv` does not override shell variables, so flags set in the shell win over `.env`.
- The user's global `CLAUDE.md` rules apply: state assumptions, keep code minimal, make surgical changes, verify against a concrete check.
