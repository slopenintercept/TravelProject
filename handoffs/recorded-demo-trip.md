# Handoff: the demo trip replays a recorded run, on any server

Written 2026-10-11 at about 06:45 Central by the chat that checks the others' work. You make the change; that chat checks it, and it is the one that builds, commits, pushes and deploys.

## What it is for

The team presents in a three-minute slot, most likely on the hosted site. A live run takes minutes: a cold group run took four to five minutes, and one measured planning step took 174 seconds. The user asked for a version "where they are really fast and we dont have to wait on the agents".

The repo already holds a recorded run of the demo trip (Japan, 7 days, Alex from Kansas City, Sam from Chicago, Jo from Dallas), from a live run on 2026-10-10. Today it can only be shown by switching the whole server over, and it looks like a failure when it is.

## What happens today

I ran this at 06:30 on a scratch backend with `DEMO_MODE=true` and `OPENAI_API_KEY=` (empty), an empty database and no Stripe, by calling the API:

| Step | Time | What came back |
| --- | --- | --- |
| `POST /api/trips` (Alex, Kansas City, Japan, 7, $2,500) until `busy` is false | 0.2 s | route Tokyo 3, Kyoto 3, Tokyo 1; three date windows; the recorded profile; **0 places to pick from** |
| `POST /dates` with the first window (2027-01-18) | under 0.1 s | `gathering` |
| Sam (Chicago, $3,000) and Jo (Dallas, $2,200) join, then `POST /plan` | 0.1 s | `choosing`: 3 flight options each, 3 stays of 8 rooms, 9 attractions, 5 transport legs, 7 days of weather |
| `PUT /choices` for each of the three | under 0.1 s each | `review`: a full calendar, no conflicts |

So the recordings are complete enough for a whole plan. What is wrong with showing it:

1. **It is a switch for the whole server.** It needs `DEMO_MODE=true` and no inference key, so while it is on no trip on that server can plan live, and changing it on the hosted site takes a deploy.
2. **The picks screen is empty.** Flag: `ideas: pending, "had no inference key (set OPENAI_API_KEY); there is no saved result"`.
3. **Every card carries a pink notice:** "Saved result. Showing saved results: the live run had no inference key (set OPENAI_API_KEY)." The Agents tab says "Saved result" on ten cards and offers "Retry the 6 that didn't finish".
4. **Nothing is ever seen working.** Every agent is done before the screen has drawn.

## Why

- **The switch.** `SpecialistNode._run` (`backend/tripwright/orchestrator.py`, line 162) goes to `_fall_back` when `config.OPENAI_API_KEY` is empty, and `recorded.cached` (`backend/tripwright/recorded.py`, line 61) replays tool results when `config.DEMO_MODE` is true. Both are read once from the environment, for every trip.
- **The notices.** `_fall_back` (line 129) sets `state.flags[name]` to a `fallback` flag and the agent's status to `fallback`. `Review.tsx` line 28 prints the flag, `Agents.tsx` lines 11, 25, 29 and 43 print "Saved result" and count it as unfinished, and `Board.tsx` line 17 puts the dot on the Agents tab.
- **The empty picks.** `fixtures/recorded.json` has nine agent results for this trip (`result:route`, `profile`, `timeframe`, `attractions` and `transport` under `kansas city:japan:7`, `result:lodging:any:japan:7`, and `result:flight` for `kansas city`, `chicago` and `dallas`). There is none for the ideas agent, whose key is `result:ideas:any:japan:7` (`_result_key`, line 74).
- **Tools outside the agents.** Three steps that are not agents call tools directly, so on a server without `DEMO_MODE` they go to the network even if every agent is replayed: `_set_dates` (line 392) searches flights, inside the `POST /dates` request and again in `plan_trip`; the weather step (line 263) geocodes and asks for climate data (the hosted site got a 429 from OpenStreetMap on this today); `draft.locate` (`draft.py`, line 62) geocodes every place on the picks list.
- **The draft's note.** `draft.explain` (`draft.py`, line 140) asks the model for a short note, and `build_draft` only stores the draft after it answers. The model client's timeout is 180 seconds (`llm.py`, line 26).

## What the user approved

After reading this plan in chat, "yes go ahead and write that":

