# Tripwright handoff

Updated 2026-10-11 at about 05:50 Central, for continuing in a new chat. If you only read one section, read "Start here". Read `README.md` and `DEMO.md` for the product and architecture; this file covers state, decisions and what is left.

## Start here

- **The app is live on Akamai**, and the server runs exactly the committed app code: `backend/` and `frontend/` as of commit `20b7737`, deployed at about 05:45 on 2026-10-11 with payments, the map, the two agent fixes and the payment notice fix. Details and commands are in "Hosting on Akamai".
- **The whole UI was rebuilt on 2026-10-11** to the design the user approved. "What the last chat did" below lists everything in order; "The redesign" says what was built and what the user still has to sign off.
- **Branch:** `combine-picks-and-group-trips` is where all work happens. On 2026-10-11 the user told the checking chat to commit, push, deploy and merge as needed, and from about 05:40 that chat pushed the branch and fast-forwarded `main` to it after each commit, the last time at about 05:50. Both hold payments, the map, the two agent fixes and the payment notice fix. Anything committed later may be local or missing from `main`: check `git status -sb` and `git log origin/main..HEAD`. Work that is not committed at all is under "Work in progress, not committed".
- **What the user was doing when this was written:** trying the new UI themselves.
  - Locally, trip `trip_479d20ea` (Alex and Sam, Dec 11 to Dec 31) is at `choosing` with stays for both travelers. Its Lodging agent had timed out at 04:24; "Retry the one that didn't finish" was pressed at 05:40 on 2026-10-11 and the agent was accepted on attempt 1 in about 59 seconds: Tokyo at $41 a night for Dec 12 to 28 (within budget), Kyoto at $50 and a last Tokyo night at $75 (both marked over the $44 budget). Nobody has confirmed a flight or a room; that is the user's to do (`handoffs/retry-lodging-real-trip.md` under Result).
  - On the hosted site, trip `trip_f24799b6` was created at 04:24 and is waiting for dates.
- Several chats share the folder: run `git status` first, commit only your own files, and never stash or revert someone else's.
- **Waiting on the user, none urgent:**
  1. The six screens that had no mockup are not signed off: the user said to leave them for now and to be reminded if they bring those screens up. The fonts question (Google Fonts, or bundled with the app) got no answer. Everything else under "The redesign" is settled.
  2. Nothing is waiting in `handoffs/`. All seven files there end with a `## Result` section saying what was done and checked: `map.md`, `lodging-over-budget.md`, `ideas-lost-task.md`, `payments.md` and `review-chat.md` (with the list of what nobody has verified), and the two from about 05:40 on 2026-10-11, `stale-hold-message.md` and `retry-lodging-real-trip.md`.
  3. Nothing about `main`: the user moved it up to the branch at about 05:32 on 2026-10-11.
  4. The full planning flow has not been run on the hosted site. The user was given the steps at about 04:55 on 2026-10-11 and means to run it themselves.
- **Housekeeping left on the Mac:** Docker Desktop may still be running from an earlier test build and can be quit.

## What the last chat did

One chat, on 2026-10-11 from about 02:30 to 04:35 Central. The user asked for the redesign in `design/REDESIGN-HANDOFF.md` to be built and tested, then for a README, a commit of everything, and a deploy.

1. **Built the redesign.** Rewrote `frontend/src/styles.css` and `App.tsx`, added `shell.ts` and the components `Agents`, `Board`, `Calendar`, `Days`, `Route`, `Start` and `Working`, rewrote the other screens, and deleted `AgentPanel`, `BudgetBar`, `CalendarGrid`, `Itinerary` and `TripForm`.
2. **Tested it** in the browser against a second backend on a throwaway SQLite copy of two real trips (see Gotchas for how), plus one live run in `DEMO_MODE` from Start to Review.
3. **Had it reviewed before shipping:** six reviewing agents, two verifiers per finding. 27 of 29 findings were confirmed (about 17 distinct, none severe) and all were fixed. One needed a backend change (approvals, below).
4. **Wrote the docs:** the README (how the screen works, how to run, test and deploy), `DEMO.md` for the new screen, and this file. A second set of agents checked all three against the code; 37 wrong or misleading statements were confirmed and corrected, many of them older than the redesign.
5. **Committed and pushed** to `combine-picks-and-group-trips`, in this order:

   | Commit | What |
   |---|---|
   | `889cd5e` | Another chat's finished change, committed after the tests passed: the ideas agents are asked for 16 places |
   | `fe15c3e` | An approval remembers which flight or room it was for |
   | `d357d45` | The UI rebuild |
   | `f1c413e` | `design/`, `skills-lock.json`, `.impeccable/config.json`, the `design-mockups` preview entry, and the ignore rules for `.claude/skills/` and `.claude/agents/` |
   | `ffe77ab` | README, demo script and handoff |
   | `6a50ad6`, `5edada2` | Handoff updates |
   | `5360e3b` | A draft agent that was cut off when planning started is left out of the agents list |

