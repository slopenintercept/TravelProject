# Handoff from the review chat

Written 2026-10-11 at about 05:25 Central, for the next chat. Your job, as the user put it: read this file and the payments chat's handoff, and make sure everything is fine.

`HANDOFF.md` is still the main state file. This one covers only what this chat did, what it checked, and what nobody has checked. The fastest route is "State right now", then "Not verified by anyone".

## State right now

Checked between 05:19 and 05:25.

| What | State |
| --- | --- |
| Branch `combine-picks-and-group-trips` | At `21a2aa1` when this was written, and level with GitHub. This file's own commit comes after that and is local. |
| `main` | Still at `d292b70`, 10 commits behind the branch. It has none of today's later work. |
| Uncommitted | Only `.claude/launch.json`: three test entries, `tripwright-pay` (payments chat), `tripwright-map` and `tripwright-map-frontend` (map chat). The app does not need them. |
| Hosted site | Redeployed by the payments chat at about 05:13 from the code at `29f5a53`. `/api/health` says `postgresql`, `object storage`, `"payments": "stripe test mode"`. Container up. |
| Local server, port 8000 | Restarted by the payments chat at 05:13:20 on the new code. `/api/health` says `sqlite`, `local disk`, `"payments": "stripe test mode"`. |
| Backend tests | 126 passed at `29f5a53`. |
| Frontend type check | `npx tsc --noEmit` passes at `29f5a53`. |

The two commits after `29f5a53` (`a144dea`, `21a2aa1`) are the payments chat's docs and `.env.example`. I did not re-run the checks on them.

## What this chat did, in order

