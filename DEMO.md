# Tripwright: 3-minute demo script

Scenario: 7 days in Japan. Alex hosts from Kansas City ($2,500) and invites Sam from Chicago ($3,000) and Jo from Dallas ($2,200). On the picks screen Alex marks Tokyo Disneyland and Fushimi Inari Taisha **Must do** and teamLab Planets TOKYO **Interested**; Sam marks Ghibli Museum **Must do**; Jo marks Fushimi Inari Taisha **Must do** and Golden Gai **No** (not for me).

## Before you go on stage

1. `.env` has `OPENAI_API_KEY` (team key) and `TAVILY_API_KEY`. Open `/api/health` and check `inference.key` is true.
2. **Use the demo trip** replays a recorded run of this trip (a live run on 2026-10-10). It works on any server with nothing to switch: each agent shows as working for a few seconds and then shows its recorded result, the top bar says **Recorded run**, and no model or site is asked. The first agents take about 6 seconds, the draft plan about 11 seconds after the last picks are saved, and planning about 10. It replays only while the origin, destination and days are still Kansas City, Japan and 7 when you press **Start planning**; the name and budget can change. Sam and Jo must type **Chicago** and **Dallas**: flights are recorded for those two cities only. From any other city that traveler's flight agent runs live, which takes minutes, and its searches are answered from the recorded ones.
3. To show the agents working live instead, type the trip in by hand: a trip started without the button is planned for real. A cold group run takes about 4 to 5 minutes; with the cache warm the tools answer instantly, but the model calls still take about 2 minutes, so start the planning step before you begin talking about it. Safety net for a live run: set `DEMO_MODE=true` and restart. Tools then replay recorded results and never browse, while the agents still reason live. If inference itself is down, every specialist falls back to its recorded result and the cards say so. The ideas list is recorded too, so the picks screen is not empty; a list saved in the database by an earlier live run (kept for 30 days) is shown first.
4. Have Sam's and Jo's browsers (or phones) ready: each joins from the invite link on their own device.
5. For paying together: `/api/health` says `"payments": "stripe test mode"`, and the Stripe dashboard is open on test-mode Payments in another tab. Safety net: on the hosted site, `#trip_paydemo/p1` (Alex) and `#trip_paydemo/p2` (Sam) open a finished two-traveler trip that nobody has paid yet.
6. Keep the app open on the Start screen, browser at about 1360 px wide. The screen has two panes: the feed on the left asks for each decision, and the board on the right shows the plan, or the agents when you switch its tab.

## Script

**0:00 The pitch (15 s)**

> "Planning a trip means twenty tabs and a spreadsheet. Tripwright is a team of agents that does the research in parallel, shows its reasoning, keeps the source behind every price, and lets you approve every decision. Agents are built on the Strands Agents SDK, and everything runs on Akamai Cloud."

Click **Use the demo trip** (top right), then **Start planning**.

**0:15 Picks (20 s)**

The ideas agent's list of places appears in the feed, grouped by category, with the draft plan beside it.

> "I never typed what I wanted to see. The ideas agent researched Japan and gave me a menu. I mark what I must do, what interests me, and what's not for me, and everyone I invite marks the same list."

Mark Tokyo Disneyland and Fushimi Inari Taisha **Must do**, teamLab Planets TOKYO **Interested**, then **Save my picks** (under the draft plan).

**0:35 Timeframe (15 s)**

Three date windows appear, each with typical weather, crowd level and the cheapest fare the agent actually found. The timeframe agent was working while you picked.

> "I didn't give dates. The timeframe agent checked real fares and three years of weather history for each window. Behind every number is a source URL and a snapshot of the page, saved to Akamai Object Storage."

Click **Choose these dates** on the first window.

**0:50 Who's coming? (20 s)**

> "Now I invite my friends. Each of them opens this link on their own phone, adds where they fly from and their budget, and marks the same list. On that list, every place shows who marked it."

Show the invite link. Sam and Jo join and save their picks; each traveler's card lists their marks, and the draft plan beside it fills in from everyone's. Click **Everyone's in: plan the trip**.

