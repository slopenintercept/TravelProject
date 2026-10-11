# Handoff: paying together (the payments chat)

Written 2026-10-11 at about 05:20 Central by the chat that built payments. It is for a chat that checks this work and the other chats' work. Nothing in this file asks you to build anything. Read "Start here" and "Gotchas" in `HANDOFF.md` first.

The other handoffs are `map.md`, `lodging-over-budget.md` and `ideas-lost-task.md` in this folder; each has a `## Result` section written by the chat that did the work.

## What the user asked for

The team is entering the "Best FinTech App" challenge at Hack Midwest. In order:

1. They asked what exists for letting someone connect a card and pay through a Strands agent. Nothing for cards does; I recommended a group payment feature instead.
2. They chose "group holds, all or nothing", and said: "we don't use to actually credit card infos thats not allowed its a demo not actually spending money".
3. They agreed to Stripe test mode ("im down to do the ... Stripe option"), made a restricted test key, pasted it into the chat and said "go ahead".
4. At about 05:09: "make sure that this will also run the live server, make sure it does once it does, commit changes ... everything is update to date and isnt running on old code and remember to commit and push onto github. But do all of this accoridng to the agents that are working right now make sure u dont break anything".

## What was built

On the Finish screen, above "Your bookings", a **Pay together** box (on a solo trip it is headed "Pay for your trip").

- Each traveler approves their own share on a test card picked from a list of three. No card number is typed.
- A share is that traveler's budget total, `state.budgets[id].spent_usd`.
- Approving places a hold. When every traveler has a hold, all are charged at once.
- Anyone on the trip can back out before that. Backing out releases every hold.
- The third card always declines: no hold is placed and the traveler can pick another.
- No LLM is involved. `payments.py` is plain Python, like `budget.py`.

With `STRIPE_SECRET_KEY` set, each hold is a Stripe test-mode PaymentIntent created with `capture_method="manual"` and confirmed with one of Stripe's test payment methods (`pm_card_visa`, `pm_card_mastercard`, `pm_card_visa_chargeDeclined`). Charging is `capture`; releasing is `cancel`. Without the key the same steps only change the trip's own state. A key that does not start with `sk_test_` or `rk_test_` is refused when a payment is attempted.

| Where | What |
|---|---|
| `backend/tripwright/payments.py` | `CARDS`, `approve`, `back_out`, `_intents` (the Stripe client, or `None`) |
| `backend/tripwright/models.py` | `Payment` (`card`, `amount_usd`, `status`, `ref`) and `TripState.payments`, keyed by traveler id |
| `backend/tripwright/api.py` | `POST` and `DELETE /api/trips/{id}/payments`, `_pay`, and `"payments"` in `/api/health` |
| `backend/tripwright/config.py`, `backend/pyproject.toml` | `STRIPE_SECRET_KEY`; `stripe==16.0.0` |
| `backend/tests/test_payments.py`, `conftest.py` | 8 tests; `conftest.py` blanks the key so tests never call Stripe |
| `frontend/src/components/Pay.tsx` | The box |
| `Finish.tsx`, `App.tsx`, `api.ts`, `types.ts`, `styles.css` | Wiring, types, and a `.shares` block of styles |

`Payment.status` is `held`, `captured`, `declined` or `released`. `ref` is the PaymentIntent id, or empty when Stripe was not used.

## Commits

All on `combine-picks-and-group-trips`, all pushed. `main` was not touched.

| Commit | What | Whose work |
|---|---|---|
| `b276145` | Pay together | Mine |
| `2b24e5b` | The map on the draft plan | The map chat's |
| `fd4cd2e` | Lodging takes the cheapest room when none fits the budget | The lodging chat's |
| `29f5a53` | Specialists keep their task when Strands trims the conversation | The ideas chat's |
| `db7bb5a` | A handoff update | Made by the "HANDOFF and README review" chat, not by me |
| `a144dea` | README, `DEMO.md` and `.env.example` for payments | Mine |
| `21a2aa1` | `HANDOFF.md`: deployed, pushed, port 8000 restarted | Mine |

## What I ran, and what it showed