1. Read `HANDOFF.md` and `README.md` and went through the open items with the user.
2. Made a page with a picture of each of the eight redesign choices nobody had confirmed ("Tripwright Redesign Choices", a private Artifact in the user's account). The user's answers are in `HANDOFF.md` under "The redesign".
3. Found why two agents had failed. Neither was a server restart, which is what the user suspected. The evidence is in `handoffs/lodging-over-budget.md` and `handoffs/ideas-lost-task.md`.
4. Changed the deploy scripts (commit `36ae915`):
   - the six hosted settings (`DATABASE_URL`, `OBJ_*`) moved from `.env` to `.env.hosted`, which is gitignored and read only by the deploy scripts, so anything run on this Mac uses SQLite and `data/evidence`;
   - `deploy.sh` clears `backend/` and `frontend/` on the server before copying, and writes the server's `.env` from the local `.env` plus `.env.hosted`.
5. Wrote three handoffs. Three other chats built them and committed their own work: the map (`2b24e5b`), lodging (`fd4cd2e`), the ideas agent (`29f5a53`). Each handoff file ends with that chat's `## Result`.
6. Committed only its own files: `36ae915`, `d25e41b`, `db7bb5a`, and the commit that adds this file.

What this chat did not do: push, deploy, restart a server, or change any application code. It also never reached the payments chat: one message was sent, that session held it for approval, and it expired undelivered. Nothing collided anyway, because every chat committed its own files.

## What I checked, and how

- **The settings split, before any deploy.** What `deploy.sh` would send was compared key by key with the old `.env`: the same 16 settings, one line each. A local import of the settings then reported `sqlite` and no bucket.
- **The settings split, after the real deploy** (read-only look over SSH at about 05:20): the server's `.env` holds all six hosted settings, no key appears twice, and the hosted `/api/health` says `postgresql` and `object storage`.
- **The clearing step, after the real deploy:** the server's `frontend/src/components` and `backend/tripwright` list exactly the files in the repo, `Map.tsx`, `Pay.tsx` and `payments.py` included.
- **The committed code on its own.** An exact copy of what is committed, built from git and not from the working folder, passed the 126 backend tests and the frontend type check.
- **The backend starts:** `import tripwright.api` works with what is installed in `backend/.venv`.

## Not verified by anyone

Most useful first.

1. **The whole flow on the hosted site.** It has only ever been run through the first stage. Payments, the map and both agent fixes are now deployed there and nobody has planned a trip end to end.
2. **Payments.** This chat did not read or review the payments code. Two places where it meets this chat's work, worth a look alongside the payments handoff:
   - `STRIPE_SECRET_KEY` sits in the local `.env`, and `deploy.sh` sends `.env` to the server. It strips only `OBJ_*` and `DATABASE_URL` before adding `.env.hosted`. That is how the hosted site got Stripe test mode; confirm it is what the user wants.
   - `HANDOFF.md` records the user's rule that agents never enter payment details and that "booking" means a link. Confirm payments stays a step the traveler takes on a test card, with no agent involved, and that a key that is not a test key really is refused.
3. **The lodging fix on the user's real trip.** `trip_479d20ea` on port 8000 still has no stays. The server now runs the fix, but nobody has pressed "Retry the one that didn't finish" on that trip. The one end-to-end run was on a copy. A retry uses a few minutes of the user's inference quota, so ask first.
4. **The ideas-agent fix under a real overflow.** The unit tests and three small requests to the endpoint pass. No agent has been run until its conversation actually outgrew the context.
5. **The map.** Join and Agents working were not opened (they draw the same component). Pins in the same spot overlap. The tiles come from OpenStreetMap, so with no internet the map area is blank.
6. **`deploy/provision.sh` and `deploy/teardown.sh`.** Both now read and write `.env.hosted`, and neither has been run since. `teardown.sh` deletes everything and only the user should run it.
7. **The server's `.env` is readable by all users on that machine** (mode 644). The file kept the mode it had; `deploy.sh` only makes a new one private. The server has no other users, so this is tidiness, not an emergency.
8. **`main`.** A chat cannot push it. If the user wants it level, they run `git push origin origin/combine-picks-and-group-trips:refs/heads/main`.
9. **Demo mode outside Tokyo and Kyoto.** The recordings cover only those two cities, so an agent searching for anywhere else still gets the wrong pages and can run out of time. It keeps its task now; it may still return nothing.
10. **Screenshots.** `design/implemented/01` to `14` predate the map and payments.

## Open with the user

- The six screens that had no mockup (Dates, Who's coming, Join, Agents working, Choose, Finish) are not signed off. The user said to leave them and to be reminded if they bring those screens up.
- Whether fonts stay on Google Fonts or get bundled: no answer yet.
- The user wants short answers in plain English, the next action first.

## Checks you can run

None of these changes anything.

```bash
git status -sb
```

```bash
cd backend && .venv/bin/python -m pytest -q
```

```bash
cd frontend && npx tsc --noEmit
```

```bash
curl -s http://localhost:8000/api/health
```

The hosted address is left out because this repo is public. `deploy/.venv/bin/linode-cli linodes list --label tripwright-app` prints it, and `<address>:8000/api/health` should say `postgresql` and `object storage`.

Do not run `npm run build` casually: it replaces `frontend/dist`, which the server on port 8000 serves. Do not restart that server or deploy without checking that no trip is busy (`GET /api/trips/<id>` returns `busy`).

## Result

Checked on 2026-10-11 between about 05:22 and 05:35 Central by a third chat, at the user's request, against this file and `handoffs/payments.md`. No application code was changed, nothing was deployed and no server on port 8000 or the hosted site was restarted.

**What was run and what it showed**

- `pytest -q`: 126 passed. `npx tsc --noEmit`: passed. `git diff 29f5a53 HEAD -- backend frontend` is empty.
- **Port 8000:** the process started at 05:13:20, after the last source edit (05:05) and the last build of `frontend/dist` (05:12). Health says `sqlite`, `local disk`, `stripe test mode`. No local trip was busy, and no trip in `data/tripwright.db` has a payment on it.
- **Hosted site:** health says `postgresql`, `object storage`, `stripe test mode`. The page, the JavaScript and the stylesheet it serves have the same SHA-256 as `frontend/dist` and as port 8000. Over SSH, read-only: every committed file under `backend/` and `frontend/` is on the server with the same checksum and nothing else is there but macOS `._` copies, the pytest cache and `egg-info`; the 27 Python files inside the running container match the committed ones.
- **Hosted demo trips:** `trip_paycheck` has both travelers `captured` with a `ref`; `trip_paydemo` has no payments. Neither was changed.
- **Stripe, asked through its API:** the six PaymentIntents in `payments.md` are as it says, all `livemode` false. The account held ten before this check, not six: the two declined attempts are intents too (`requires_payment_method`), and two more `succeeded` at 05:06 belong to a local throwaway copy that was also named `trip_paydemo` (Alex and "Bleh"), not to the hosted one. Nothing is left holding a card.
- **Pay together clicked in the browser with Stripe on**, the gap `payments.md` lists first. A second backend on port 8003 on a scratch SQLite file, with copies of `trip_99aaaeb1` and the solo `trip_d23a42ee`, in two tabs: the declining card gave "was declined" and no hold; Visa gave "On hold" and "1 of 2 approved"; the other traveler's Back out gave "Hold released" in both tabs with no reload; approving again from both gave "Trip paid. $5,652 charged across 2 cards." in both tabs; the solo trip read "Pay for your trip" and one click gave "Your card was charged." No console errors. Stripe then showed those intents as `requires_payment_method`, `canceled`, and three `succeeded`. The server is stopped and its preview entry removed.
- **Cases with no test, run as throwaway tests with Stripe off** (not added to the repo): a solo trip is charged at once; with three travelers the first two holds wait for the third; a live key and a Stripe refusal both come back from the route as a 400 with no payment recorded; someone not on the trip gets a 403 and releases nothing.
- **Secrets:** no value from `.env` or `.env.hosted` is in any commit or in the handoff files, apart from the two public hostnames that are meant to be there; the hosted address is in no tracked file.

**Found**

- After Alex approves, the line at the top of Alex's feed ("$2,737 is on hold. Nobody is charged until … approves.") stays there after the other traveler approves, above "Trip paid", until it is dismissed. It is the app's ordinary message line and it is not wrong about anything that was charged, but in the two-screen demo it reads as a contradiction. Not changed.
- `HANDOFF.md` disagreed with itself in four places after the two chats' edits crossed (the branch "not pushed", the map "not built yet", port 8000 "has to be restarted", the "Updated" time). Corrected.
- This file's table says `.claude/launch.json` holds three test entries. It holds two, the map chat's; the payments chat removed its own.

**Still not checked by anyone**

Items 1, 3, 4, 5, 6, 9 and 10 under "Not verified by anyone" above, and in `payments.md`: a capture that fails part-way, a plan changed after a hold, and a hold older than Stripe keeps one. The server's `.env` is still mode 644.
