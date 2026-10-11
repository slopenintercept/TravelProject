# Handoff: Retry on the user's real trip

Written 2026-10-11 at about 05:40 Central by the chat that checked payments. You press one button and report what happened; that chat checks on it every three minutes. There is no code to write.

## What this is

`trip_479d20ea` is the user's own trip on the local server (port 8000): Alex (`p1`, the host) and Sam (`p2`), $3,000 each, Dec 11 to Dec 31. It is at stage `choosing`. Its Lodging agent ended as `pending` at 04:24 ("No result yet: timed out after 240s"), so neither traveler has stays.

The cause was fixed in commit `fd4cd2e` (`handoffs/lodging-over-budget.md` has the diagnosis and the fix). The server on port 8000 has run that code since 05:13:20. The one end-to-end run of the fix was on a copy of this trip. Nobody has pressed Retry on the real one.

## What the user approved

Pressing "Retry the one that didn't finish" on this trip, at about 05:35. It uses a few minutes of the inference quota.

## Before you press

All read-only.

1. `curl -s http://localhost:8000/api/health` says `sqlite` and `local disk`.
2. `GET http://localhost:8000/api/trips/trip_479d20ea` shows `busy` false, stage `choosing`, and agent `lodging` with status `pending`. Print only the fields you need, not the whole trip.
3. If `lodging` is no longer `pending`, or the trip is busy, stop and say so in your Result: the user may have pressed it themselves.

## Press it

Open `http://localhost:8000/#trip_479d20ea/p1` (Alex's own link), switch the board to the **Agents** tab, and click **Retry the one that didn't finish** once.

What the button does (`retry` in `backend/tripwright/api.py` line 334 and `backend/tripwright/orchestrator.py` line 524): it runs again only the research agents that did not finish, which here is Lodging alone. The `draft` agent also shows `failed` ("Stopped when the server restarted"); it is not a research agent, it is not retried, and it is left out of the list on purpose.

## What to expect

- The trip is `busy` straight away and the Lodging lane shows the agent working.
- On the copy it was accepted on attempt 1, about 80 seconds after the press. The agent's limit is 240 seconds across all attempts.
- On the copy both travelers got a Tokyo room at $41 a night for Dec 12 to 28 (within budget), a Kyoto room at $54 and a last Tokyo night at $57, the last two marked "Cheapest option found at $54 a night; that is over Alex's lodging budget of about $44 a night." Prices are live, so the rooms may differ.

## After it stops being busy

Report each of these:

1. How long it took and the Lodging agent's final status, attempt count and any send-back messages.
2. For each traveler: how many stays, and for each stay the city, the dates, the room chosen, its nightly price, and whether its card says it is over budget.
3. The stage is still `choosing` and neither traveler is `confirmed`.
4. On the Choose screen, for Alex and then for Sam (`#trip_479d20ea/p2`): every stay shows its options, and nothing in the browser console is an error.

## If it does not work

- **Timed out again, or `fallback`:** do not keep pressing. Copy what the Agents tab shows for Lodging (what it searched, what it was sent back for) into your Result. Do not change code.
- **A network or endpoint error** (the endpoint allows 60 requests a minute): one more press is fine. Say that you did.
- **The button answers "The agents are still working" or "Every agent finished":** report it as it is.

## Ground rules

- Read "Start here" and "Gotchas" in `HANDOFF.md` first.
- **Do not confirm a flight or a room for either traveler.** Choosing is the user's. Do not move, add or remove anything else on the trip.
- **Do not stop or restart the server on port 8000.** The run lives in that process; a restart kills it and leaves the page saying "working".
- Another chat is changing `frontend/src/useTrip.ts` (`handoffs/stale-hold-message.md`) and will rebuild `frontend/dist` once at the end. That cannot hurt the run. If the page looks wrong after a reload, reload once more.
- Do not commit, push or deploy. Do not touch the hosted site. Never print `.env` or `.env.hosted`.

## When you finish

Add a `## Result` section at the end of this file with the four points above, or what went wrong. Write it last and in one go: the checking chat takes that heading as "done".
