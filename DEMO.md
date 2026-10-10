# Tripwright: 3-minute demo script

Scenario: 7 days in Japan. Alex hosts from Kansas City ($2,500, needs Tokyo Disneyland and Kyoto), and invites Sam from Chicago ($3,000, needs the Ghibli Museum) and Jo from Dallas ($2,200, needs Fushimi Inari).

## Before you go on stage

1. `.env` has `OPENAI_API_KEY` (team key) and `TAVILY_API_KEY`. Open `/api/health` and check `inference.key` is true.
2. Plan the demo trip once beforehand. A cold group run takes about 4 to 5 minutes; with the cache warm the tools answer instantly, but the model calls still take about 2 minutes, so start the planning step before you begin talking about it.
3. Safety net: set `DEMO_MODE=true` and restart. Tools then replay recorded results and never browse, while the agents still reason live. If inference itself is down, every specialist falls back to its recorded result and the cards say so.
4. Keep the app open on the new-trip form, browser at about 1360 px wide.

## Script

**0:00 The pitch (15 s)**

> "Planning a trip means twenty tabs and a spreadsheet. Tripwright is a team of agents that does the research in parallel, shows its evidence, and lets you approve every decision. Agents are built on the Strands Agents SDK, and everything runs on Akamai Cloud."

Click **Use the demo trip**, then **Plan my trip**.

**0:15 Timeframe (25 s)**

Three date windows appear, each with typical weather, crowd level and the cheapest fare the agent actually found.

> "I didn't give dates. The timeframe agent researched crowds and seasons, then checked real fares and three years of weather history for each window. The cheapest window is hundreds of dollars below the others. Behind every number is a source URL and a snapshot of the page, saved to Akamai Object Storage."

Point at the route lane: the route planner proposes the cities, and the orchestrator's code makes the nights add up and ends the route with a last night in Tokyo for the flight home. Then click **Choose these dates** on the first window.

**0:40 Who's coming? (20 s)**

> "Now I invite my friends. Each of them opens this link and adds where they fly from, their budget, and what they need versus want to see."

Show the invite link, add Sam and Jo with **Add a traveler here** (or have a teammate join from their phone), then click **Everyone's in: plan the trip**.

**1:00 Agents in parallel (40 s)**

The agent panel shows a flight agent for each traveler, plus lodging, attractions, transport and weather, all working side by side.

> "This is one Strands Graph. Each traveler gets their own flight agent, searching from their own city within their own budget. Lodging and attractions are planned for the group: everyone's needs and wants go in together. Every specialist has its own headless browser session on our Akamai VM. Watch the status pills: working, under review, accepted. The orchestrator checks every result before accepting it: do the dates match, does every price trace back to a page we actually loaded, is it within that category's share of the budget. When something fails, it is sent back with specific feedback, up to twice. The model never types a price: it picks option ids, and code joins them to the scraped data."

Point at a **sent back** pill if one appears, and at the tool calls scrolling in a lane. Then budget, scheduler and validate run in sequence.

**1:40 Review (35 s)**

> "Every decision is a card with its price and the agent's reasoning. Nothing is booked. The link takes me to the provider to finish myself."

- Flight card: read one tradeoff line, open **Swap** to show the other two options.
- Lodging: "I was never asked hotel or Airbnb. The agent researched what most travelers pick here and why." Click **Switch to Airbnb**.

> "Only the lodging agent re-runs. Then budget, scheduler and validation run again. And that override is now a stated preference in my traveler profile for the next trip."

Point at the budget bar updating by category.

**2:15 Itinerary (30 s)**

Open the **Itinerary** tab.

> "The schedule is deterministic code, not the model: opening hours, travel time between stops, everyone's flight times. The goal is the fewest itineraries that meet the most preferences: one shared plan while it fits, and if something only one person needs doesn't fit, they split off for it and regroup. I can switch the view to any one traveler."

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
