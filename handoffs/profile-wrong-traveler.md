# Handoff: the Profile agent describes the last trip's host

Written 2026-10-11 at about 06:03 Central by the chat that checks the others' work. You make the fix; that chat checks on it, and it is the one that commits, pushes, restarts the local server and deploys.

## What happened

At 05:51 the user started a trip on the hosted site as **Deep**, from **Kansas**, to Japan, 7 days, $3,000 (`trip_13d3fa4f`). The Profile agent was accepted first time, and its card on the Agents tab reads:

> Alex is a solo traveler from Kansas City planning a 7-day balanced-pace trip to Japan on a $3,000 budget, with no specific sights or preferences stated yet.

Nobody on that trip is called Alex. The four trips on the hosted site, in the order they were made:

| Trip | Entered on Start | The profile's summary |
| --- | --- | --- |
| `trip_7e281cec` | Alex, Kansas City, $2,500 | "Alex is a solo traveler from Kansas City ... $2,500 budget, with no specific must-see or preferred sights." |
| `trip_185cdd46` | Alex, Kansas City, $2,500 | "Alex is a solo traveler from Kansas City ... $2,500 budget, with no specific sights or preferences stated yet." |
| `trip_f24799b6` | alex, Kansas, $3,000 | "Alex is a solo traveler from Kansas City ... $3,000 budget, with no specific sights or preferences stated yet." |
| `trip_13d3fa4f` | Deep, Kansas, $3,000 | The same sentence, word for word. |

The order of the middle two is my reading of the summaries, not something I checked against the clock. `home` on each profile is right ("Kansas" on the last two): only the sentence is wrong.

## Why

There is one saved profile for the whole app, and its sentence is handed to the next trip's agents as if it described the new host.

1. `store.save_profile` and `load_profile` (`backend/tripwright/store.py`, lines 50 to 57) read and write a single row, `"default"`.
2. `new_trip` (`backend/tripwright/orchestrator.py`, line 363) starts every trip with `profile=store.load_profile()`: the whole profile the last trip left, summary included.
3. `brief` (`backend/tripwright/specialists.py`, lines 70 to 72) adds `Host: {state.profile.summary} Stated preferences: ...` to what every agent is told.
4. The Profile agent's task is that brief plus "Build the host's traveler profile from the request." (`SPECS`, line 863). So it reads "- Deep: flying from Kansas, budget $3,000 ..." and, two lines later, "Host: Alex is a solo traveler from Kansas City ...", and hands the second one back.
5. `plan_timeframe` (line 375) saves the result as the new `"default"`, so the next trip starts from it again.

This is not the reuse of an earlier trip's result: only the ideas agent has `reuse=True`, and the Profile agent's status was "Accepted by the orchestrator".

What is meant to carry over is `stated_preferences` ("Learned from review-screen overrides; carried into future trips", `models.py` line 57). `new_trip` reads them for Airbnb and the rental car, and `_learn` (line 575) writes them. The summary, the interests and the home are about one trip.

It reaches further than the card. Until the Profile agent has finished, the route, timeframe and ideas agents get the stale `Host:` line too, and on this trip every later agent got it for good, next to the real traveler's line.

## What the user approved

Fixing it.

## Suggested change

The smallest version I can see. The checks below are what matter; if you find something simpler that passes them, use it.

1. **`new_trip`:** carry over only the stated preferences, not the rest of the saved profile. The Airbnb and rental car lines just below it must keep working.
2. **`brief`:** say `Host: <summary>` only when there is a summary. A new trip now has none until its own Profile agent has answered, and "Host:  Stated preferences: none yet." would be noise. Keep telling the agents the stated preferences when there are any.

Keep in mind:

- `build_profile` (line 132) already takes `home` and `pace` from the request and keeps the known `stated_preferences`. It should not need to change.
- If the Profile agent fails, the trip keeps a profile with no summary. Nothing should print an empty one.
- Out of scope, and not asked: that there is one `"default"` profile for everybody. On the hosted site, which has no login, a preference one visitor states ("Prefers Airbnb over hotels") is applied to the next stranger's trip. That is a product decision for the user; say nothing in code about it.
- Out of scope: repairing `trip_13d3fa4f` or any other trip already saved with the wrong sentence.