6. **`main`:** the chat's own push to `main` was refused by its permission check, so the user ran the fast-forward themselves, twice; the second left `main` at `d292b70`, level with the branch at that moment.
7. **Deployed twice** with `deploy/deploy.sh`: `f1c413e` at 04:04 and `5360e3b` at 04:29. Each time the server's log was checked first, and the second time a trip that had just been started on the hosted site was waited out. After each, the JavaScript the server serves was compared byte for byte with the local build.
8. **Cleaned the server:** the five deleted components were still in the server's source folder, because the deploy does not remove files. At the user's request they were deleted over SSH after checking they were identical to git's last copies.
9. **The local server was restarted by the user** at 04:17 (see Gotchas), so it runs today's backend code.

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
- Local runs use local files only (SQLite and `data/evidence`); the hosted database and bucket are for the hosted site (decided 2026-10-11).
- The hosted site keeps its plain `http://<ip>:8000` address for now; the user said to leave it.
- Agents never enter payment details or passwords, never create accounts, and never bypass bot detection or CAPTCHAs. "Booking" means handing the user a link. One exception to Tripwright never taking payment, chosen by the user on 2026-10-11 for the Best FinTech App challenge: Pay together on Finish, with test cards and Stripe test mode only and no agent involved.

## How to run

```bash
cd backend && .venv/bin/python -m uvicorn tripwright.api:app --port 8000
```

That command uses the local SQLite file and `data/evidence`: since about 04:50 on 2026-10-11 the hosted database and bucket are named in `.env.hosted`, which only the deploy scripts read (see Hosting). The server on port 8000 was restarted after that, at about 05:13 on 2026-10-11, from the project root as `backend/.venv/bin/uvicorn tripwright.api:app --app-dir backend --port 8000`.

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
- `main` was fast-forwarded to this branch several times on 2026-10-10 and again on 2026-10-11, each time because the user asked. At about 05:32 on 2026-10-11 the user ran it themselves; after that they told the checking chat to merge as needed, and its pushes to `main` went through (the last at about 05:50). Earlier chats' pushes to `main` were refused by their permission check ("merge without review"), and a new chat should expect the same until the user says otherwise. Fast-forwarding is not a standing rule: commits made here are not in `main` until the user asks again.
- To fast-forward `main` without leaving this branch or touching the working folder: `git push origin origin/combine-picks-and-group-trips:refs/heads/main`, then `git fetch && git branch -f main origin/main`.
- `group-trips-live-run` is pushed at `b370be3` and is fully contained in the current branch.
- GitHub push protection once blocked a push because a third-party Mapbox token sat inside scraped page text. It was redacted, not bypassed, and `tools/research.py` now strips such tokens.

## What changed today, newest first

- `20b7737` A line about payments at the top of the feed is cleared when another traveler changes the payments. After Alex approved, "... is on hold. Nobody is charged until Sam approves." used to stay above "Trip paid" once Sam had approved or backed out. `useTrip.ts` remembers the payments a notice was shown with and drops the notice when a refresh brings different ones; a tab's own notice stays. It applies to any notice, not only payment ones (built from `handoffs/stale-hold-message.md`; checked on the built frontend in the browser).
- `b276145` Pay together on the Finish screen, built by the payments chat for the Best FinTech App challenge. Each traveler approves their own share (their budget total) on a test card picked from a list. Approving places a hold; every card is charged at once when the whole group has approved, and anyone backing out first releases every hold (`backend/tripwright/payments.py`, `POST` and `DELETE /api/trips/{id}/payments`, `TripState.payments`, `frontend/src/components/Pay.tsx`). No LLM is involved and no card number is typed.
  - `STRIPE_SECRET_KEY` in `.env` is a restricted Stripe test key the user made at about 04:55 on 2026-10-11; `deploy.sh` sends it to the server with the rest of `.env`. With it each hold is a test-mode PaymentIntent with manual capture; without it the holds are kept in the trip; a key that is not a test key is refused.
  - Checked on the hosted site at about 05:14 against real Stripe test mode, on `trip_paycheck`: a hold was `requires_capture`, backing out made it `canceled`, both payments were `succeeded` once both travelers approved, and the declining test card was refused. All were `livemode` false.
  - `trip_paydemo` on the hosted site is the same finished two-traveler trip (Alex `p1`, Sam `p2`), unpaid, kept for the demo. Both are copies of local `trip_99aaaeb1` that the payments chat added to the hosted database.
  - Known limits: a hold keeps the amount it was placed for if the plan changes afterwards; holds never expire in the app; after capture the money goes nowhere (a real product would pass it to a booking API).
