# Handoff: the checking chat

Written 2026-10-11 at about 06:25 Central by the chat that has been checking the others' work since 05:22. The user is moving to a new chat and wants it "to operate the same you do inside of this chat". This file is how that chat worked, what is true right now, and what is still open. `HANDOFF.md` is still the main state file for the app; read its "Start here" and "Gotchas" too.

## Read this first

1. **Nothing is running that needs you.** Every handoff that was passed to a subagent is back, reviewed, committed, pushed, in `main` and deployed. This chat's three-minute timer is deleted.
2. **Ask before the next deploy.** At 06:21 a deploy went out seconds after the user stopped the command that started it, and it most likely cut off a Lodging run on a hosted trip (see "What went wrong at 06:21"). The user's go-ahead to deploy was given to this chat; get your own.
3. **One hosted trip may need a click:** `trip_b2d14492` (Alex and Shree, at `choosing`) has its Lodging agent marked "Stopped when the server restarted". "Retry the one that didn't finish" on its Agents tab runs it again. It uses inference quota and it is the user's or their friend's trip, so tell the user; do not press it yourself unless asked.

## The job

The user finds a problem, usually by using the app and sending a screenshot. Then:

1. **Find the cause yourself**, far enough that a subagent does not have to guess: the file and line, the data that shows it, and the smallest change you can see.
2. **Write one handoff file per fix** in `handoffs/`. The user passes each file to a fresh chat ("subagent"). You do not write the fix.
3. **Check every three minutes** for a `## Result` heading at the end of the file.
4. **When it is there:** read the diff and the Result, run the tests and the type check, build the frontend if it changed, click through the fix yourself on the built frontend, commit it together with its Result, push the branch and fast-forward `main`.
5. **Put it live:** restart the local server if the backend changed, and deploy to the hosted site, each only when no trip is busy.
6. **Keep `HANDOFF.md` true** and tell the user what happened in a few plain lines.

Tiny things (two leftover lines in a config file) this chat just did itself and said so.

## What the user has said, in their words

- 05:35, on what this chat may do: "I have given you also permissions to do everything so do them accordingly that include updating server, commit, pushing, and merging and everything in between". After that, pushes to `main` from this chat went through; earlier chats' were refused by their permission check. A go-ahead belongs to the chat it was given to: ask the user once whether it carries over to you, and ask every time before a deploy (point 2 above).
- 05:35, on the method: "just make handoff files for it ill pass them to agents, you check every 3 mintues".
- 06:05, on demo mode: "make sure all of the problems we are fixing also fix for the 'demo' version as well if they exist in there if not don't worry about them".
- 06:10, on scope: "its just a hackathon project no one else is going to use it after we show it off". Do not raise multi-user, security-hardening or long-term concerns. Judge a finding by whether it shows in the demo.
- On two findings from their first hosted run: "the other 2 we dont care about right now" (they are listed under "Left alone on purpose").
- 06:20, after being offered a fix for how short activities look on the calendar: "honestly no need to do it ignore that part". I read "that part" as the calendar fix and dropped it. `handoffs/calendar-short-activities.md` says so at its top.
- They want short answers in plain English, the next action first. They run commands themselves in the app's Terminal pane when given one, one command per code block. The memory files for this project say the same and load into every chat here.

## State right now

Checked between 06:22 and 06:25.

