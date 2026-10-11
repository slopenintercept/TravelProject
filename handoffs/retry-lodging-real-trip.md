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

## Result

Written 2026-10-11 at about 05:45 Central. Retry was pressed once, at 05:40:15, and it worked.

**Before the press** (read-only): health said `sqlite` and `local disk`; the trip was not busy, stage `choosing`, Lodging `pending` on attempt 2 ("No result yet: timed out after 240s").

1. **Time and status.** Busy straight away; the Lodging lane showed the agent working. It was `accepted` at 05:41:14, about 59 seconds after the press, on attempt 1, with no send-backs ("Accepted by the orchestrator"). Found: "Tokyo: 2 options from $592; Kyoto: 6 options from $100; Tokyo: 3 options from $75". Every other agent is unchanged; `draft` is still `failed` ("Stopped when the server restarted"), as expected.
2. **Stays.** Alex and Sam each have the same 3 stays with the same rooms chosen:
   - Tokyo, Dec 12 to Dec 28: Guest House Tokyo Samurai, Asakusa, $41 a night ($656). Within budget ("Best-rated option within Alex's lodging budget of about $44 a night"). 2 options.
   - Kyoto, Dec 28 to Dec 30: Agora Place Kyoto Nijo, Nakagyo, $50 a night ($100). Says over budget ("Cheapest option found at $50 a night; that is over Alex's lodging budget of about $44 a night."). 6 options.
   - Tokyo, Dec 30 to Dec 31: TOKYO-W-inn Asakusa, $75 a night ($75). Says over budget, same wording at $75. 3 options.
   Sam's cards say the same with Sam's name.
3. **Stage.** Still `choosing`; neither traveler is `confirmed` (checked again at 05:45). Nothing was confirmed or changed by this chat.
4. **Choose screen.** After a reload, Alex's (`/p1`) and Sam's (`/p2`) pages each show all three stays with their options (2, 6, 3) and one room selected in each. Totals: Alex $2,523 of $3,000, Sam $2,624 of $3,000. The browser console had no messages at all for either.

**Two things seen on the Choose screen, not fixed (no code was changed):**

- The room chosen for each over-budget stay carries the badge "Matched to your budget", right under a line saying it is over budget.
- `Choose.tsx` takes its selected flight and rooms from the trip only when the screen first opens (`useState` at lines 30 and 31). Seen: going from Sam's link to Alex's in the same tab without a reload left no flight selected and the total at $831 (stays only); a reload gave $2,523. By the same code, a Choose screen that was open before the Retry would show the new stays with no room selected until reloaded; that case was read from the code, not clicked.
