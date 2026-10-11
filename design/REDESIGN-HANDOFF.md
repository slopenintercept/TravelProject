# Tripwright UI redesign: handoff for implementation

**Status: built on 2026-10-11.** Everything below was implemented later the same day; `HANDOFF.md` ("The redesign") says what was built, what was decided along the way and what still needs the user's sign-off. Screenshots of the result are in `implemented/`. The rest of this file is kept as written.

Written 2026-10-11 for a new Claude Code chat. The design work is finished and approved as mockups. Your job is to rebuild the React frontend so the whole app looks and behaves like them. Nothing in `frontend/` has been changed yet.

Read `HANDOFF.md`, `README.md` and `DEMO.md` at the repo root for the product, the architecture and the decisions already made. This file covers only the redesign.

## Start here

- **The design is `design/direction-c-lilac.html`.** It is one static HTML file with three screens (Start, Picks, Review), filled with a real saved trip's data. It is the source of truth for layout, colour, type and copy. Read its CSS and markup before writing any code.
- **See it running:** start the `design-mockups` entry in `.claude/launch.json` (a static server on port 5180), then open `http://localhost:5180/Direction%20C%20Options.html`. That page switches between the three screens and a mid-run example. Opening the HTML file directly does not work for the switcher page, because it loads the mockup in a frame.
- **Screenshots** of the approved state are in `design/reference/`, numbered 1 to 5. `palette-from-user.png` is the image the user supplied for the colours.
- **Only three screens are designed.** The app has about ten. The rest must be built in the same system; section "Screens that were not mocked" says how, and which choices need the user's sign-off.
- **Scope is the website at desktop width** (1280 to 1440px). The user said to work only on the hosted website. Do not spend time on phone layouts unless asked.

## What the user decided

These came from the user directly. Do not reopen them.

| Decision | Detail |
|---|---|
| Direction | "C": one screen for the whole trip, a feed on the left and the plan on the right. Directions A and B were rejected. |
| Reference | The user named mindtrip.ai as the reference for feel. The mockups borrow its large tight headlines, pill controls and big rounded panels, not its logo, typeface, photos or layouts. |
| Flow | Layouts may be reworked and the flow may change. Review and Itinerary are no longer two tabs: decisions sit in the feed and the calendar is always beside them. |
| Colour | The "Lilac (Soft & Airy)" palette, sampled from the user's own image. Seven palettes I proposed were rejected as ugly (Ember, Moss, Paper, Daybreak, Blush, Departures, Plum), and so was the original navy. Do not propose colour variations. |
| Agents | Every headline on every screen names the agent behind it, with a status dot and a few words on what it found or is doing. |
| Agent naming | Always "X agent": "Validate agent", "Ideas agent". Per-traveler ones read "Flight agent · Alex". |
| Agent tags on Start | Hidden. Nothing has run yet. |
| Agent tags on categories | Kept on every category heading in Picks, even though each says "Ideas agent". The user was offered the option to drop them and said keep. |
| Agent details | Clicking a tag opens that agent on an "Agents" tab on the plan panel, with its card highlighted. |
| Other agent placements | A top strip, a side rail, a card in the feed and a bottom dock were shown and not chosen. Do not build them. |

## The design system

Lift exact values from the `:root` block and the rules in `design/direction-c-lilac.html`. The summary below is for orientation.

**Layout.** The app fills the viewport: a 64px top bar, then two panes that scroll independently. The feed is a fixed 560px column on the left. The plan panel (called the board) takes the rest, as one large rounded panel with 20px of margin on the right and bottom.

**Type.** Bricolage Grotesque (weights 600 to 800, tracking about -0.04em) for the brand, headlines and large figures. Figtree (400 to 700) for everything else. Both load from Google Fonts in the mockup; decide whether to load them the same way or bundle them, and say which you chose. Sizes in use: 76px hero, 34px screen headline, 24px section headline, 16px body, 14px and 13px secondary. Nothing below 13px.

**Colour tokens.**