- A map on the draft plan: Leaflet on OpenStreetMap tiles, one pin per place, the viewer's must-do places filled (`frontend/src/components/Map.tsx`; built from `handoffs/map.md`).
- Lodging no longer times out when no room fits the budget: it takes the cheapest central room and the card says it is over budget (built from `handoffs/lodging-over-budget.md`).
- A specialist keeps its task when Strands trims a long conversation (built from `handoffs/ideas-lost-task.md`).
- `36ae915`, committed at about 05:10 on 2026-10-11 and pushed with the rest at about 05:17: local runs use local files, and the deploy clears `backend/` and `frontend/` on the server before copying. The six hosted settings moved from `.env` to `.env.hosted`; `deploy/lib.sh`, `deploy.sh`, `provision.sh` and `teardown.sh` follow (see Hosting).
- `5360e3b` Once planning has started, a draft agent that did not finish is left out of the feed's agent list, the Agents tab and its count (`laneOrder` in `Agents.tsx`). The draft is only rebuilt while people join, so if planning starts mid-rebuild its status stays "working" for good. A draft agent that finished is still listed.
- `d357d45`, `ffe77ab` The UI was rebuilt to the Direction C design (see "The redesign"), with a README and demo script to match.
- `fe15c3e` An approval now remembers which flight or room was approved (`TripState.approvals` holds its id), so choosing another one, by any route, puts the card back to proposed. The redesign brought the Approve buttons back, which made this matter.
- `889cd5e` The ideas agents are asked for 16 places, shared out by the nights in each city; the review still accepts 12 to 25.
- Tests are kept off the hosted database: `backend/tests/conftest.py` blanks `DATABASE_URL` and `OBJ_BUCKET` before the app's settings load (see Hosting for why).
- Hosted on Akamai (see Hosting). `deploy/provision.sh` got the temporary-key fix (`560ff83`).
- `b8b92f9` The ideas agent gives each place's reason in under 10 words.
- `2b9ae63` Review cards show their facts as short tags and the agent's reason in a "Why this pick" box (details below).
- `6a672ca` A Back button on every screen, fixed bottom-left (since the redesign it is in the top bar). It undoes the last move in the app or reopens the previous step where that can still change, and never undoes the agents' work. It replaces "Back to review" in the Finish footer.
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

Choices made while building. At about 05:05 on 2026-10-11 the user settled most of them, from a page with a picture of each ("Tripwright Redesign Choices", a private Artifact): build a map the easy way (`handoffs/map.md`; built since, see the first bullet below), keep purple, and keep Approve as a marker that gates nothing. They left three to the chat, which kept them as built: activities on the calendar, "Swap it in", and the two added Review sections. Still open: the six screens with no mockup, and the fonts.