- The fast run belongs to **the demo trip, not the server**: a trip started with "Use the demo trip" gets the recorded run; every other trip still plans live with the real agents. It has to work on the hosted site with nothing to switch.
- **A saved picks list** for the demo trip.
- **One small "Recorded run" label** instead of the pink notices.
- **Each agent shows as working for a few seconds** before its result appears.

They did not decide, and these are mine: the number of seconds for each agent, where the label sits, the wording on the agents' cards, leaving out the draft's note, and that the demo trip ignores the saved profile. If one of them turns out wrong, say so in your Result rather than widening the change.

The label stays. The point of it is that nobody watching is told a replay is live.

## Suggested change

The smallest version I can see. The checks are what matter; if you find something simpler that passes them, use it.

The rule in one line: **a recorded trip behaves the way the whole server does today with `DEMO_MODE=true` and no inference key (which I ran end to end, above), but only for that trip, and it says "recorded" instead of "saved result".**

1. **Mark the trip.** `recorded: bool = False` on `TripRequest` (`models.py`, line 43; `frontend/src/types.ts`, line 49). `Start.tsx` sends `true` only when "Use the demo trip" was pressed and the origin, destination and days still match `DEMO` at submit. The name and budget may be changed.
2. **Tools replay for that trip.** One way: a `ContextVar` in `recorded.py` that `cached` reads next to `config.DEMO_MODE`, set from `state.request.recorded` in `_trip` and `create_trip` (`api.py`, lines 93 and 199) before either starts background work. Each request is its own task, and tasks started from it copy the value.
3. **Agents replay for that trip.** At the top of `_run`, before the `reuse` check: if the trip is recorded and `recorded.saved(key)` has a result, show the agent as `working`, wait, then store that result the way `_fall_back` does (same re-dating, same `after_fallback`), clear the flag, and end as `accepted`. Wording, mine: "Replaying the recorded run" while it waits and "Recorded result" when done. Do not pass through `under_review`: nothing is being reviewed.
4. **Seconds, mine:** route 1, profile 2, ideas 3, timeframe 5, flight 4, transport 6, lodging 7, attractions 9. Constants, not settings.
5. **The label.** A chip reading "Recorded run" in the top bar next to the destination, dates and travelers chips (`App.tsx`, lines 101 to 105), shown when `state.request.recorded`.
6. **The draft's note.** On a recorded trip `explain` returns "" as it does with no key, so the draft appears without waiting on the model.
7. **The saved profile.** A recorded trip does not read the saved stated preferences in `new_trip` (line 364) and `plan_timeframe` (line 379) does not save its profile. Otherwise a last host who switched to Airbnb gives the demo trip `lodging_override = "airbnb"` over recorded hotel rooms, and the demo trip wipes the saved preferences.
8. **Record the picks list and its locations** (next section).
9. **Docs:** `DEMO.md` and `README.md` lines 211 to 215, only where this change makes them untrue (see check 10).

How the obvious version goes wrong:

- **The database wins over the recording.** `_fall_back` reads `store.cache_get` before `recorded.saved`, and the ideas agent's `reuse` check (line 152) reads the database first too. The hosted database holds results from other people's Japan trips. A recorded trip must take `fixtures/recorded.json` only.
- **Replaying tools on a trip that is not the demo trip.** If the flag is sent after someone pressed the button and then changed the destination to Italy, no agent has a recording, so they all run live, with tools answering from Tokyo and Kyoto recordings. That is why the flag depends on the three fields.
- **The value not reaching the work.** `_trip` starts `schedule_choices` and `_redraft` itself (lines 101 and 103): set the value before them. The weather step runs inside the Strands graph; check that the value reaches it (check 2 does).
- **An agent with no recording.** A traveler from any city but Kansas City, Chicago or Dallas has no recorded flights. Let that agent run as it does today. Do not add a second fallback.
- **A new status name.** `accepted` with the label on the trip is enough and touches nothing else. A `recorded` status would need `models.py` line 335, `types.ts` line 305 and three tables in `Agents.tsx`.

## The picks list to record

`data/tripwright.db` on this Mac has the list the Ideas agent produced for this exact trip on 2026-10-10 at about 23:59, in its `cache` table under the key `result:ideas:kansas city:japan:7`. That is the key's old shape; today's code looks for `result:ideas:any:japan:7`. I loaded it with `SPECS["ideas"].load` at 06:40: 24 places, each with a source, none with coordinates (Tokyo 13, Kyoto 8, Hakone, Kamakura, Nikko). Local trip `trip_faf39eb6` holds the same 24.

