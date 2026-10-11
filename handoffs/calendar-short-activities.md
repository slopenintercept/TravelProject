# Handoff: short activities on the calendar are cut off and show no time

**Dropped.** At about 06:20 on 2026-10-11, before this file went to anyone, the user said "honestly no need to do it ignore that part". Nothing here was built. It is kept in case they change their mind.

Written 2026-10-11 at about 06:18 Central by the chat that checks the others' work. You make the fix; that chat checks on it every three minutes, and it is the one that builds, commits, pushes and deploys.

## What happens

On "Your days", an activity shorter than about an hour and a half is a thin block with one cut-off line of its name and no time. The user sent a screenshot of their own trip on the hosted site (`trip_119a35c4`, Deep and Shree) at about 06:15:

| On the calendar | What it is |
| --- | --- |
| "Shibuya…" | Shibuya Crossing, 09:00 to 09:45 |
| "Meiji Jingu…" | Meiji Jingu Shrine, 12:52 to 13:52 |
| "Kinkaku-ji…" | Kinkaku-ji (Golden Pavilion), 11:55 to 12:40 |
| "Arashiyama…" | Arashiyama Bamboo Grove, 11:53 to 12:23 |
| "Omoide…" | Omoide Yokocho (Memory Lane), 20:55 to 22:10 |
| "Kyoto →…" | the train from Kyoto to Osaka, 09:00 to 10:15 |
| "Sensō-ji Temple,…" and "Tokyo Skytree" | 90 minutes each: two lines of name, no time |

Six of that trip's eleven activities cannot be read without hovering. Longer ones are fine: "Fushimi Inari Taisha 09:00–11:00", "Osaka Castle and Park 10:15–12:45".

## Is it in the demo too

Yes. It is the same `Calendar` component everywhere, and `DEMO_MODE` changes only the search tools. It shows less on the demo trip because that trip's activities are longer (two all-day parks). On `trip_paydemo` on the hosted site: "Kyoto Tea…" (Kyoto Tea Ceremony, 45 minutes), "Shi…" (Shibuya Crossing, 60 minutes, sharing its column with another block), and five 90-minute activities with two lines of name and no time.

## Why

`frontend/src/components/Calendar.tsx`:

- An hour is 35 px tall and a line of text is 17 px (`HOUR_PX`, `LINE_PX`, lines 5 and 6).
- A block is its length at that scale, less 2 px (line 140). The number of lines that fit is `(height - 12) / 17`, rounded down (line 147).
- The time is shown only when three lines fit and the block has its column to itself (`timed`, line 148).

So an activity gets two lines only from about 83 minutes, and its time only from about 112 minutes. The grid always runs to 24:00 (`MIN_END`, line 8), so most of its height is empty evening.

`frontend/src/styles.css` lines 225 to 229 style the block (`.ev`, `.ev .t`, `.ev small`, `.ev.tight`).

## What the user asked

They sent the screenshot and said: "make sure this problem of how the calendar looks isnt on the demo verison". They did not say how it should look. That the problem is the cut-off names and missing times is my reading of the screenshot; the targets below are mine.

## What it should do afterwards

1. An activity of 45 minutes or more shows its name without being cut to a single word: in practice, two lines of name, or one line that the name fits on.
2. An activity of 60 minutes or more shows its start and end time.
3. A 30-minute activity may stay a single line.
4. The same holds on the demo trip.
5. Nothing that works now is lost: blocks that do not overlap in time do not overlap on screen, two blocks that do overlap still share the column, dragging to another day and clicking a block still work, and the week still fits the board with no sideways scroll at 1280 px and 1440 px wide.

## Suggested change

Yours to choose; these are the levers I can see, cheapest first.

- **Make an hour taller.** At about 60 px an hour, a 60-minute block fits two lines and a 75-minute block fits name and time. On its own that makes the grid about 960 px tall from 08:00 to 24:00.
- **Stop the grid where the trip stops.** Let it end an hour or so after the latest item instead of always at 24:00 (keep a sensible minimum, such as 20:00). On the user's trip that takes out most of what a taller hour adds.
- **Show the time sooner.** A block with room for two lines could give one to the name and one to the time when the name fits on one line.
- Tighter padding in short blocks, if it reads well. Do not shrink the text below the 13 px the calendar already uses.

Keep in mind:

