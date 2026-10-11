# Handoff: the "on hold" line that outlives the hold

Written 2026-10-11 at about 05:40 Central by the chat that checked payments. You make the fix; that chat checks on it every three minutes, and it is the one that commits, pushes and deploys.

## What happens

On the Finish screen, with two travelers each in their own tab:

1. Alex approves his share. The line at the top of Alex's feed reads "$2,737 is on hold. Nobody is charged until Sam approves."
2. Sam approves. Both tabs change with no reload: both rows read "Paid" and the box reads "Trip paid. $5,652 charged across 2 cards."
3. Alex's line from step 1 is still there, right above "Trip paid", until he clicks Dismiss.

The same happens when Sam backs out instead: Alex's row reads "Hold released" under a line that still says his share is on hold.

Nothing is charged wrongly and the box itself is always right. It only reads as a contradiction, and the demo shows exactly this on two screens (`DEMO.md`, "2:45 Finish and pay together").

## Why

- `backend/tripwright/payments.py` answers each approve or back out with a sentence (lines 70, 76, 81 and 96), and `_pay` in `backend/tripwright/api.py` then sends a `state` event to every open tab.
- `frontend/src/useTrip.ts`: `act` (line 135) shows that sentence as `notice`, for the tab that made the request. It is cleared only by that tab's next action or by Dismiss.
- The other tab's action reaches this tab as a `state` event (line 114), which fetches the trip again and replaces `view`. Nothing looks at `notice`, so a sentence about the old payments stays over the new ones.
- `frontend/src/App.tsx` (lines 120 to 133) draws the line.

## What the user approved

Fix the stale line before the demo.

## Suggested change

The smallest version I can see, about five lines in `useTrip.ts`. The checks below are what matter; if you find something simpler that passes them, use it.

- Remember what the trip's payments were when the notice was shown (in `act`, from the response).
- When a later refresh brings different payments, clear the notice.

Two things that will trip up the obvious versions:

- **This tab's own action also causes a `state` event.** "Clear the notice on any `state` event" wipes a sentence the moment it appears. The refresh after your own action brings the same payments as the response did, which is why comparing payments works.
- **`setView` and `setNotice` land in the same render.** An effect that clears the notice whenever the payments change will clear the one that was just set.

Keep in mind:

- `state.payments` can be missing (a server started before payments existed); `Pay.tsx` line 39 allows for that.
- Out of scope: the wording of any sentence, the look of the line, how notices behave for anything that is not a payment, and the backend.

## Checks

In two tabs on a throwaway copy of a finished two-traveler trip (see "How to try it"):

1. Alex approves with Visa. His line reads "... is on hold. Nobody is charged until ... approves." and stays.
2. The other traveler approves. In Alex's tab the line is gone with no reload and both rows read "Paid". The other traveler's own tab still reads "Everyone is in. Every card was charged."
3. On a fresh copy: Alex approves, the other traveler backs out. In Alex's tab the line is gone and his row reads "Hold released". The other tab still reads "... backed out. Every hold was released and nobody was charged."
4. The declining card: "... was declined, so no hold was placed. Try another card." appears and stays in the tab that tried it.
5. Dismiss still clears a line.
6. `cd frontend && npx tsc --noEmit` passes.

There are no frontend tests in this repo, so the browser is the check.

## How to try it

"Gotchas" in `HANDOFF.md` has the general recipe. The specifics that worked an hour ago:

- **A second backend on a scratch database.** A temporary entry in `.claude/launch.json` with `runtimeExecutable: "env"` and args `DATA_DIR=<your scratch folder>/data DATABASE_URL= OBJ_BUCKET= STRIPE_SECRET_KEY= <repo>/backend/.venv/bin/python -m uvicorn tripwright.api:app --app-dir <repo>/backend --port 8013`. The empty `STRIPE_SECRET_KEY=` matters: without it every click makes a test payment in the user's Stripe account. With it the holds are kept in the trip and the screen behaves the same.
- **Check `/api/health` on that port** says `sqlite`, `local disk` and `"payments": "holds kept in the app"` before clicking anything.
- **Seed it** with copies of `trip_99aaaeb1`: save `GET http://localhost:8000/api/trips/trip_99aaaeb1` (read-only), change `state.id`, and write it with `store.save_trip(TripState.model_validate(state))`, run with the same four variables. With `DATABASE_URL` empty, `config.DATABASE_URL` reads `sqlite:///<DATA_DIR>/tripwright.db`, not an empty string: check it names your scratch folder before saving. A paid copy cannot be paid again, so make one copy per run (`trip_msg1`, `trip_msg2`, ...).
- **A dev server for the frontend**, so nothing has to be built while you iterate: a second temporary entry, `env TRIPWRIGHT_BACKEND=http://localhost:8013 npm --prefix <repo>/frontend run dev -- --port 5183 --strictPort`. Open `http://localhost:5183/#trip_msg1/p1` and `#trip_msg1/p2`, and click **Finish** (top right of **Your days**) in each.
- Remove both entries from `.claude/launch.json` and stop both servers when you are done.