- **A map on the draft plan.** Under the route's city chips, a Leaflet map on OpenStreetMap tiles (`components/Map.tsx`) pins every place on the list that has coordinates; the viewer's must-do places are filled. It shows wherever the draft plan does, once the first draft has looked the coordinates up.
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
- **Deployed code:** `backend/` and `frontend/` as of commit `20b7737`, redeployed on 2026-10-11 at about 05:45 with `deploy/deploy.sh` (the deploy before it, at about 05:13, was `29f5a53`). The hosted log for the 40 minutes before showed no trip running, and afterwards every committed file under `backend/` and `frontend/` was on the server with the same checksum. (Health passed and says `"payments": "stripe test mode"`, and the JavaScript the server serves is byte for byte the local build in `frontend/dist`). The deploy copies the working folder, uncommitted changes included, so check `git status` first.
- **How to check nobody is mid-run before a deploy:** read the server's request log over SSH (`cd /opt/tripwright && docker compose logs --since 3h app`, and look for `POST`, `PUT` and `DELETE` lines), then ask the hosted site for the `busy` flag of any trip that was just started (`GET /api/trips/<id>`) and wait until it is false. Before the 04:29 deploy a trip had been created five minutes earlier; its first stage finished at 04:28 and the deploy ran then. A command that printed a hosted trip's full state was refused by the chat's permission check; one that printed only its stage and `busy` went through.
- **The deploy clears `backend/` and `frontend/` on the server before it copies** (changed at about 04:50 on 2026-10-11; the user left the decision to the chat). A file deleted here no longer stays behind there. Before that the server had kept the five components the redesign deleted (`AgentPanel`, `BudgetBar`, `CalendarGrid`, `Itinerary`, `TripForm`); they were removed by hand over SSH on 2026-10-11 because the user asked. The payments chat's deploy at about 05:13 on 2026-10-11 was the first run of the changed script; afterwards the server's `frontend/src/components` and `backend/tripwright` listed exactly the files in the repo.
- **Redeploy:** `PATH="$PWD/deploy/.venv/bin:$PATH" SSH_KEY=~/.ssh/tripwright_ed25519 bash deploy/deploy.sh` from the project root. It reuses what exists, rebuilds the container and waits for `/api/health`.
- **Tools on this Mac:** `linode-cli` and `boto3` live in `deploy/.venv` (gitignored); the user signed the CLI in themselves. The deploy SSH key is `~/.ssh/tripwright_ed25519`, made for this and with no passphrase. `ssh -i ~/.ssh/tripwright_ed25519 root@<ip>` gets a shell.
- **Local runs use local files.** At 23:47 on 2026-10-10 `provision.sh` wrote `OBJ_*` and `DATABASE_URL` into the local `.env`, which pointed every local server and script at the hosted Postgres and bucket. At about 04:50 on 2026-10-11 the user decided local stays local, so those six values now live in `.env.hosted` (gitignored, readable only by the user) and are empty in `.env`. `provision.sh` and `teardown.sh` write `.env.hosted`; `deploy.sh` sends the server the local `.env` with those six lines taken from `.env.hosted`. What it would send was compared with the old `.env`: the same 16 settings, one line each. A server started after the change needs no `DATABASE_URL=` in front. `backend/tests/conftest.py` still blanks the variables for tests, now as a second safeguard.
- **Tests wrote into the hosted database for a few minutes.** With `DATABASE_URL` in `.env`, pytest ran against Postgres: it took over a minute, three timing tests failed, and it left about 60 throwaway trips there (ids like `trip_<19 digits>`, plus some ordinary-looking ids). `conftest.py` now prevents this and the suite is back to about 5 seconds. The leftover rows are harmless, since trips are only reached by id, and were not deleted: some ordinary-looking ids may be real trips.
- **Verified on the server:** health reports inference key, Tavily, PostgreSQL and Object Storage; the demo trip's first stage was accepted with live fares; flight and hotel page snapshots were taken by the server's own browsers and saved to the bucket. A test trip, `trip_7e281cec`, was left in the hosted database.
- **What went wrong on the way:** the user's first signup was refused by Akamai's fraud check; the Akamai booth gave them a different signup link, which worked. `linode-cli obj` could not make its own access key (the API answers 500 when no region is sent), so `provision.sh` now hands it a temporary key. The database's hostname took a few minutes to resolve after it was created.
- **Stop the billing:** `bash deploy/teardown.sh` deletes everything, including the database and snapshots. It asks for a typed "yes", and only the user should decide to run it.

## Work in progress, not committed

- Nothing in the code. The payments chat committed its work at 05:12 on 2026-10-11 (`b276145`), and the code at `20b7737` was checked as committed: 126 backend tests pass, the frontend type check passes, and `frontend/dist` is the build of that source. The map chat's two test entries in `.claude/launch.json` were removed at about 05:38 on 2026-10-11 because the user asked, so that file is as committed.

`.claude/skills/` and `.claude/agents/` are on this Mac only and ignored by git on purpose: they are third-party tooling (20 MB, with a macOS binary) and the repo is public. `skills-lock.json` records the 23 skills listed in it.

## Not done or not verified