| Token | Value | Used for |
|---|---|---|
| `--ground` | `#d8e4fc` | Page background |
| `--board` | `#e9f0fe` | The plan panel |
| `--glass` | white at 50% | Cards, on top of the ground |
| `--tint` | `#0a54a6` | Mixed at 4 to 30% for input fills, chips, calendar blocks, dividers |
| `--accent` / `--on-accent` | `#0a54a6` / white | Buttons, headlines, agent names |
| `--strong` / `--text` / `--dim` | `#07174f` / `#1d2d62` / `#51648a` | Text, strongest to quietest |
| `--pick` / `--pick-soft` | `#6e57ac` / `#b5a8df` | A place marked Must do / Interested |
| `--solo` / `--alt` | `#fcd3de` / `#a9f1d9` | A calendar activity only you are on / only another traveler is on |
| `--ok` / `--bad` | `#2fb3b8` / `#fca58e` | Agent finished dot / over-budget pill and conflict card edge |
| `--c-flights`, `--c-lodging`, `--c-attractions`, `--c-transport` | `#1698de`, `#7cd1cb`, `#f185a5`, `#b5a8df` | Budget bar segments |

**Shape.** Buttons and chips are full pills. The board has a 32px radius, cards 24px, idea rows and agent cards 18px, calendar blocks 10px. Cards have a white hairline border and one soft shadow (`--lift`).

**Not in the design, on purpose:** photos (the app has no image source), gradients, emoji, icons beyond text arrows.

## Agent tags

The pattern is a headline with a small button beside it on the same baseline:

`[dot] Validate agent  5 issues, 4 yours`

- The dot is teal when the agent is finished, a pulsing blue dot while working, a blue ring while under review, a hollow grey ring while waiting.
- The text is a few words only. While the agent runs it says what it is doing: "working…", "under review", "sent back, trying again", "waiting".
- Clicking it switches the board to its Agents tab and highlights that agent's card.

Which agent goes with which headline, as mocked:

| Screen | Headline | Agent | Words when finished |
|---|---|---|---|
| Picks | What sounds good? | Ideas agent | 24 places |
| Picks | each category (Family, Culture…) | Ideas agent | 4 found (the count in that category) |
| Picks | Draft plan | Draft agent | 13 activities from everyone's picks |
| Review | Needs you | Validate agent | 5 issues, 4 yours |
| Review | Your flight | Flight agent · Alex | best of 3 options |
| Review | Your stays | Lodging agent | 8 options a stay |
| Review | the budget figure | Budget agent | both travelers over |
| Review | Your days | Scheduler agent | 12 placed, 5 didn't fit |

Three things the mockup does not settle, which you must handle:

1. **Where the short words come from.** The mockup's are hand-written. The real data has `state.agents[name].found`, which is longer ("3 options; best is Delta at $1,874"). My recommendation: derive the short form in the frontend where the state already holds the number (ideas per category, violations, unscheduled, flight options), and fall back to `found` cut off with an ellipsis. Do not change the backend for this without asking.
2. **Statuses the mockup does not show.** `AgentStatusName` in `frontend/src/types.ts` also has `sent_back`, `fallback`, `pending` and `failed`. The current app shows fallback as "saved result" and offers "Retry the N that didn't finish" (see `AgentPanel.tsx`). Keep that behaviour; put the retry button on the Agents tab. Give those states a dot in `--bad`.
3. **The Agents tab replaces `AgentPanel`.** The mockup's agent cards show name, status and what was found. The real lanes also carry the orchestrator's rejections and a tool log (`useTrip.ts`). Keep both, behind the card or a "Show details" control, so the demo can still show agents being sent back.

## Screen by screen

### Start (mocked)

Replaces `TripForm.tsx`. Left: the "Plan a trip." headline, the existing lede, the seven inputs as rows in one card, and a full-width "Start planning" button. "Use the demo trip" moves to the top bar. Right: the board in its empty state, with "Your route" and "Your days" headlines and dashed placeholders. No agent tags.

### Picks (mocked)

