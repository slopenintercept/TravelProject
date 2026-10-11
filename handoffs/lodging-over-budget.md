# Handoff: lodging when no room fits the budget

Written 2026-10-11 at about 05:00 Central by the chat that diagnosed this. You implement the fix; that chat only checks on it.

## What happened

On the user's local trip `trip_479d20ea` (two travelers, $3,000 each, Dec 11 to Dec 31, route Tokyo 16 nights, Kyoto 2, Tokyo 1) the Lodging agent ended as `pending`: "timed out after 240s; there is no saved result". Neither traveler has stays. The user suspected a server restart. It was not: the server started at 04:17:33, planning began at 04:20:23, and the agent ran into its own time limit at 04:24:23.

From the running server's event log for that trip:

| Time | What the agent did |
| --- | --- |
| 04:20:23 | Started. Three web searches, then one hotel search per stay with `max_nightly_usd: 44`. |
| 04:21:07 | "Kyoto Nakagyo and the second Tokyo stay came up empty." It began trying other neighbourhoods. |
| 04:21 to 04:23 | 19 hotel searches for the single night of Dec 30 across 14 Tokyo neighbourhoods, 6 for Kyoto. |
| 04:24:00 | Answered after 217 seconds, with a hotel found by searching Kokubunji for the last night. |
| 04:24:00 | Sent back: "stay 3 (Tokyo, 2026-12-30 to 2026-12-31): Fuchu Urban Hotel Annex is too far from central Tokyo". |
| 04:24:23 | Out of time 23 seconds into the second attempt. |

The budget split leaves each traveler about $44 a night for a room over 19 nights. The pages the agent fetched for the night of Dec 30 are still in the `cache` table of `data/tripwright.db` (keys like `hotels:asakusa tokyo:2026-12-30:2026-12-31:1`, kept for 6 hours from about 04:21). The cheapest room on each:

Shinjuku $57, Shibuya $69, Asakusa $75, Kuramae $75, Yanaka $79, Harajuku $80, Nihonbashi $84, Kanda $85, Oshiage $85, Akihabara $97, Ueno $97, Ginza $121. Kokubunji, the suburb that was rejected, $33.

So no central room at $44 existed that night, and the agent had no way to learn that or to settle for the cheapest one.

## Why the code cannot finish

1. **The search hides everything over the cap.** `_finish` in `backend/tripwright/tools/lodging.py` (line 127) drops every option above `max_nightly`, and `Toolbox._rooms` in `backend/tripwright/toolbox.py` (line 137) then answers "Nothing found under that price." Each of those pages held 6 to 18 rooms. The cap is applied after the page is fetched and cached, so the cheaper-but-over rooms are already in hand.
2. **The review refuses an over-budget stay.** `build_lodging` in `backend/tripwright/specialists.py` (around line 437) rejects a stay whose cheapest option is more than 15% over the tightest traveler's nightly cap: "nothing fits ...; search again with a lower max_nightly_usd". When no such room exists, nothing the agent does can pass.
3. **The prompt demands the impossible and does not bound the hunt.** `lodging_task` (same file, line 484) says "Every stay needs at least one option at or under $X a night", and nothing limits how many neighbourhoods the agent tries. The 240 seconds cover every attempt together (`SpecialistNode.invoke_async`, `backend/tripwright/orchestrator.py` lines 100 to 104).

What already works: `assign_rooms` (`specialists.py`, line 457) gives a traveler the cheapest option when none fits and writes "Cheapest option found at $X a night; that is over NAME's lodging budget of about $Y a night." The budget step and `validate_itinerary` then show that traveler as over budget. The plan can carry an over-budget room honestly; it just never gets that far.

## What the user approved

Let the lodging agent accept the cheapest central room and flag it over budget.

## Suggested change

The smallest version I can see. The tests below are what matter; if you find something simpler that passes them, use it.

1. **`_finish` in `tools/lodging.py`:** when nothing is at or under the cap, return the cheapest few (three is enough) instead of none. When some are under the cap, keep returning only those, and make sure the cheapest of them is among the ones kept (today the list is cut to `MAX_OPTIONS` by rating, which can drop it). `_finish` also serves `search_airbnb`.
2. **`Toolbox._rooms` in `toolbox.py`:** when the rooms returned are over the cap, say so in the first line, for example "Nothing at or under $44 a night in Asakusa. The cheapest found:". The agent must be able to tell.
3. **`build_lodging`:** stop rejecting a stay only because its cheapest option is over the tightest budget. After step 1 every search result already holds the cheapest room its page had, so if that is over, there was nothing cheaper in that neighbourhood to find. Keep every other check, including the distance check.
4. **`lodging_task`:** replace the "Every stay needs at least one option at or under ..." sentence. Tell the agent that a search with nothing in budget lists the cheapest rooms instead, that it should then take the cheapest one in a central neighbourhood, and that it should try at most two neighbourhoods per stay.

Things to keep in mind:

- The user's rule: nobody else's budget may influence a traveler's hotel. Rooms are still assigned per traveler in `assign_rooms`; do not change that.
- Prices and facts never come from the model. The agent answers with option ids and the code joins them back (`ctx.rooms`).
- A room's `lat`/`lon` is the geocode of the neighbourhood that was searched (`toolbox.py`, line 153), so the distance check (`MAX_KM_FROM_CENTER = 20`) measures the neighbourhood, not the hotel.
- Out of scope: the 240-second limit, the scheduler, the budget optimizer, the UI.

## Ground rules