## Checks

1. **A new test** (for example `backend/tests/test_profile.py`): with a saved profile whose summary names another traveler and whose stated preferences include "Prefers Airbnb over hotels", `new_trip` for a different host gives a trip whose `brief` does not contain that summary or that name, still contains the stated preference, and has `lodging_override == "airbnb"`. It should fail before your change and pass after.
2. **The whole suite:** `cd backend && .venv/bin/python -m pytest -q`. It gives 126 passed now.
3. **One live run of the Profile agent,** because the test cannot show what the model writes. On a scratch backend (below) whose saved profile is the Alex sentence from the table, start a trip as Deep from Kansas to Japan, 7 days, $3,000, and read the Profile agent's summary once it is accepted. It should describe Deep, or at least not Alex from Kansas City. Run it once; it uses a little of the inference quota.

## How to try it

- **A second backend on a scratch database:** a temporary entry in `.claude/launch.json` named `tripwright-profile`, with `runtimeExecutable: "env"` and args `DATA_DIR=<your scratch folder>/data DATABASE_URL= OBJ_BUCKET= STRIPE_SECRET_KEY= DEMO_MODE=true <repo>/backend/.venv/bin/python -m uvicorn tripwright.api:app --app-dir <repo>/backend --port 8016`. `DEMO_MODE=true` replays the recorded searches, so the timeframe and ideas agents cost almost nothing; the model is still the real one. Check `/api/health` on that port says `sqlite` and `local disk` first.
- **Seed the saved profile** before starting the server's trip: `store.save_profile(TravelerProfile(home="Kansas City", summary="Alex is a solo traveler from Kansas City planning a 7-day balanced-pace trip to Japan on a $3,000 budget, with no specific sights or preferences stated yet."))`, run with the same variables. With `DATABASE_URL` empty, `config.DATABASE_URL` reads `sqlite:///<DATA_DIR>/tripwright.db`: check it names your scratch folder before saving.
- **Start the trip** from the Start screen at `http://localhost:8016`, or with `POST /api/trips`. The Profile agent has no tools and answers in a few seconds; you do not have to wait for the timeframe agent.
- The server does not reload on code changes: start it after your edit.
- Remove the entry from `.claude/launch.json` and stop the server when you are done. Remove only your own entry and never restore that file with git.

## Demo mode

Added at about 06:10, after this file was handed over: the user asked that every fix also holds in demo mode, where the problem exists there.

- **`DEMO_MODE=true` changes the tools only** (`backend/tripwright/recorded.py`): they replay recorded results. The agents still ask the real model, through the same `new_trip` and `brief`. So the fault is in demo mode too and the same fix covers it. Check 3 already runs with `DEMO_MODE=true`; say so in your Result.
- **One path only the safety net uses.** With no inference key, or after three failed attempts, the Profile agent does not run: `_fall_back` (`orchestrator.py`, line 128) shows the last accepted profile for the same origin, destination and days, from the database first and then from `backend/tripwright/fixtures/recorded.json`. The recorded one ("A budget-conscious first-time visitor from Kansas City ...") names nobody. One saved in the database by an earlier trip can name that trip's host. It is shown as a saved result, and the demo script's host is the one the recording was made for, so **leave the fallback as it is**.
- **Check 4, no code, if you see this in time:** on the scratch backend, restarted with `OPENAI_API_KEY=` added to its variables, start a trip as Sam from Kansas City to Japan for 7 days and report what the Profile agent's card says and how it is marked. This uses no inference. If you had already finished, the checking chat runs it.

## Ground rules

- Read "Start here" and "Gotchas" in `HANDOFF.md` first. The user's global rules apply: minimum code, surgical changes, verify against a concrete check.
- Your files are `backend/tripwright/orchestrator.py` (`new_trip` only), `backend/tripwright/specialists.py` (`brief` only) and one new test file. Nothing in `frontend/`.
- **Do not stop or restart the server on port 8000,** and do not open the user's trips on it. It keeps running the old code until the checking chat restarts it.
- **Do not commit, push or deploy.** The user and a friend are trying the hosted site right now, and a deploy restarts it. Do not touch the hosted site at all.
- Never print `.env` or `.env.hosted`.