| What | State |
| --- | --- |
| Branch `combine-picks-and-group-trips` and `main` | Level with each other and with GitHub. This file's commit is the newest. Working folder clean. |
| Local server, port 8000 | Started 06:14:11 on the code at `a736182`, in a Terminal tab titled "Tripwright :8000" that this chat opened. Health: `sqlite`, `local disk`, `stripe test mode`. It serves `frontend/dist`, built at about 05:56 from the source at `62c4a9d`. A new chat cannot stop another chat's terminal tab; stop it by killing whatever listens on the port. |
| Hosted site | Container recreated at 06:21:34 with the code at `a736182`. Every committed file under `backend/` and `frontend/` is on the server with the same checksum, the 27 Python files in the running container match, and the JavaScript and stylesheet it serves have the same SHA-256 as `frontend/dist`. Health: `postgresql`, `object storage`, `stripe test mode`. The server's `.env` has 17 settings, none twice. |
| Tests | 128 backend tests pass; `npx tsc --noEmit` passes. |
| `.claude/launch.json` | As committed. No temporary entries. |
| Other servers | Only `design-mockups` on port 5180. Nothing on 8001 to 8017 or 5173 to 5187. |
| Stripe test account | 15 PaymentIntents when last asked at about 05:28, none holding a card, none live. The user has since paid `trip_119a35c4` on the hosted site, so there are more now. |

### Trips

Hosted site (the address is left out of the repo on purpose; `deploy/.venv/bin/linode-cli linodes list --label tripwright-app` prints it):

| Trip | What it is | State |
| --- | --- | --- |
| `trip_paydemo` | The unpaid safety net named in `DEMO.md` (Alex `p1`, Sam `p2`) | `review`, no payments. **Never approve or back out on it.** |
| `trip_paycheck` | The payments chat's paid check | `review`, both `captured` |
| `trip_119a35c4` | The user's (Deep) and their friend's (Shree), started about 06:05 | `review`, both confirmed, both paid. The first trip ever planned end to end on the hosted site. Its Lodging agent timed out and shows saved results (`fallback`). |
| `trip_b2d14492` | Alex and Shree, most likely the friend's | `choosing`, no stays. Lodging "Stopped when the server restarted"; weather `pending` (OpenStreetMap answered 429). |
| `trip_13d3fa4f` | The user's first try (Deep, start date 2027-11-28) | `gathering`. Its profile still reads "Alex ... from Kansas City"; the fix only reaches new trips. |

