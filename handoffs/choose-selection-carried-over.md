# Handoff: the Choose screen keeps the last traveler's selection

Written 2026-10-11 at about 05:50 Central by the chat that checks the others' work. You make the fix; that chat checks on it every three minutes, and it is the one that builds, commits, pushes and deploys.

## What happens

On a trip at `choosing`, in one browser tab:

1. Open Sam's link, `#<trip>/p2`. The Choose screen shows Sam's flight and rooms selected and a total.
2. Change the address to Alex's link, `#<trip>/p1`, without reloading.
3. Alex's screen has no flight selected, and "Flight and stays" counts the stays only. On the user's real trip it read $831; after a reload it read $2,523.

Clicking "Confirm my flight and stays" in that state is refused ("That flight is not one of your options"), so nothing wrong is saved. It looks broken, and two people passing one laptop between them will see it.

Seen at 05:45 today on `trip_479d20ea` (`handoffs/retry-lodging-real-trip.md`, under Result).

## Why

- `frontend/src/components/Choose.tsx` lines 30 and 31 keep the selected flight and rooms in `useState`, and the starting values (`flights?.selected_id`, each stay's `selected_id`) are read once, when the component is first mounted.
- `frontend/src/App.tsx` line 179 renders the same `<Choose>` for whoever `you` is. A change of address swaps `you` (the `hashchange` listener at line 45) without unmounting it, so Sam's flight id stays in state. It is not one of Alex's options, so no radio is checked. The room ids often still match, because both travelers' stays are copies of the same options.

## What the user approved

Fixing it.

## Suggested change

One attribute in `App.tsx`: `key={you.id}` on `<Choose>`. React then mounts a fresh component for a different traveler, and both `useState`s start from that traveler's own picks. If you find something simpler, use it; the checks below are what matter.

Two cases I read from the code and believe are already fine. Say so in your Result if you read them differently, but do not build anything for them:

- **The top bar's "Switch".** It goes through "Who are you?", which replaces the Choose screen, so coming back mounts it fresh.
- **A Choose screen that is open when a Retry starts.** The Lodging agent's status becomes `working`, `optionsReady` (line 64) turns false, and the Working screen replaces Choose until the agent is done (line 84). Do not press Retry to test this: it runs the agents and uses the inference quota.

## Checks

On a throwaway copy of `trip_479d20ea` (see "How to try it"), in one tab:

1. Open `#<copy>/p2`. Note Sam's selected flight, rooms and total.
2. Change the address to `#<copy>/p1` without reloading. Alex's flight marked "Agent's pick" is selected, a room is selected in every stay, and the total is the flight plus the stays. Reload: nothing changes.
3. Change the address back to `#<copy>/p2` without reloading: the same as in step 1.
4. Select a different flight for Sam, change to `p1` and back to `p2`: Sam's selection is back to the one the trip holds. That is expected, since nothing was confirmed.
5. `cd frontend && npx tsc --noEmit` passes.

There are no frontend tests in this repo, so the browser is the check.

## How to try it

"Gotchas" in `HANDOFF.md` has the general recipe. The specifics:

- **A second backend on a scratch database.** A temporary entry in `.claude/launch.json` named `tripwright-choose`, with `runtimeExecutable: "env"` and args `DATA_DIR=<your scratch folder>/data DATABASE_URL= OBJ_BUCKET= STRIPE_SECRET_KEY= <repo>/backend/.venv/bin/python -m uvicorn tripwright.api:app --app-dir <repo>/backend --port 8015`. Check `/api/health` on that port says `sqlite` and `local disk` before opening anything.
- **Seed it** with a copy of `trip_479d20ea`: save `GET http://localhost:8000/api/trips/trip_479d20ea` (read-only; it is the user's real trip, so nothing else), change `state.id` to `trip_choose1`, and write it with `store.save_trip(TripState.model_validate(state))`, run with the same four variables. With `DATABASE_URL` empty, `config.DATABASE_URL` reads `sqlite:///<DATA_DIR>/tripwright.db`: check it names your scratch folder before saving.
- **A dev server for the frontend:** a second temporary entry named `tripwright-choose-frontend`, `env TRIPWRIGHT_BACKEND=http://localhost:8015 npm --prefix <repo>/frontend run dev -- --port 5185 --strictPort`. Open `http://localhost:5185/#trip_choose1/p2`.
- **Do not click "Confirm my flight and stays".** It starts the scheduling agents and uses the inference quota.

## Ground rules

- Read "Start here" and "Gotchas" in `HANDOFF.md` first. The user's global rules apply: minimum code, surgical changes, verify against a concrete check.
- **Your file is `frontend/src/App.tsx`, the `<Choose>` element at line 179 only.** Another chat is changing a label at line 83 of `frontend/src/components/Choose.tsx` at the same time (`handoffs/choose-budget-badge.md`). If your fix needs `Choose.tsx`, keep to lines 30 and 31 and leave line 83 alone.
- **`.claude/launch.json` is shared with that chat.** Add your two entries under the names above, remove only those two when you are done, and never restore the file with git.
- **Do not run `npm run build`.** Two chats are changing the frontend at once; the checking chat builds once, when both are in.
- **Do not commit, push or deploy.** Do not stop or restart the server on port 8000, and change nothing on `trip_479d20ea`.
- The user and a friend are trying the hosted site right now. Do not touch it. Never print `.env` or `.env.hosted`.

## When you finish

Add a `## Result` section at the end of this file: what you changed, what you ran and what it showed for each of the five checks, and anything left undone. Write it last and in one go, after your servers are stopped and your launch entries are removed: the checking chat takes that heading as "ready".

## Result

Written 2026-10-11 by the chat that made the fix. Not built, not committed, not deployed: that is the checking chat's.

**What changed.** One line, in `frontend/src/App.tsx`: `key={you.id}` on the `<Choose>` element, as suggested. `Choose.tsx` was not touched.

**How it was checked.** A copy of `trip_479d20ea` saved as `trip_choose1` in a scratch SQLite file, served by a second backend on port 8015 (`/api/health` said `sqlite` and `local disk`) and a Vite dev server on port 5185. One tab; the address was changed by setting `location.hash`, and a marker on `window` survived every change, so the page never reloaded between steps.

| Check | What it showed |
|---|---|
| 1. Open `#trip_choose1/p2` | Sam: Alaska and JAL ($1,793, "Agent's pick") selected, a room selected in each of the three stays, "Flight and stays: $2,624 of your $3,000 budget". |
| 2. Change to `p1`, no reload | Alex: United and ANA ($1,692, "Agent's pick") selected, a room selected in each of the three stays, $2,523. After a reload the selections and the total were the same. |
| 3. Back to `p2`, no reload | The same as check 1: Alaska and JAL, three rooms, $2,624. |
| 4. Select another flight for Sam, go to `p1` and back | With United ($1,861) selected Sam's total read $2,692. Alex's screen still read $2,523 with United and ANA. Back on `p2`, Sam was on Alaska and JAL and $2,624 again. |
| 5. `npx tsc --noEmit` | Passed (exit 0). |

**The check catches the bug.** With the line taken out, the same steps showed the fault from this handoff: on `p1` no flight was selected and the total read $831. With the line back in, it read $2,523.

**The two cases read from the code.** I read both the same way as the handoff, and built nothing for them.

- "Switch" in the top bar links to `#<trip>` with no traveler, so `you` is empty and the "Who are you?" screen replaces Choose.
- A Retry sets the Lodging agent to `working`, `optionsReady` turns false and the Working screen replaces Choose. Not tried in the browser, since Retry runs the agents.

**Left as it was.**

- "Confirm my flight and stays" was never clicked, and Retry was never pressed.
- `trip_479d20ea` was only read: afterwards it was still at `choosing`, neither traveler confirmed, selected flights `f4` (Alex) and `f1` (Sam).
- Both servers are stopped, ports 8015 and 5185 are free, and the two `tripwright-choose` entries are out of `.claude/launch.json`. The port 8000 server was not touched.
- `npm run build` was not run, so `frontend/dist` and the hosted site still have the fault until the checking chat builds and deploys.