## When you finish

Add a `## Result` section at the end of this file: the files you changed, what you ran and what it showed for each of the three checks (quote the summary the live run produced), and anything left undone. Write it last and in one go, after your server is stopped and your launch entry is removed: the checking chat takes that heading as "ready".

## Result

Written 2026-10-11 by the chat that made the fix. Nothing is committed, pushed or deployed. The scratch server on port 8016 is stopped and the `tripwright-profile` entry is gone from `.claude/launch.json`.

**Files changed**

- `backend/tripwright/orchestrator.py`, `new_trip` only (plus `TravelerProfile` added to the import): a new trip starts with `TravelerProfile(stated_preferences=<the saved ones>)` instead of the whole saved profile. The Airbnb and rental car lines read the same list as before.
- `backend/tripwright/specialists.py`, `brief` only: the `Host:` line is added only when the profile has a summary or stated preferences, and an empty summary is left out of it. With both it reads exactly as before.
- `backend/tests/test_profile.py`, new, two tests.

**Check 1, the new test.** Both tests failed before the change (the brief held "Host: Alex is a solo traveler from Kansas City ...") and pass after. They cover: no "Alex" and no "Kansas City" in the new host's brief, the stated preference still in it, `lodging_override == "airbnb"`, and no `Host:` line at all when nothing is known yet.

**Check 2, the whole suite.** `cd backend && .venv/bin/python -m pytest -q`: 128 passed (126 plus the two new ones).

**Check 3, one live run, with `DEMO_MODE=true`.** Scratch backend on 8016 (`/api/health`: `sqlite`, `local disk`, `demo_mode: true`, inference key present), saved profile seeded with the Alex sentence from the table. `POST /api/trips` as Deep, Kansas, Japan, 7 days, $3,000 gave `trip_87ab3340`. The Profile agent was "Accepted by the orchestrator" on attempt 1 and wrote:

> A solo traveler from Kansas planning a 7-day balanced-pace Japan trip on a $3,000 budget, visiting Tokyo, Kyoto, and Osaka.

No Alex and no Kansas City; `home` is "Kansas". It does not use the name Deep. Run once. Demo mode replays the tools only, so this is the same `new_trip` and `brief` as a normal run and the one fix covers both.

**Check 4, no inference key.** Same scratch backend restarted with `OPENAI_API_KEY=` (`/api/health`: `"key": false`). `POST /api/trips` as Sam, Kansas City, Japan, 7 days, $2,500 (the handoff gave no budget; I used the demo's) gave `trip_8817d12a`. The Profile agent's card:

- status `fallback`, attempt 0, message "Using saved results: had no inference key (set OPENAI_API_KEY)"
- found: "A budget-conscious first-time visitor from Kansas City planning a 7-day, balanced-pace Japan trip focused on Tokyo Disneyland and Kyoto within a $2,500 total budget."
- flag: "Showing saved results: the live run had no inference key (set OPENAI_API_KEY)."

That is the recorded profile from `fixtures/recorded.json`; it names nobody. Route and timeframe were `fallback` too, ideas `pending` (no saved result). The fallback was left as it is.

**Left undone, and noticed**

- Not changed, as told: the single `"default"` profile, the fallback, and trips already saved with the wrong sentence.
- A side effect of always giving a new trip a profile: if the Profile agent fails with no saved result, `plan_timeframe` now saves a profile with no summary as `"default"` (stated preferences kept). Before, with nothing saved, it saved nothing. Nothing prints the empty summary: `brief` skips it.
- Noticed, not touched, and not new: when the Profile agent falls back, the saved result replaces the trip's whole profile, stated preferences included, and `plan_timeframe` then saves that as `"default"`. So a fallback run can drop "Prefers Airbnb over hotels" for later trips. In check 4 there were none to lose.
- The server on port 8000 was not touched and still runs the old code.