- Read "Start here" and "Gotchas" in `HANDOFF.md` first. The user's global rules apply: minimum code, surgical changes, verify against a concrete check.
- Several chats share this working folder. Uncommitted work that is not yours is in it: a payments chat's (`backend/tripwright/api.py`, `config.py`, `models.py`, `payments.py`, `backend/pyproject.toml`, `backend/tests/conftest.py`, `backend/tests/test_payments.py`, several frontend files) and deploy/docs changes. Another agent is fixing the ideas agent in `backend/tripwright/orchestrator.py` at the same time. Your files are `tools/lodging.py`, `toolbox.py`, `specialists.py` and a new test file. Make small targeted edits and leave everything else alone.
- Do not commit, push or deploy. The user decides that.
- Do not restart or stop the server on port 8000; it is the user's. Never print `.env` or `.env.hosted`.

## How to check it

1. **Baseline first:** `cd backend && .venv/bin/python -m pytest -q` (about 5 seconds). Note what fails before you touch anything; the payments chat's tests may fail for reasons that are not yours.
2. **New tests, written before the change and failing without it,** in a new file `backend/tests/test_lodging_budget.py`:
   - `_finish` with every option above the cap returns the cheapest ones, not an empty list;
   - `_finish` with some options under the cap returns only those, the cheapest of them included;
   - `build_lodging` accepts a stay whose cheapest option is over the tightest traveler's cap, and `assign_rooms` then gives that traveler the cheapest room with the "that is over ... lodging budget" sentence;
   - `build_lodging` still rejects a room that is too far from the centre.
3. **The whole suite passes** apart from anything that failed in the baseline. `test_each_traveler_gets_a_room_that_fits_their_own_budget` in `backend/tests/test_group.py` (line 439) is the nearest existing test.
4. **Against the real pages,** until about 10:20 on 2026-10-11 while they are cached: open `data/tripwright.db` read-only (`sqlite3 'file:data/tripwright.db?mode=ro'`) or copy it to your scratch folder, run the saved Asakusa page for `2026-12-30` through `_finish` with a cap of 44, and confirm it returns the $75 room marked as over the cap.
5. **End to end, only if time allows** (about 4 minutes and some of the user's inference quota): a second backend on port **8012** with `DATA_DIR=<your scratch folder>` holding a copy of `data/tripwright.db`, `/api/health` saying `sqlite`; copy `trip_479d20ea` under a new id (`store.load_trip`, change `state.id`, save); open it as a traveler and press "Retry the one that didn't finish" on the Agents tab. Lodging should be accepted, with the last stay shown as over budget.

Then replace the "The Lodging agent timed out ..." bullet under "Not done or not verified" in `HANDOFF.md` with what is true now.

## When you finish

Add a section `## Result` at the bottom of this file: the files you changed, what you ran and what it showed, and anything left undone. Do the same if you stop early. Another chat reads this file every few minutes to see whether the work is done.

## Result

Done on 2026-10-11 at about 05:40 Central. Nothing is committed, pushed or deployed, and the server on port 8000 was not touched.

Files changed:

- `backend/tripwright/tools/lodging.py`: `_finish` always keeps the cheapest room under the cap, and returns the three cheapest rooms when nothing is under it.
- `backend/tripwright/toolbox.py`: `_rooms` takes the cap and the place, and starts with "Nothing at or under $44 a night in Asakusa. The cheapest found:" when the rooms are over the cap. Both search tools pass them in.
- `backend/tripwright/specialists.py`: `build_lodging` no longer rejects a stay for being over the tightest budget (every other check is unchanged). `lodging_task` drops the "Every stay needs at least one option at or under ..." sentence and tells the agent to take the cheapest central room when a search says nothing is in budget, and to search at most two neighbourhoods per stay.
- `backend/tests/test_lodging_budget.py`: new, five tests.
- `HANDOFF.md`: the "Lodging agent timed out" bullet and the matching line under "Start here".

What was run:

1. Baseline: 119 passed.
2. The new tests before the change: 4 failed, 1 passed (the "too far from the centre" test, which checks behaviour that was to stay).
3. The whole suite after the change: 126 passed. That is the 119, my 5, and 2 in `tests/test_conversation.py` from the chat fixing the ideas agent (those 2 failed in one run midway, before that chat's fix landed).
4. The saved Asakusa page for 2026-12-30 (16 rooms, cheapest $75) through `_finish` with a cap of 44: it returns the rooms at $75, $79 and $92, and `_rooms` prints "Nothing at or under $44 a night in Asakusa. The cheapest found:" above them.
5. End to end on port 8012 with a copy of the database in my scratch folder, trip copied as `trip_lodgingfix`, "Retry the one that didn't finish" pressed on the Agents tab as Alex: Lodging was accepted on attempt 1, and the trip stopped being busy about 80 seconds after the press. Both travelers got Guest House Tokyo Samurai in Asakusa at $41 a night for Dec 12 to 28 (within budget), Hotel M's Est Kyoto Station South at $54 for Dec 28 to 30, and BOOK AND BED TOKYO Shinjuku at $57 for Dec 30 to 31. The last two cards read "Cheapest option found at $54 (or $57) a night; that is over Alex's lodging budget of about $44 a night." The server is stopped and its preview entry is removed from `.claude/launch.json` again.

Left undone:

- The user's real trip `trip_479d20ea` is unchanged; its Lodging agent is still `pending`. The server on port 8000 runs the old code until it is restarted, so a retry there will fail the same way until then.
- One end-to-end run only. The agent kept to the limit of two neighbourhoods that time; nothing in the code enforces it, and the 240-second limit is as it was.
- When a page has no rooms at all, the search still answers "Nothing found under that price." I left that wording alone.
