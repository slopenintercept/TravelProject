# Handoff: "Matched to your budget" on a room that is over budget

Written 2026-10-11 at about 05:50 Central by the chat that checks the others' work. You make the fix; that chat checks on it every three minutes, and it is the one that builds, commits, pushes and deploys.

## What happens

On the Choose screen, each stay has a line saying how its room was picked, and the picked room carries a small badge. When no room fits the traveler's budget the two disagree:

> Dec 28 – Dec 30 · Cheapest option found at $50 a night; that is over Alex's lodging budget of about $44 a night.
>
> **Agora Place Kyoto Nijo** Matched to your budget

Seen at 05:45 today on the user's real trip `trip_479d20ea` (`handoffs/retry-lodging-real-trip.md`, under Result), on the Kyoto stay and the last Tokyo night, for both travelers.

## Why

- `assign_rooms` in `backend/tripwright/specialists.py` (line 452) gives each traveler the best-rated room within their budget, or the cheapest one found when none fits, and writes which it was into the stay's `reasoning`.
- `frontend/src/components/Choose.tsx` line 83 puts "Matched to your budget" on whichever room is the stay's `selected_id`, whatever the reason it was picked. Until this morning a stay with no room in budget could not get this far, so the badge was always true (`fd4cd2e` changed that).

## What the user approved

Fixing the contradiction. They did not choose the wording.

## Suggested change

One line: make the badge say **Picked for you**. It is true in both cases, and the line above the options already says whether the room is within the budget or the cheapest found.

Not asked for, so leave it unless the user says otherwise: keeping "Matched to your budget" for rooms that do fit. The frontend cannot tell which case it is without reading the sentence in `reasoning`, and the honest way would be a new field set in `assign_rooms`, which means a backend change and a server restart.

Related, and not part of this: after a traveler confirms and comes back to choose again, `selected_id` is their own choice, so this badge and the flight's "Agent's pick" then sit on what they chose themselves. Leave both.

## Checks

On a throwaway copy of `trip_479d20ea` (see "How to try it"), as Alex and then as Sam:

1. The Kyoto stay and the last Tokyo night: the picked room no longer says "Matched to your budget" under a line that says it is over budget.
2. The first Tokyo stay (within budget): the badge reads sensibly next to "Best-rated option within ... lodging budget ...".
3. The flight's badge still reads "Agent's pick".
4. `cd frontend && npx tsc --noEmit` passes.

There are no frontend tests in this repo, so the browser is the check.

## How to try it

"Gotchas" in `HANDOFF.md` has the general recipe. The specifics:

- **A second backend on a scratch database.** A temporary entry in `.claude/launch.json` named `tripwright-badge`, with `runtimeExecutable: "env"` and args `DATA_DIR=<your scratch folder>/data DATABASE_URL= OBJ_BUCKET= STRIPE_SECRET_KEY= <repo>/backend/.venv/bin/python -m uvicorn tripwright.api:app --app-dir <repo>/backend --port 8014`. Check `/api/health` on that port says `sqlite` and `local disk` before opening anything.
- **Seed it** with a copy of `trip_479d20ea`: save `GET http://localhost:8000/api/trips/trip_479d20ea` (read-only; it is the user's real trip, so nothing else), change `state.id` to `trip_badge1`, and write it with `store.save_trip(TripState.model_validate(state))`, run with the same four variables. With `DATABASE_URL` empty, `config.DATABASE_URL` reads `sqlite:///<DATA_DIR>/tripwright.db`: check it names your scratch folder before saving.
- **A dev server for the frontend:** a second temporary entry named `tripwright-badge-frontend`, `env TRIPWRIGHT_BACKEND=http://localhost:8014 npm --prefix <repo>/frontend run dev -- --port 5184 --strictPort`. Open `http://localhost:5184/#trip_badge1/p1`, then `#trip_badge1/p2`.
- **Do not click "Confirm my flight and stays".** It starts the scheduling agents and uses the inference quota.

## Ground rules

- Read "Start here" and "Gotchas" in `HANDOFF.md` first. The user's global rules apply: minimum code, surgical changes, verify against a concrete check.
- **Your file is `frontend/src/components/Choose.tsx`, line 83 only.** Another chat is changing how the Choose screen is mounted in `frontend/src/App.tsx` at the same time (`handoffs/choose-selection-carried-over.md`). Do not touch `App.tsx` or lines 30 and 31 of `Choose.tsx`.
- **`.claude/launch.json` is shared with that chat.** Add your two entries under the names above, remove only those two when you are done, and never restore the file with git.
- **Do not run `npm run build`.** Two chats are changing the frontend at once; the checking chat builds once, when both are in.
- **Do not commit, push or deploy.** Do not stop or restart the server on port 8000, and change nothing on `trip_479d20ea`.
- The user and a friend are trying the hosted site right now. Do not touch it. Never print `.env` or `.env.hosted`.

## When you finish

Add a `## Result` section at the end of this file: what you changed, what you ran and what it showed for each of the four checks, and anything left undone. Write it last and in one go, after your servers are stopped and your launch entries are removed: the checking chat takes that heading as "ready".

## Result

Written 2026-10-11 by the chat that made the fix.

**Changed:** one line, `frontend/src/components/Choose.tsx` line 83: the badge text "Matched to your budget" is now "Picked for you". Nothing else in the file, and no other file.

**Checked** on `trip_badge1`, a copy of `trip_479d20ea` in a scratch SQLite database (backend on port 8014, `/api/health` said `sqlite` and `local disk`; Vite dev server on port 5184), read from the page text as Alex (`#trip_badge1/p1`) and as Sam (`#trip_badge1/p2`):

1. Kyoto (Dec 28 – 30) and the last Tokyo night (Dec 30 – 31): the line says "Cheapest option found at $50 / $75 a night; that is over ...'s lodging budget of about $44 a night", and the picked room (Agora Place Kyoto Nijo, TOKYO-W-inn Asakusa) reads "Picked for you". "Matched to your budget" appears nowhere on the page. Same for both travelers.
2. First Tokyo stay (Dec 12 – 28): "Best-rated option within ...'s lodging budget of about $44 a night", and Guest House Tokyo Samurai reads "Picked for you". Same for both travelers.
3. The flight's badge still reads "Agent's pick", for both travelers.
4. `cd frontend && npx tsc --noEmit` passes (exit 0), run right after the edit and again at the end with the other chat's `App.tsx` change in the tree.

"Confirm my flight and stays" was not clicked. `trip_479d20ea` was only read, once, with `GET /api/trips/trip_479d20ea`.

**Cleaned up:** both servers stopped (nothing listens on 8014 or 5184), and the `tripwright-badge` and `tripwright-badge-frontend` entries are removed from `.claude/launch.json`. The entries still showing in that file's diff are the other chat's. The scratch database is in this chat's scratchpad, outside the repo.

**Not done, as instructed:** no `npm run build`, no commit, push or deploy. Keeping "Matched to your budget" for rooms that do fit the budget was left out (it needs a new field from `assign_rooms`).

One thing to know when building: the dev server compiled whatever was in `frontend/src` at the time, so the browser check may have run with the other chat's `App.tsx` change in place or without it. The badge line does not depend on it.