1. **Backend tests.** 111 passed before my work, 119 with my 8, and 126 on the folder with all four pieces of work in it. Last run after `a144dea`: 126 passed.
2. **Frontend.** `npx tsc --noEmit` and `npm run build` passed on the folder that became `29f5a53`.
3. **Clicked through in the browser, holds kept in the app** (no key yet). A second backend on port 8003 read a throwaway copy of the local database. On `trip_99aaaeb1`, in two tabs:
   - Alex approved with Visa: his row read "On hold", the chip "1 of 2 approved".
   - The second traveler used the declining card: "was declined", and Alex's hold stayed.
   - The second traveler used Visa: both rows read "Paid", and Alex's tab changed with no reload.
   - On `trip_03e9231a`: a hold, then backing out, gave "Hold released"; a second back-out answered 400.
4. **Real Stripe test mode, locally** (port 8003, trip copy `trip_stripe1`). I drove the two routes with `fetch` from the page, then asked Stripe for each PaymentIntent:
   - `pi_3UPJaUHaJ64YkgVD1GQzv0jr`: `requires_capture` after the hold, `canceled` after backing out.
   - `pi_3UPJalHaJ64YkgVD0mqElKhh` and `pi_3UPJamHaJ64YkgVD0coopRl0`: `succeeded`, $2,155.79 and $1,579.09.
   - The declining card raised Stripe's card error and no hold was placed.
   - All `livemode` false. The Finish screen then read "Trip paid" and "Runs on Stripe test mode".
5. **Stripe's first answer was a refusal.** It no longer accepts `payment_method_types`. The call now sends `automatic_payment_methods` with `allow_redirects: "never"`. The refusal reached the screen as a readable 400 and changed nothing in the trip.
6. **The hosted site, after the deploy** (about 05:14), with `curl` on `trip_paycheck`: hold, declined card, back out, hold again, second traveler approves. Stripe reported:
   - `pi_3UPJmYHaJ64YkgVD1Sn8Lcl3`: `canceled`, nothing received.
   - `pi_3UPJmcHaJ64YkgVD0QXPqSZS` and `pi_3UPJmdHaJ64YkgVD1mO691A3`: `succeeded`, $2,737.35 and $2,914.35.
7. **The hosted site in the browser.** `#trip_paydemo/p1` on Finish at 1360 px showed the box with "0 of 2 approved" and no console errors. I did not click Approve there.

## What I did outside my own files

Check these first; they are where I could have broken someone else's work.

- **I committed three other chats' work.** I read each `## Result` section, ran the whole suite (126 passed) and the type check, then made one commit for each. `types.ts` and `styles.css` held both the map's lines and mine, so I staged my hunks alone with `git apply --cached` for `b276145` and the rest went into `2b24e5b`.
- **A second chat was about to commit the same work.** The "HANDOFF and README review" chat had already written into `HANDOFF.md` that the map's lines were committed. My commits landed at 05:12, just before its own. It then committed `db7bb5a`. My message telling it what I had done was held by that session and never delivered. I have not checked that `db7bb5a` and my later edits to `HANDOFF.md` agree with each other everywhere.
- **I deployed the working folder** at about 05:11 with `deploy/deploy.sh`. Before it, the hosted log for the last 10 minutes showed only my own request, and `trip_f24799b6` was `awaiting_dates` and not busy. After it, `/api/health` said `"payments": "stripe test mode"`, and the JavaScript the server serves had the same SHA-256 as the local `frontend/dist` build.
- **I restarted the local server on port 8000** at about 05:13. `trip_479d20ea` was at `choosing` and not busy. I killed pid 82669, which another chat's terminal tab had started at 04:17, and started the same command in a Terminal tab titled "Tripwright :8000".
- **I added two trips to the hosted database**, both copies of local `trip_99aaaeb1` with traveler `p2` renamed from "friend2" to "Sam":
  - `trip_paydemo`: unpaid. It is the safety net named in `DEMO.md`. Leave it unpaid.
  - `trip_paycheck`: paid, by the check in point 6 above.