- The Lodging agent timing out when no room fits the budget is fixed (2026-10-11, committed; details in `handoffs/lodging-over-budget.md` under Result). A hotel or Airbnb search with nothing at or under the price now says so and lists the three cheapest rooms, the review no longer refuses a stay for being over the tightest budget, and the agent is told to take the cheapest central room and to search at most two neighbourhoods per stay. On a copy of `trip_479d20ea` the retry was accepted on the first attempt in about 80 seconds, with the Kyoto stay ($54 a night) and the last Tokyo night ($57) shown as over each traveler's $44 budget. On the user's own `trip_479d20ea` the retry was pressed at 05:40 on 2026-10-11 and worked the same way (`handoffs/retry-lodging-real-trip.md`).
- Two things seen on the Choose screen during that retry, not fixed: a room that is over the traveler's budget carries the badge "Matched to your budget" under the line saying it is over budget; and `Choose.tsx` reads its selected flight and rooms from the trip only when the screen first opens, so going from one traveler's link to another's in the same tab leaves no flight selected and a wrong total until the page is reloaded.
- `deploy/provision.sh` and `deploy/teardown.sh` have not been run since they were pointed at `.env.hosted`. `deploy.sh` has: after the 05:13 deploy on 2026-10-11 the server's `.env` held all six hosted settings once each and `/api/health` said `postgresql` and `object storage`. That file is still mode 644 on the server, because it kept the mode it had; `deploy.sh` only makes a new one private.
- Redesign: a real mouse drag on the calendar was not tried (the drag events were fired from a script, and the move and the refusal both worked). Phone widths were not checked; under 960px the panes stack. "Apply swaps", "Switch to Airbnb", "Add a rental car", "More like my picks", removing a traveler and the retry button were not clicked after the rebuild; their handlers are unchanged.
- **An agent that searches for a long time no longer loses its task** (fixed and committed 2026-10-11; deployed, and running on port 8000, since about 05:13). In a `DEMO_MODE` run that morning the ideas agent was sent back with `BadRequestError 400: No user query found in messages` and then timed out, so the picks list was empty: its conversation outgrew the endpoint's 32k context, Strands trimmed the oldest messages, the task among them, and the endpoint refuses a request with no user message. Specialists are now built by `specialist_agent` in `orchestrator.py` with `SlidingWindowConversationManager(pin_first=1)`, which keeps the task through both the overflow trim and the 40-message trim after each run; `backend/tests/test_conversation.py` covers both. Checked on the real endpoint with three small requests: task + tool call + result is answered, task + send-back + tool call + result (two user messages in a row) is answered, and tool call + result with no task still gets the 400. **Not run:** a whole trip on the real endpoint. **Not fixed, on purpose:** demo mode still answers a search with the closest recorded one, and the 80 recorded searches are all Tokyo and Kyoto, so on a route with other cities the ideas agent can still search until its 240 seconds run out and return nothing. Details in `handoffs/ideas-lost-task.md`.
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
- One app server is running locally, on port 8000. The payments chat restarted it at about 05:13 on 2026-10-11, after checking that no trip was busy, in a tab of the Claude app's Terminal pane titled "Tripwright :8000". `/api/health` says `sqlite`, `local disk` and `"payments": "stripe test mode"`. It belongs to no chat's preview list; Ctrl+C in that terminal tab, or killing whatever listens on the port, stops it. It serves `frontend/dist`, so a rebuild shows up on reload without a restart. The `design-mockups` static server may also be up, on port 5180. Nothing is listening on 8001 or 8002. Preview configs: `tripwright` (8000), `tripwright-8001`, `tripwright-8002`, `tripwright-frontend`, `design-mockups` (5180), `tripwright-windows`.
- Restarting a server kills any agent run in progress. Check that no trip is busy first (`GET /api/trips/<id>` returns `busy`).
- To test without touching a real trip, copy it: load it with `store.load_trip`, change `state.id`, and save.
- To click through the UI without touching any real data, start a second backend with `DATA_DIR=<a temporary folder>` on another port, save copies of trips into its SQLite file, and run `TRIPWRIGHT_BACKEND=http://localhost:<port> npm run dev -- --port 5174`. Check `/api/health` says `sqlite` first.
- After renaming or deleting a file under `frontend/src`, restart the Vite dev server; it kept serving the old module path.
- Booking.com blocks headless browsers, so hotels come from Google Hotels.
- `tavily_search` in strands-agents-tools prints a deprecation warning; it still works.
- `load_dotenv` does not override shell variables, so flags set in the shell win over `.env`.
- A chat cannot push to `main` (its permission check refuses it as a merge without review). Give the user the command to run.
- The user runs commands themselves in the app's Terminal pane when given one. Give one command per code block.
- The user's global `CLAUDE.md` rules apply: state assumptions, keep code minimal, make surgical changes, verify against a concrete check.