## Ground rules

- Read "Start here" and "Gotchas" in `HANDOFF.md` first. The user's global rules apply: minimum code, surgical changes, verify against a concrete check.
- Your files are `frontend/src/useTrip.ts` and, only if you need it, `frontend/src/App.tsx`. Nothing in `backend/`.
- **Another chat is pressing Retry on the user's real trip on port 8000 while you work** (`handoffs/retry-lodging-real-trip.md`). Do not stop or restart the server on port 8000, and do not open or change `trip_479d20ea`.
- **Run `npm run build` once, at the very end,** after the checks pass. It replaces `frontend/dist`, which port 8000 serves from disk; that is safe for a trip being planned, and it is what the deploy will ship.
- **Do not commit, push or deploy.** At 05:12 today two chats came within a minute of committing the same work. The checking chat commits yours after reading your Result.
- Do not touch the hosted site. Never print `.env` or `.env.hosted`.

## When you finish

Add a `## Result` section at the end of this file: the files you changed, what you ran and what it showed for each of the six checks, and anything left undone. Write it last and in one go, after the build: the checking chat takes that heading as "ready to commit and deploy".

## Result

Written 2026-10-11 by the chat that made the fix. Nothing is committed, pushed or deployed.

**Changed:** `frontend/src/useTrip.ts` only (7 lines added, 1 replaced). `App.tsx` and `backend/` are untouched.

- `act` remembers the payments its response carried (`noticePayments`, a ref) when it shows a notice.
- `refresh` (the fetch after a `state` event) clears the notice if the payments it gets back differ from those.
- This tab's own action refreshes with the same payments its response had, so its own notice stays.

**Checks**, in two tabs (`#…/p1` Alex, `#…/p2` friend2) on the Vite dev server at port 5183 against a scratch backend on port 8013. `/api/health` there read `sqlite`, `local disk`, `holds kept in the app`. The trips were copies of `trip_99aaaeb1` with payments emptied.

1. Pass. `trip_msg1`: Alex approved with Visa. His line read "$2,737 is on hold. Nobody is charged until friend2 approves." and was still there 3 seconds later, after his own refresh.
2. Pass. friend2 approved. Alex's tab, with no reload: no line, both rows "Paid · Visa ···· 4242". friend2's tab kept "Everyone is in. Every card was charged."
3. Pass. `trip_msg2`: Alex approved, friend2 backed out. Alex's tab: no line, his row "Hold released". friend2's tab kept "friend2 backed out. Every hold was released and nobody was charged."
4. Pass. `trip_msg1`, before check 1: the declining card gave "Visa ···· 0002 was declined, so no hold was placed. Try another card." in Alex's tab, still there 2 seconds later. friend2's tab showed no line.
5. Pass. Dismiss cleared that line.
6. Pass. `npx tsc --noEmit` printed nothing, before and after the checks.

Then `npm run build` once: `dist/assets/index-3E-sSUu9.js`, built with no errors.

**Left undone or not checked:**

- The built `frontend/dist` was not clicked through; the checks ran on the dev server from the same source.
- Not tried against Stripe test mode (the scratch backend had an empty `STRIPE_SECRET_KEY`), and not tried with a server that sends no `payments`.
- One side effect to know about: the rule covers every notice, not only payment ones. A line about something else (a refused calendar move, say) also clears if another traveler changes the payments while it is showing. It does not clear on any other change.

**Cleaned up:** both temporary entries are out of `.claude/launch.json` (the file has no diff), both servers are stopped, and nothing is listening on 8013 or 5183. The scratch database is in this chat's scratchpad, outside the repo. Port 8000 and `trip_479d20ea` were not touched, apart from one read-only `GET` of `trip_99aaaeb1` on port 8000.