- **I wrote `STRIPE_SECRET_KEY` into `.env`.** The user pasted the key into the chat, so it is in that chat's transcript. It is a restricted test key ("full access except sensitive operations").
- **I made six test PaymentIntents** in the user's Stripe test account, listed above.
- **I rebuilt `frontend/dist`** several times; the last build is from the folder that became `29f5a53`.
- **I edited docs other chats wrote:** `README.md` (the Finish row, one safety bullet, one layout line), `DEMO.md` (a checklist item and the Finish step) and `HANDOFF.md` (12 replacements; the diff of `21a2aa1` shows each).
- **`.claude/launch.json`:** I added and later removed `tripwright-pay`. The map chat's two entries are still there, uncommitted.

## State when this was written

- **GitHub:** `combine-picks-and-group-trips` is at `21a2aa1`. `main` is at `d292b70`, without payments, the map or the two fixes.
- **Hosted site:** runs `backend/` and `frontend/` as of `29f5a53`. Later commits changed docs only.
- **Local:** one app server, on port 8000, on SQLite and local disk, with Stripe test mode on. The server on port 8003 is stopped.
- **Uncommitted:** this file, and `.claude/launch.json` (the map chat's two test entries).

## How to check it

1. `cd backend && .venv/bin/python -m pytest -q` gives 126 passed. `tests/test_payments.py` alone gives 8.
2. `git diff 29f5a53 HEAD --stat -- backend frontend` prints nothing, so the deployed code is the committed code.
3. `/api/health` on port 8000 and on the hosted site both say `"payments": "stripe test mode"`.
4. On the hosted site, `GET /api/trips/trip_paycheck` shows both travelers `captured` with a `ref`, and `GET /api/trips/trip_paydemo` shows `"payments": {}`.
5. Ask Stripe about a PaymentIntent without printing the key:

   ```bash
   cd backend && .venv/bin/python -c "import stripe; from tripwright import config; pi = stripe.StripeClient(config.STRIPE_SECRET_KEY).v1.payment_intents.retrieve('pi_3UPJmcHaJ64YkgVD0QXPqSZS'); print(pi.status, pi.amount, pi.livemode)"
   ```

6. To click through the box yourself, use a second backend on a throwaway copy of the database. "Gotchas" in `HANDOFF.md` says how. With the key in `.env`, that backend makes real test PaymentIntents.
7. Nothing secret is in the pushed commits. My scan of `6c7abf8..a144dea` for key and database-address patterns had one hit: line 58 of `deploy/provision.sh`, which builds the address from shell variables.

## Not done, or not checked

- **With Stripe on, nobody has clicked Approve in the browser.** Points 4 and 6 above drove the routes directly; the clicks in point 3 were without a key.
- **I did not open the Stripe dashboard.** The statuses above came from Stripe's API.
- **A solo trip is untested.** `approve` charges at once when there is one traveler; no test or browser run covers it.
- **Three or more travelers were not run.** The tests and the browser runs use two.
- **A capture that fails part-way is not handled.** If Stripe refuses the second capture, the first traveler stays charged, the rest stay on hold, and the trip then refuses every further change as "already paid".
- **A hold keeps the amount it was placed for.** A change to the plan in Review afterwards does not move it.
- **Holds never expire in the app.** Stripe releases a card authorization after about 7 days; the app would still show "On hold".
- **If the key is removed while a Stripe hold exists,** backing out marks the hold released in the trip and does not cancel it at Stripe.
- **After capture the money goes nowhere.** A real product would pass it to a booking API.
- **After the deploy I opened only the Finish screen** on the hosted site. Picks with the map, the lodging fix and the ideas fix were not looked at there by me, and no full planning run was made.
- **`DEMO.md` now runs to about 3:20**; its title still says 3 minutes.
- **`HANDOFF.md`'s "Updated" line** at the top was not changed by me.
- **My doc edits had no second reader.**

## Open with the user

1. Whether to move `main` up to the branch. I offered; they had not answered.
2. The Finish screen is one of the six screens without a mockup that the user has not signed off. Payments added a section to it.
3. The Stripe key is in a chat transcript. It is test-only. I told the user to delete it in Stripe after the hackathon.

## Cautions

- Never print `.env` or `.env.hosted`. The hosted site's address is left out of the repo on purpose.
- Do not approve or back out on `trip_paydemo`.
- Restarting a server stops any trip being planned on it. Check `busy` first.
