# Interest picks: agents suggest places, each traveler marks them

Date: 2026-10-10. Status: approved in conversation, pending review of this written spec.

## Goal

Today the new-trip form and the join form ask each person to type what they need and want to see. Replace that with a step where agents research the destination and show options, each person marks what they are and aren't interested in, and those marks drive the per-person and group plans the agents then build.

Success looks like:

- Neither form has "need to see" or "want to see" boxes.
- After submitting the form, the host sees a list of 15-25 real places for the destination and marks each one **Must do**, **Interested** or **Not for me** (or leaves it unmarked).
- People who join through the invite link mark the same list, with no wait.
- Planning uses the marks: must-dos are scheduled for the people who marked them, interested places are scheduled where they fit, nobody is scheduled for a place they marked "not for me", and nobody pays for a ticket they skip.

## Decisions (from the conversation)

| Question | Decision |
| --- | --- |
| What are the options? | Specific places and experiences, not themes. Each is marked must do / interested / not for me. |
| One list or one per person? | One shared list, researched once when the host creates the trip. Anyone can add a place that is not on it. |
| "Not for me" when someone else marked it must do | The skipper skips it: that block is free time for them, or one of their own picks if one fits, and they regroup after. They do not pay for that ticket. |
| Unmarked places | Neutral. Not scheduled because of anyone; agents may still add well-known extras by pace, never one somebody marked "not for me". |
| Joiners | Same step, same list, after the join form. |
| Changing picks | Allowed until the host starts planning. After that the review screen's Remove/Restore controls apply. |
| How it is built | Approach A: a new lightweight **ideas** agent produces the list; the planning-stage agents keep working from `need`/`want`, plus a new `skip`. |

Approaches not taken: researching every option in full up front (slow first screen, large rewrite of the attractions agent), and reusing the attractions agent early (it is built to fill a schedule, not to give a broad menu).

## Flow

**Host**

1. New-trip form: name, origin, destination, days, optional start date, budget, pace.
2. Stage 1 starts at once: `route` (cities from the destination alone), then `profile`, `timeframe` and the new `ideas` agent in parallel.
3. "What sounds good?" screen: the ideas list, grouped by category. Each place shows name, city, a one-line why, three mark buttons, and other travelers' marks ("Sam: must do"). An "Add a place" box adds a place to the shared list. While the ideas agent is still working the screen says "Agents are finding places…".
4. After saving picks, the date options (the timeframe agent has been running in the background).
5. "Who's coming?", then the host starts planning, as now.

**Joiner**

1. Join form: name, origin, budget.
2. The same "What sounds good?" screen on the already-researched list, then "Who's coming?".

**Both:** an "Edit my picks" link in the header until planning starts.

**Planning:** `plan_trip` always re-plans the route from everyone's picks (today only groups do), then runs the specialists as now.

**When the ideas agent fails** (no key, timeout, blocked): it falls back to a saved result like every agent. With none, the screen says the agents could not suggest places and shows the "Add a place" box, so people can still enter their must-dos by hand.

## Data model (`models.py`)

- New `Idea`: `id`, `name`, `city`, `category`, `why`, `source: Source | None`, `added_by: str | None` (traveler id for a place someone added; `None` for agent results).
- `TripState.ideas: list[Idea] = []`.
- `Traveler` keeps `need: list[str]` and `want: list[str]` (place names) and gains `skip: list[str] = []` and `picked: bool = False`. A place name appears in at most one of the three lists for a traveler. These lists are the only record of marks.
- `Attraction` gains `skip_by: list[str] = []` (traveler ids).
- `TravelerIn` keeps `need` and `want` with empty defaults so saved trips and existing tests still load; the forms stop sending them.

## Ideas agent (`specialists.py`, `orchestrator.py`)

- A new `ideas` `Spec`, built like the others: a Strands `Agent` with `web_research` and `read_source`, structured output `IdeasOut(ideas: list[IdeaOut])`, where `IdeaOut` has `name`, `city`, `category`, `why`, `source_url`.
- Task: suggest 15-25 distinct places and experiences across categories for the trip's destination, length and pace, each with a source from `web_research`.
- Deterministic review (`build_ideas`), each failure sent back as feedback:
  - every `source_url` was returned by a tool in this run;
  - between 12 and 25 places;
  - no duplicate names (case- and space-insensitive);
  - every city is in the destination (same check the attractions review uses for cities).