Open that database **read-only** (`sqlite3.connect("file:data/tripwright.db?mode=ro", uri=True)`) and never write to it.

1. **Record the list** as `result:ideas:any:japan:7` with `recorded.record`, so the file keeps its formatting. `git diff --stat` on `recorded.json` should show additions only.
2. **Its 24 `source.evidence_url` values point at the project's storage bucket.** The repo is public and no other entry in `recorded.json` names that host (`grep -c linodeobjects.com` gives 0 now, and must after). All 586 evidence links in the file now read `/evidence/20261010/<file>`, served from `backend/tripwright/fixtures/evidence/` (`api.py`, line 452). Do the same: a plain GET of each of those 24 public files into `fixtures/evidence/20261010/` and the path rewritten. If a file cannot be fetched, set that `evidence_url` to null and list it in your Result. Nothing else on the hosted side.
3. **Record the locations the draft looks up for this list.** `draft.locate` asks `places.geocode` for `"<name>, <city>"`, then `"<city>, Japan"`, and for each route city `"<city>, Japan"`. With replay on, a lookup that is not recorded gives no coordinates, so the place gets no pin on the draft's map (`DraftPlan.tsx`, line 30). `recorded.json` has 8 of the 24 by name now and neither `geocode:tokyo, japan` nor `geocode:kyoto, japan`; the local database has 18 of the 24 and both cities. One way: on a scratch `DATA_DIR` whose cache you first filled with the local database's `geocode:` rows, run `draft.locate` once with `RECORD_FIXTURES=true` for a trip state holding this list and the recorded route. `cached` records cache hits as well as fresh lookups. The few that are missing go to OpenStreetMap; if it answers 429, wait and run again.

The names on this list are not quite the demo script's: it has "teamLab Planets TOKYO" and "Golden Gai", where `DEMO.md` says "teamLab Planets" and "Shinjuku Golden Gai".

## Checks

Checks 1 to 3 are tests in a new file, for example `backend/tests/test_recorded_trip.py`. Each should fail before your change and pass after. The delays should be patched to zero in tests.

1. **A recorded trip runs from start to review on recordings alone, with a key set.** With `config.OPENAI_API_KEY` set to any string and `DEMO_MODE` false: create the demo trip with `recorded=True`, set the first window's dates, add Sam (Chicago) and Jo (Dallas), plan, confirm all three. It reaches `review` with 24 ideas, three flight options for each traveler, three stays, 9 attractions, 5 legs and 7 days of weather; `state.flags` is empty; every research agent's status is `accepted`.
2. **Nothing left the process.** In the same run, `make_model` and whatever the tools use to reach the network are replaced by something that raises, and nothing raises.
3. **An ordinary trip is untouched.** The same request with `recorded=False` does not take the recorded path (its agents call the model), and after a recorded trip has run, a tool call made for an ordinary trip does not replay.
4. **The whole suite:** `cd backend && .venv/bin/python -m pytest -q` gives 128 passed now. `cd frontend && npx tsc --noEmit` passes.

Then in the browser, on the scratch setup below, 1360 px wide. Use a stopwatch and put the seconds in your Result.