- The user approved this design from a mockup (`design/direction-c-lilac.html`); the colours, radius and type stay as they are. Only the density changes.
- `layout` (line 19) decides which blocks share a column from their times, not their pixels. A minimum height that is taller than the block's real length would cover the block after it, so prefer a taller hour to a taller minimum.
- The pink and green blocks are one traveler's own activity ("Alex only", "Sam only" in the legend). Leave their colours.
- Out of scope: what the scheduler puts on which day, the empty afternoons, and the places that "didn't fit".

## Checks

In the browser, on copies of both trips (see "How to try it"), at 1280 px and at 1440 px wide:

1. On the copy of the user's trip, each row of the table above: say what the block shows now.
2. On the copy of the demo trip: "Kyoto Tea Ceremony", "Shibuya Crossing" and the 90-minute activities.
3. Point 5 above: drag one activity to another day and back, click one to open its card, and look at Mon Jun 21 on the demo trip, where two activities overlap.
4. How tall the calendar is before and after, in pixels, for both trips.
5. `cd frontend && npx tsc --noEmit` passes.

Save a screenshot of each trip's calendar at 1280 px into your scratch folder and give the paths in your Result; the checking chat will show them to the user.

There are no frontend tests in this repo, so the browser is the check.

## How to try it

- **The two trips, as the hosted site returned them at about 06:15** (the whole `GET /api/trips/<id>` answer; the trip is under `state`):
  - `/private/tmp/claude-501/-Users-deep-Documents-Travel-Project/2e765be7-ba15-4b3e-ad27-5a43849b046d/scratchpad/trip_119a35c4.json`
  - `/private/tmp/claude-501/-Users-deep-Documents-Travel-Project/2e765be7-ba15-4b3e-ad27-5a43849b046d/scratchpad/trip_paydemo.json`

  If those are gone, local `trip_99aaaeb1` on port 8000 is the trip `trip_paydemo` was copied from (read-only `GET`).
- **A second backend on a scratch database:** a temporary entry in `.claude/launch.json` named `tripwright-cal`, with `runtimeExecutable: "env"` and args `DATA_DIR=<your scratch folder>/data DATABASE_URL= OBJ_BUCKET= STRIPE_SECRET_KEY= <repo>/backend/.venv/bin/python -m uvicorn tripwright.api:app --app-dir <repo>/backend --port 8017`. Check `/api/health` on that port says `sqlite` and `local disk` first.
- **Seed it:** for each file, change `state.id` (to `trip_cal1`, `trip_cal2`) and write it with `store.save_trip(TripState.model_validate(state))`, run with the same four variables. With `DATABASE_URL` empty, `config.DATABASE_URL` reads `sqlite:///<DATA_DIR>/tripwright.db`: check it names your scratch folder before saving.
- **A dev server for the frontend:** a second temporary entry named `tripwright-cal-frontend`, `env TRIPWRIGHT_BACKEND=http://localhost:8017 npm --prefix <repo>/frontend run dev -- --port 5187 --strictPort`. Open `http://localhost:5187/#trip_cal1/p1` and `#trip_cal2/p1`.
- Both trips are at Review. Dragging an activity to another day re-plans the days (`move_item` in `backend/tripwright/orchestrator.py`); I did not check whether that re-plan asks the model, so keep it to the one drag and back that check 3 needs. **Do not click "Swap", "Apply swaps", "Retry" or "Confirm":** some of those run agents and use the inference quota.
- Remove both entries from `.claude/launch.json` and stop both servers when you are done. Remove only your own entries and never restore that file with git.

## Ground rules

- Read "Start here" and "Gotchas" in `HANDOFF.md` first. The user's global rules apply: minimum code, surgical changes, verify against a concrete check.
- Your files are `frontend/src/components/Calendar.tsx` and the calendar's rules in `frontend/src/styles.css` (lines 217 to 240 or so). Nothing in `backend/`.
- **Do not run `npm run build`.** The checking chat builds.
- **Do not commit, push or deploy.** Do not stop or restart the server on port 8000, and do not open the user's trips on it.
- The user and a friend are using the hosted site right now. Do not touch it. Never print `.env` or `.env.hosted`.

## When you finish

Add a `## Result` section at the end of this file: what you changed and why you chose it, what each of the five checks showed, the two screenshot paths, and anything left undone. Write it last and in one go, after your servers are stopped and your launch entries are removed: the checking chat takes that heading as "ready".
