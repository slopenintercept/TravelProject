# Tripwright: 3-minute demo script

Scenario: 7 days in Japan. Alex hosts from Kansas City ($2,500) and invites Sam from Chicago ($3,000) and Jo from Dallas ($2,200). On the picks screen Alex marks Tokyo Disneyland and Fushimi Inari Taisha **Must do** and teamLab Planets **Interested**; Sam marks the Ghibli Museum **Must do**; Jo marks Fushimi Inari **Must do** and Shinjuku Golden Gai **Not for me**.

## Before you go on stage

1. `.env` has `OPENAI_API_KEY` (team key) and `TAVILY_API_KEY`. Open `/api/health` and check `inference.key` is true.
2. Plan the demo trip once beforehand. A cold group run takes about 4 to 5 minutes; with the cache warm the tools answer instantly, but the model calls still take about 2 minutes, so start the planning step before you begin talking about it.
3. Safety net: set `DEMO_MODE=true` and restart. Tools then replay recorded results and never browse, while the agents still reason live. If inference itself is down, every specialist falls back to its recorded result and the cards say so. The ideas list has no recorded result until someone plans the demo trip once with `RECORD_FIXTURES=true`; without one, the picks screen is empty and you add the places by hand with **Add a place**.
4. Have Sam's and Jo's browsers (or phones) ready: each joins from the invite link on their own device.
5. Keep the app open on the new-trip form, browser at about 1360 px wide.

## Script

**0:00 The pitch (15 s)**

> "Planning a trip means twenty tabs and a spreadsheet. Tripwright is a team of agents that does the research in parallel, shows its evidence, and lets you approve every decision. Agents are built on the Strands Agents SDK, and everything runs on Akamai Cloud."

Click **Use the demo trip**, then **Plan my trip**.

**0:15 Picks (20 s)**

The ideas agent's list of places appears, grouped by category.

> "I never typed what I wanted to see. The ideas agent researched Japan and gave me a menu. I mark what I must do, what interests me, and what's not for me, and everyone I invite marks the same list."

Mark Tokyo Disneyland and Fushimi Inari **Must do**, teamLab Planets **Interested**, then **Save my picks**.

**0:35 Timeframe (15 s)**

Three date windows appear, each with typical weather, crowd level and the cheapest fare the agent actually found. The timeframe agent was working while you picked.

> "I didn't give dates. The timeframe agent checked real fares and three years of weather history for each window. Behind every number is a source URL and a snapshot of the page, saved to Akamai Object Storage."

Click **Choose these dates** on the first window.

**0:50 Who's coming? (20 s)**

> "Now I invite my friends. Each of them opens this link on their own phone, adds where they fly from and their budget, and marks the same list. Every place shows how many of us want it."

Show the invite link. Sam and Jo join and save their picks; their marks appear on the list. Click **Everyone's in: plan the trip**.

**1:10 Agents in parallel (25 s)**

The agent panel shows a flight agent for each traveler, plus lodging, attractions, transport and weather, all working side by side.

> "This is one Strands Graph. Each traveler gets their own flight agent, searching from their own city within their own budget. Attractions are planned for the group from everyone's picks. The orchestrator checks every result before accepting it: do the dates match, does every price trace back to a page we actually loaded. The model never types a price: it picks option ids, and code joins them to the scraped data."

**1:35 Choose your flight and stays (15 s)**

As soon as Alex's flight and rooms are found, Alex's screen switches to **Choose your flight and stays**.

> "Before any activities are planned, each of us picks our own flight and rooms. The running total shows what's left for everything else."

Pick a different flight, then **Confirm my flight and stays**. The days are planned around it; Sam's and Jo's confirms re-plan them in a second.

**1:50 Review (25 s)**

> "Every decision is a card with its price and the agent's reasoning. I only see my own flight, rooms and transport; the attractions are the group's. Nothing is booked."

- Transport: open **Swap** on a leg, or **Add a rental car**: it only changes my plan and my budget.
- Attractions: point at **Must do: 2 of 3** and at Golden Gai missing, because Jo marked it not for me.

Point at the budget bar updating by category.

**2:15 Itinerary (30 s)**

Open the **Itinerary** tab.

> "The schedule is deterministic code, not the model: opening hours, travel time between stops, everyone's flight times. One shared plan while it fits; if something only one person wants doesn't fit, they split off for it and regroup, and nobody is sent to a place they marked not for me."

Drag **Senso-ji** to another Tokyo day: it re-times and re-validates. Drag it onto a Kyoto day:

> "It refuses and tells me why: I'm in Kyoto that day."

**2:45 Finish (10 s)**

Click **Finish** (bottom right).

> "This is the hand-off. Every link opens the provider with my details already in: the flight search on my dates and airline, each hotel's page on my stay dates. I just pick and pay."

Click the flight's **Open with details filled in**.

**2:55 Close (5 s)**

> "Strands for the agents, graph, tools, hooks and structured output. Akamai for inference, compute, Postgres and object storage. Tripwright."

## If something goes wrong

- A lane shows **fallback**: the live run failed review or timed out, and the card is showing the last accepted result. Say so; it is the designed behaviour.
- A lane shows **pending**: there was no saved result for that piece. The rest of the plan still completes.
- A site blocks the browser: the tool reports it and the agent uses another source. Booking.com already does this, which is why hotels come from Google Hotels.