5. **Start.** Press "Use the demo trip", then "Start planning". "Recorded run" is in the top bar. The agents show as working, then the picks list appears with 24 places within about 5 seconds, and all four first agents are done within about 7. No pink notice anywhere and no dot on the Agents tab.
6. **Picks, dates, travelers.** As Alex mark Tokyo Disneyland and Fushimi Inari Taisha "Must do" and teamLab Planets TOKYO "Interested", and save. "Choose these dates" on the first window answers in under a second. Sam (Chicago, $3,000) joins and marks Ghibli Museum "Must do"; Jo (Dallas, $2,200) joins, marks Fushimi Inari Taisha "Must do" and Golden Gai "No". Another traveler's part can be sent with `curl` and an `X-Traveler` header. About 11 seconds after the last save the draft plan fills in, with pins on its map. Say how many of the 24 places have a pin.
7. **Planning.** "Everyone's in: plan the trip": the Agents tab shows the agents running in parallel, Alex's Choose screen appears within about 9 seconds, and everything is done within about 11. Each card reads "Accepted"; with "Show details", "Recorded result". No "Retry" button.
8. **Review.** Confirm for all three. Review appears in about a second. Alex's flight, stays, transport and "Things to do" cards have no pink notice. For each of the four marked places, say whether it is on the days of whoever marked it or offered under "Needs you" (in my run with no picks, Tokyo Disneyland was left off as "Days in Tokyo are already full").
9. **An ordinary trip on the same server.** Type a trip by hand (not the button). No label. Its agents try to run live; on the scratch setup they cannot reach a model and end as "Didn't finish", which is expected there. Then press "Use the demo trip", change the destination to Italy and start: no label, and `GET /api/trips/<id>` shows `"recorded": false`.
10. **Docs.** `DEMO.md`: "Before you go on stage" steps 2 and 3 say what is now true; the script uses the list's own names; it says Sam and Jo must type Chicago and Dallas, and what happens if they do not. `README.md` lines 211 to 215 no longer say the picks screen starts empty. Change nothing else in either.

## How to try it

- **A second backend on a scratch database.** A temporary entry in `.claude/launch.json` named `tripwright-recorded`: `runtimeExecutable` `env`, args `DATA_DIR=<your scratch folder>/data`, `DATABASE_URL=`, `OBJ_BUCKET=`, `STRIPE_SECRET_KEY=`, `DEMO_MODE=`, `RECORD_FIXTURES=`, `OPENAI_API_KEY=not-a-real-key`, `OPENAI_BASE_URL=http://127.0.0.1:9`, then `<repo>/backend/.venv/bin/python -m uvicorn tripwright.api:app --app-dir <repo>/backend --port 8021`. Start it with `preview_start`.
- **Why those values.** The hosted site has a key and no `DEMO_MODE`, and this copies that: `/api/health` should say `"key": true`, `"demo_mode": false`, `sqlite`, `local disk` and `holds kept in the app`. The key is fake and the address answers nothing, so no inference quota can be used and a model call fails at once instead of quietly working.
- **The frontend from source.** A second temporary entry, `tripwright-recorded-ui`: `env TRIPWRIGHT_BACKEND=http://localhost:8021 npm --prefix <repo>/frontend run dev -- --port 5191 --strictPort`. Do not run `npm run build`: `frontend/dist` is what port 8000 serves.
- The server does not reload on code changes. Restart yours after each backend edit.
- The recording step in "The picks list to record" is a one-off script with its own scratch `DATA_DIR`. It is the only thing here that needs the real network.
- Do not press "Switch to Airbnb", "Add a rental car", "More like my picks" or "Retry" on the demo trip as part of the checks. They are off the script. If you know what one of them does on a recorded trip, say so in your Result.
- When you are done, stop both servers and remove both entries. Remove only your own entries and never restore that file with git.

## Ground rules

- Read "Start here" and "Gotchas" in `HANDOFF.md` first. The user's global rules apply: minimum code, surgical changes, verify against a concrete check. This is a hackathon demo: no multi-user or hardening work.
- **Your files:** `backend/tripwright/models.py` (`TripRequest`), `recorded.py`, `orchestrator.py`, `api.py`, `draft.py` (`explain`), `fixtures/recorded.json` and new files under `fixtures/evidence/20261010/`, one new test file; `frontend/src/types.ts`, `components/Start.tsx`, `App.tsx`; `DEMO.md` and `README.md` as in check 10. If you need another file, say why in your Result.
- Nobody else is working in the folder as of 06:45. Run `git status` first all the same, and never stash or revert a file that is not yours.
- **Do not stop or restart the server on port 8000,** and do not open the user's trips on it. `data/tripwright.db` is read-only for you.
- **Do not build, commit, push or deploy,** and do not touch the hosted site beyond the 24 file downloads above.
- Never print `.env` or `.env.hosted`, and do not put the hosted address or the bucket's host in any file.
- Use `date +%H:%M` for every time you write down.

## When you finish

Add a `## Result` section at the end of this file: the files you changed, what each of the ten checks showed (with the seconds you measured), which of my choices you changed and why, and anything left undone or noticed. Write it last and in one go, after your servers are stopped and your launch entries are removed: the checking chat takes that heading as "ready".