Replaces `Picks.tsx` and puts `DraftPlan.tsx` beside it. Left: places grouped by category, each row with Must do / Interested / No. A Must do row fills purple; an Interested row gets a lilac tint; a No row goes dashed with the name struck through. Clicking the active choice again clears it. "Add a place" and "More like my picks" sit at the end of the feed. Right: the draft plan as seven day columns, the tallies, and "Save my picks".

The mockup shortens "Not for me" to "No" on the button to fit the row. The mockup's draft columns highlight your own Must dos in purple.

### Review (mocked)

Replaces `Review.tsx`, `Itinerary.tsx`, `CalendarGrid.tsx`, `BudgetBar.tsx` and the Review / Itinerary tabs in `App.tsx`.

Left, the feed:
- **Needs you.** One card per thing that needs this traveler: each place that did not fit, with its reason, and the traveler's own budget overrun. Built from `state.violations` and `state.unscheduled`. Another traveler's budget problem is counted in the tag ("5 issues, 4 yours") but gets no card.
- **Your flight** and **Your stays.** The chosen option, its facts as chips, "Why this pick", then Approve, Swap and the booking link.

Right, the board:
- A two-tab switch: "Your days" and "Agents · 14".
- The budget row: spent of total, the Budget agent tag, a bar in four category colours with a marker at the budget, and the "Over by" pill.
- "Your days": the Everyone / Just me / other-traveler switch, Finish, and a week calendar from 08:00 to 24:00 with the weather in each day's header. Split activities sit side by side, pink for yours and mint for the other traveler's.

What the mockup leaves out of Review, and my recommendation for each:
- **Transport legs and the "most travelers here pick" cards.** Add them to the feed as further sections ("Getting around", Transport agent) in the same card style.
- **Attraction cards.** The current Review lists every attraction with Approve / Swap / Remove. In the new design the calendar is where attractions are handled (click one to swap or remove, as `Itinerary.tsx` does today), so do not repeat them as feed cards. Confirm with the user before dropping per-attraction Approve.
- **"Swap it in" and "Drop" on a conflict card are new buttons.** Drop maps to the existing remove decision (`api.decide(id, 'remove', 'attraction:<id>')`). "Swap it in" has no single existing call: `api.swapItem(itemId, attractionId)` needs the scheduled item to replace, so it needs a step where the traveler picks which activity gives way. Design that step in the same style and show the user.
- **Budget proposals.** `onApplyBudget` and `state.budget_proposals` exist today. Put the proposal on the budget-overrun card in "Needs you".

### Screens that were not mocked

Build these in the same two-pane system. These layouts are my recommendations, not the user's decisions: show the user each one once it runs.

| Screen | Today | Recommended layout |
|---|---|---|
| Choosing dates | `Timeframe.tsx` | Feed: "When do you want to go?" with the Timeframe agent tag, one card per date window. Board: the route so far, and the Agents tab. |
| Who's coming | `Gathering.tsx` | Feed: "Who's coming?", the traveler list, the invite link, "Start planning". Board: the draft plan, as on Picks. |
| Join / Who are you | `Join.tsx`, `TravelerForm.tsx` | Feed only, centred or with the trip summary on the board. No agent tags. |
| Agents working | the waiting branches in `App.tsx` | Feed: the headline and one line per agent as it reports. Board: open on the Agents tab, since there is no plan yet. This is the screen where the working, under-review and sent-back states matter most. |
| Choose flight and stays | `Choose.tsx` | Feed: "Your flight" and one "Your stays" section per city, options as selectable cards, Flight and Lodging agent tags. Board: the days so far. |
| Finish | `Finish.tsx` | Feed: "Your trip is ready to book" and the bookings by category. Board: the final days, read-only. |

Things in today's top bar and page chrome that the mockup does not show but must survive: the Back button and its rules (`back` in `App.tsx`), "Edit my picks", "Switch" traveler, "New trip", the "Agents working…" indicator, and the error and notice banners. Put the banners at the top of the feed and Back in the top bar.