- Fallback and the review loop are the existing `SpecialistNode` behavior. The result is stored in `state.ideas`.
- `timeframe_graph` adds `ideas` with an edge from `route`, next to `profile` and `timeframe`.

## API (`api.py`)

Both new endpoints return `TripView` and answer 400 once the stage is `planning` or `review`.

- `PUT /api/trips/{trip_id}/travelers/{traveler_id}/picks`, body `{need: [str], want: [str], skip: [str]}`.
  - 403 unless `X-Traveler` is `traveler_id`.
  - 400 if a name is not on `state.ideas`, or appears in more than one list.
  - Sets the traveler's three lists and `picked = true`.
- `POST /api/trips/{trip_id}/ideas`, body `{name: str, city: str | None}`.
  - Any traveler on the trip (`X-Traveler` required).
  - 400 if the name is empty or already on the list.
  - Appends an `Idea` with `added_by` set, `category` "Added by the group", no source. No agent runs; the attractions agent researches it at planning time like any wish.

## Planning changes

**Attractions agent**

- `wishes()` returns, per wish, who needs it, who wants it and who skips it.
- `brief()` lists each traveler's "not interested in" places; the task tells the agent never to add those as extras.
- `build_attractions` sets `skip_by` from skip wishes and rejects:
  - an extra place (no need or want) that matches a skipped place by wish id or normalized name;
  - a place linked only to skip wishes.

**Scheduler (`scheduler.py`)**

- A shared activity's `travelers` is everyone minus `skip_by`.
- The split-off logic treats skippers as available during that activity, so one of their own must-do or interested places can be placed for them then; otherwise it is free time.
- `plan_note` names skips, e.g. "Alex skips Tokyo Disneyland on Fri Nov 13."

**Budget:** unchanged; tickets are already charged per traveler going.

**Validation (`validate.py`):** new error when a traveler is going to a place they skipped.

**Route:** `plan_trip` always runs `route_graph()` and `_set_dates` before the specialists.

## Frontend

- `TripForm` and `TravelerForm`: remove the two fields (and the demo-trip button's values for them).
- New `components/Picks.tsx`: the ideas list grouped by category, three-way mark per place, others' marks as chips, "Add a place" form, "Save my picks" button.
- `api.ts`: `savePicks`, `addIdea`. `types.ts`: `Idea`, `TripState.ideas`, `Traveler.skip`, `Traveler.picked`, `Attraction.skip_by`.
- `App.tsx`: before planning starts, show `Picks` when `you.picked` is false or the person chose "Edit my picks"; otherwise the existing date / gathering screens.
- Review cards: a "Skipping" chip next to "Needs it / Wants it / Going" (cards gain `skip_by` names in `cards.py`).

## Testing

Backend (pytest):

- `build_ideas`: unknown URL, too few, too many, duplicates, city outside the destination.
- Picks endpoint: only your own; names must be on the list; a name in two lists; refused after planning starts; sets `picked`.
- Add-a-place endpoint: added with `added_by`; duplicate refused.
- `wishes()` with skips.
- `build_attractions`: an extra matching a skip is rejected; `skip_by` is filled.
- Scheduler: a skipper is not on the activity and is not charged; their own pick is placed during it when it fits; `plan_note` mentions the skip.
- Validation: going to a skipped place is an error.
- A solo `plan_trip` re-plans the route.

Frontend: type-check, build, and a two-person run in the browser pane.

## Known gaps

- **Demo without a key.** There is no recorded ideas list yet, so the demo trip shows an empty list without an API key; places can be added by hand. One live run with `RECORD_FIXTURES=true` records it. The recorded attractions result may also stop matching the demo trip once the host's must-sees come from picks instead of the form; check this during implementation.
- **Profile agent** still infers interests from the form, which now says less. Not changed here.
- `DEMO.md` and `README.md` describe the old form; update those passages.