Local, port 8000: `trip_479d20ea` (the user's real trip, Alex and Sam) is at `choosing` with three stays each since the retry at 05:40. Nobody has confirmed a flight or a room; that is the user's to do.

## What this chat shipped

All on `combine-picks-and-group-trips`, all in `main`, all deployed.

| Commit | What | Handoff |
| --- | --- | --- |
| `20b7737` | A line about payments at the top of the feed is cleared when another traveler changes the payments | `stale-hold-message.md` |
| `7ad9911` | (No code.) Retry on `trip_479d20ea` gave both travelers their stays | `retry-lodging-real-trip.md` |
| `84e8f48` | The picked room on Choose reads "Picked for you" instead of "Matched to your budget" | `choose-budget-badge.md` |
| `62c4a9d` | `<Choose>` is keyed by traveler, so one traveler's selection is not carried to the next | `choose-selection-carried-over.md` |
| `a736182` | A new trip carries over only the saved stated preferences, not the last host's profile sentence | `profile-wrong-traveler.md` |

Before those, between 05:22 and 05:35, this chat checked the payments chat's and the review chat's work; what it ran is under `## Result` at the end of `handoffs/review-chat.md`.

Deploys by this chat: 05:45 (`20b7737`) and 06:21 (`a736182`). Local restart: 06:14.

**Demo mode.** `DEMO_MODE=true` changes the search tools only (`backend/tripwright/recorded.py`). The frontend does not know about it and neither does `payments.py`, so all five fixes hold there. The profile fix was run live with `DEMO_MODE=true`; with no inference key the Profile agent shows the recorded profile, which names nobody.

## What went wrong at 06:21

Say this to the user plainly if they ask; they were told once, at about 06:25.

- The quiet check passed at about 06:20:50: no trip busy, no change on the hosted site for three minutes. `deploy.sh` started.
- The user stopped the command. The app reported the call as rejected, but the copy and the build were already under way on the server, and the container was recreated at 06:21:34.
- Afterwards `trip_b2d14492`'s Lodging agent read "Stopped when the server restarted". `recover` (`backend/tripwright/orchestrator.py`, line 507) writes that only for an agent that was working when the server went down, and at 06:19 nothing on that trip was working. So someone most likely pressed Retry in the 40 seconds between the check and the restart. The old container's log went with it, so this cannot be confirmed.
- Nothing else was affected: `trip_119a35c4` was already at `review` and paid, and its stale `draft` status became `failed`, which the app leaves out of its lists.

What to take from it: **the check cannot see the 40 to 50 seconds the build takes.** While the user is on the hosted site, do not deploy on the check alone. Ask, wait for "deploy now", then run the check and the deploy.

## How to do each step

### Look for a Result

```bash
grep -c '^## Result' handoffs/<file>.md; git status --short
```

Careful: `grep -c` exits with status 1 when the count is 0, so anything chained after it with `&&` does not run. It cost this chat one skipped edit and one skipped deploy. Use `;` after it.

### The timer

`CronCreate` with `*/3 * * * *` and the whole check written into the prompt (what is open, what to do when a Result appears, the deploy rule). It lives only in the chat that made it and fires only while that chat is idle. Delete it with `CronDelete` when there is nothing left to watch, and recreate it with a new prompt when the open items change.

### Review

- `git diff` should touch only the files the handoff named. `git diff handoffs/ | grep -c '^-[^-]'` should print 0: the subagent only added to its handoff.
- `.claude/launch.json` should have no diff, and nothing should be listening on the subagent's ports.
- `cd backend && .venv/bin/python -m pytest -q` (128 now) and `cd frontend && npx tsc --noEmit`.

### Build

`cd frontend && npm run build`, once, by this chat only. To prove `frontend/dist` is the build of the current source without touching it: `npx vite build --outDir <scratch>/distcheck --emptyOutDir` and compare the SHA-256 of each file. Builds are repeatable, and the server's own build of the same source has matched byte for byte on every deploy.

### Click through on the built frontend

A second backend that serves `frontend/dist` from a scratch database, so no real trip and no Stripe:

- A temporary entry in `.claude/launch.json` named `tripwright-check`: `runtimeExecutable` `env`, args `DATA_DIR=<scratch>/data`, `DATABASE_URL=`, `OBJ_BUCKET=`, `STRIPE_SECRET_KEY=`, then `<repo>/backend/.venv/bin/python -m uvicorn tripwright.api:app --app-dir <repo>/backend --port 8003`. Start it with `preview_start`.
- Check `/api/health` says `sqlite`, `local disk` and, with the Stripe line, `holds kept in the app`. Leave `STRIPE_SECRET_KEY=` out only when the point is to test against Stripe test mode; every click then makes a test payment in the user's account.
- Seed it from a read-only `GET http://localhost:8000/api/trips/<id>`: change `state.id` and `store.save_trip(TripState.model_validate(state))`, run with the same variables. With `DATABASE_URL` empty, `config.DATABASE_URL` is `sqlite:///<DATA_DIR>/tripwright.db`, not an empty string: assert that before saving.
- The other traveler's action can be sent with `curl` and an `X-Traveler` header while you watch the first traveler's tab; that is exactly what another tab does.
- Never click "Confirm my flight and stays", "Retry", "Swap" or "Apply swaps" on a copy: they run agents and use the inference quota.
- Afterwards stop the server and remove the entry. `git checkout -- .claude/launch.json` is fine only when the whole diff is yours.

### Commit, push, merge

One commit per fix, holding the code and that handoff's Result. Match the messages in `git log`: a plain sentence saying what is now true. Then:

```bash
git push origin combine-picks-and-group-trips
```

```bash
git push origin origin/combine-picks-and-group-trips:refs/heads/main
```

```bash
git fetch && git branch -f main origin/main
```

A handoff-only commit after that puts `main` one behind again; push `main` again or say so.

### Restart the local server

Only when the backend changed. Check the newest rows of `trips` in `data/tripwright.db` and that `GET /api/trips/<id>` says `busy` false for each. Then kill whatever listens on port 8000 and start, from the project root in a Terminal tab titled "Tripwright :8000":

```bash
backend/.venv/bin/uvicorn tripwright.api:app --app-dir backend --port 8000
```

Confirm `/api/health` and that `trip_479d20ea` still has its stays.

### Deploy

Only with the user's word (see above), and only with a clean `git status`, because the deploy copies the working folder.

1. Over SSH, read the app's log (`cd /opt/tripwright && docker compose logs --since 45m app`), take every trip id in it, and ask the hosted site for each one's `busy`. A `draft` agent still marked `working` after planning started is stale and does not count. No trip busy, and no `POST`, `PUT` or `DELETE` in the last three minutes.
2. `PATH="$PWD/deploy/.venv/bin:$PATH" SSH_KEY=~/.ssh/tripwright_ed25519 bash deploy/deploy.sh`. About 50 seconds. The old container serves until the new one is built; the swap is a few seconds. A new container starts with an empty log.
3. Afterwards: `/api/health`; the SHA-256 of `/`, the JavaScript and the stylesheet against `frontend/dist`; `sha256sum` of every file under `/opt/tripwright/backend` and `frontend` (leaving out `node_modules`, `__pycache__`, `dist`, `.venv`) against `git ls-files`; `trip_paydemo` still has `"payments": {}`.

Print only a hosted trip's stage, `busy` and the fields you need; a command that printed a whole hosted trip was refused by an earlier chat's permission check.

### Ask Stripe

`cd backend && .venv/bin/python` with `stripe.StripeClient(config.STRIPE_SECRET_KEY).v1.payment_intents`, then `.retrieve(id)` or `.list(params={"limit": 100})`. Read `metadata` with `.to_dict()`. Never print any part of the key: a command that printed its first eight characters was refused.

## How to write a handoff for a subagent

The other eleven files in `handoffs/` are the examples; `stale-hold-message.md` and `profile-wrong-traveler.md` are the shortest complete ones. What made them work:

- **What happens**, as steps anyone can repeat, with the exact text on screen and the trip it was seen on.
- **Why**, with file and line numbers you opened yourself.
- **What the user approved**, in their words, and what they did not decide. If you chose a wording or a target, say it is yours.
- **Suggested change**: the smallest you can see, plus the two or three ways the obvious version goes wrong. "The checks are what matter; if you find something simpler, use it."
- **Checks**: numbered, each with what should be on screen. This repo has no frontend tests, so for the frontend the browser is the check; for the backend ask for a test that fails before and passes after.
- **How to try it**: the scratch backend recipe above with a port and entry names of its own (old handoffs name 8013 to 8017 and 5183 to 5187; pick others so two subagents never share one), the trip to copy, and what not to click.
- **Ground rules**: the one or two files that are theirs; who else is working and on what; do not build, commit, push or deploy; do not restart port 8000; do not touch the hosted site; never print `.env`.
- **When you finish**: a `## Result` section, written last and in one go, after their servers are stopped and their launch entries are removed.

Use `date +%H:%M` for every time you write down. Do not put the hosted address in a file: the repo is public.

## Left alone on purpose

- **The calendar.** On "Your days" an activity under about an hour and a half is one cut-off line with no time. It is the same on the demo trip. Diagnosed, handoff written, then dropped by the user. The file is kept in case they change their mind.
- **"Save my picks" is hidden** while the board shows the Agents tab; it sits under the Draft plan tab. The user got stuck there once.
- **A start date more than about 11 months away** has no fares, so the Timeframe agent is sent back until its 240 seconds run out. The host can still pick a date on the dates screen.
- **One saved profile for everybody**, so a stated preference carries to the next visitor's trip. The user said it does not matter.
- Everything under "Not done or not verified" in `HANDOFF.md`, and "Not verified by anyone" in `review-chat.md`.

## Open with the user

- `trip_b2d14492` needs Retry pressed (point 3 at the top).
- The six screens that had no mockup are still not signed off. The user said to leave them and to be reminded when they bring those screens up; Choose and Finish were both changed today.
- Fonts on Google Fonts or bundled: no answer yet.