**1:10 Agents in parallel (25 s)**

The feed lists one line per agent, and the board opens on its **Agents** tab: a flight agent for each traveler, plus lodging, attractions, transport and weather, all working side by side. An agent the orchestrator rejects shows **Sent back by the orchestrator** on its card, with the reason.

> "This is one Strands Graph. Each traveler gets their own flight agent, searching from their own city within their own budget. Attractions are planned for the group from everyone's picks. The orchestrator checks every result before accepting it: do the dates match, does every price trace back to a page we actually loaded. For flights and rooms the model never types a price: it picks option ids, and code joins them to the scraped data. Ticket and transport prices it does write, and each one has to cite a page a tool actually loaded."

**1:35 Choose your flight and stays (15 s)**

As soon as Alex's flight and rooms are found, Alex's screen switches to **Choose your flight and stays**.

> "Before any activities are planned, each of us picks our own flight and rooms. The running total shows what's left for everything else."

Pick a different flight, then **Confirm my flight and stays**. The days are planned around it; Sam's and Jo's confirms re-plan them in a second.

**1:50 Review (25 s)**

> "The feed on the left is every decision that needs me, each with its price and the agent's reasoning. I only see my own flight, rooms and transport; the attractions are the group's. Nothing is booked."

- **Needs you:** a must-see that did not fit offers **Swap it in** (pick which activity gives way) or **Drop**.
- **Getting around:** open **Swap** on a leg, or **Add a rental car**: it only changes my plan and my budget.
- Click an activity on the calendar: its card opens at the top of the feed with who needs it, who wants it and who is going.
- Click the tag beside a headline, for example **Flight agent**: the board switches to that agent's card. Click the **Your days** tab at the top of the board to bring the budget bar and calendar back.

Point at the budget bar above the calendar updating by category.

**2:15 Your days (30 s)**

The calendar is on the right, under the budget bar. If the board is still showing the agents, click the **Your days** tab first.

> "The schedule is deterministic code, not the model: opening hours, travel time between stops, everyone's flight times. One shared plan while it fits; if something only one person wants doesn't fit, they split off for it and regroup, and nobody is sent to a place they marked not for me."

Drag a Tokyo activity the whole group is going to (one of the agent's own suggestions, often Senso-ji or Shibuya Crossing; hover it and the tooltip says Everyone) to another Tokyo day: it re-times and re-validates. Drag it onto a Kyoto day:

> "It refuses and tells me why: I'm in Kyoto that day."

**2:45 Finish and pay together (30 s)**

Click **Finish** (top right of **Your days**). At the top is **Pay together**: each traveler and their share. Keep **Visa ···· 4242** selected and click **Approve my share**.

> "Group trips fall apart over money. I approve my share and Stripe places a hold on my card. Nobody is charged until everyone has approved, and if anyone backs out, every hold is released."

On Sam's device, click **Finish**, then **Approve my share**. Both rows turn to **Paid** on both screens. Show the two payments in the Stripe dashboard.

> "Everyone is in, so every card is charged at the same moment. This runs on Stripe test mode: test cards, no real money."

> "This is the hand-off. The flight and hotel links open the provider with my details already in: the flight search on my dates and airline, each hotel's page on my stay dates. Tickets and transport link to the right page, and the step says what to buy there. I just pick and pay."

Click the flight's **Open with details filled in**.

**3:15 Close (5 s)**

> "Strands for the agents, graph, tools, hooks and structured output. Akamai for inference, compute, Postgres and object storage. Tripwright."

## If something goes wrong

- An agent shows **Saved result** (a coral dot beside its name): the live run failed review or timed out, and the card is showing the last accepted result. Say so; it is the designed behaviour.
- An agent shows **Didn't finish**: there was no saved result for that piece. The rest of the plan still completes, and **Retry the N that didn't finish** on the board's Agents tab runs those agents again.
- A site blocks the browser: the tool reports it and the agent uses another source. Booking.com already does this, which is why hotels come from Google Hotels.