## Open questions for the user

Ask these early; none blocks starting on Start, Picks and the shared styles.

1. **The map.** The mockup shows a map as a dashed placeholder on Start and Picks. The app has no map. Ideas carry `lat` and `lon`, so one is buildable, but it is new scope and a new dependency. Build it, or drop the placeholder?
2. **Purple for marked places.** Must do and Interested use the palette's purple and lilac so a marked place never looks like a blue button. The user's image had no Picks screen, so this was my call and is not yet confirmed.
3. **Per-attraction Approve** (see Review above).

## How to work in this repo

- **Run the frontend** with the `tripwright-frontend` launch entry (Vite on 5173, proxying `/api` to the backend on 8000). The backend serves `frontend/dist`, so port 8000 only shows your changes after `cd frontend && npm run build`. That build also runs the TypeScript check; there is no frontend test suite.
- **The local backend reads the hosted database** (`DATABASE_URL` is set in `.env`). Anything you click that changes a trip changes real hosted data. Creating a trip or starting planning launches real agent runs that take minutes.
- **Use existing trips to look at screens:** `http://localhost:5173/#trip_99aaaeb1/p1` is at Review with two travelers; `#trip_faf39eb6/p1` shows Picks.
- **Do not restart the servers on 8000 or 8001** without checking that no trip is mid-run; a restart kills live runs.
- **Other Claude chats edit this folder at the same time.** Run `git status` first. As of this handoff another chat has uncommitted changes in `HANDOFF.md`, `README.md`, `backend/tests/test_ideas.py` and `backend/tripwright/specialists.py`. Commit only your own files; never stash or revert someone else's.
- **Nothing from the design work is committed.** `design/`, `.impeccable/`, `.claude/skills/`, `.claude/agents/`, `skills-lock.json` and one new entry in `.claude/launch.json` are all uncommitted. Ask the user before committing them.
- **Do not deploy.** The app is live on Akamai; deploying is the user's call.
- **A design checker runs on every edit.** The `impeccable` skill installed hooks in `.claude/settings.local.json` that scan UI files after each Edit or Write and at the end of a turn. Fix real findings. Three false positives from the mockups are already recorded in `.impeccable/config.json`.
- **Skills installed for this work:** `impeccable`, `emil-design-eng`, `animate`, `review-animations`, `web-design-guidelines`, `vercel-react-best-practices`, `vercel-composition-patterns`, `break-ui`, and the `ui-ux-pro-max` plugin.
- **Product rules that still hold** (from `HANDOFF.md`): no source or evidence links in the UI; "booking" means handing the user a link.

## Suggested order

1. Tokens, fonts and the two-pane shell in `styles.css` and `App.tsx` → verify: every existing screen still renders inside the new shell, `npm run build` passes.
2. Start, then Picks with the draft plan beside it → verify: side by side with `design/reference/1-start.jpg` and `2-picks.jpg` at 1360×900; marking, clearing and saving picks still work.
3. The agent tag component and the Agents tab, replacing `AgentPanel` → verify: tag click opens the tab on the right agent; an agent sent back by the orchestrator still shows it.
4. Review: feed, budget row and calendar → verify against `3-review.jpg`; drag, swap and remove on the calendar still work; approve and swap still work for flight and stays.
5. The screens that were not mocked, one at a time, showing the user each.
6. Remove the styles and components the new design makes unused.

## Files

| File | What it is |
|---|---|
| `design/direction-c-lilac.html` | The approved design. Source of truth. |
| `design/shared.js` | The mock data and the small script behind the mockups. |
| `design/Direction C Options.html` | Switcher for the three screens and the mid-run example. Needs port 5180. |
| `design/reference/` | Screenshots of the approved design and the user's palette image. |
| `design/direction-c-night-flight.html` | The same design in the rejected navy palette. Kept as the old version only. |
| `design/Tripwright Redesign.html`, `direction-a-postcard.html`, `direction-b-ledger.html` | The first round of three directions. A and B were rejected. History only. |
