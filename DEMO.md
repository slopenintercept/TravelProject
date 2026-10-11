# Tripwright: 3-minute demo script

Scenario: 7 days in Japan from Kansas City, $2,500 total. On the picks screen, mark Tokyo Disneyland and Fushimi Inari Taisha (Kyoto) **Must do** and teamLab Planets **Interested**.

## Before you go on stage

1. `.env` has `OPENAI_API_KEY` (team key) and `TAVILY_API_KEY`. Open `/api/health` and check `inference.key` is true.
2. Plan the demo trip once beforehand. A cold run takes about 3 minutes (most of it Google Flights page loads for the date windows); with the cache warm, the tools answer instantly and only the model calls remain.
3. Safety net: set `DEMO_MODE=true` and restart. Tools then replay recorded results and never browse, while the agents still reason live. If inference itself is down, every specialist falls back to its recorded result and the cards say so. The ideas list has no recorded result until someone plans the demo trip once with `RECORD_FIXTURES=true`; without one, the picks screen is empty and you add the three places by hand with **Add a place**.
4. Keep the app open on the new-trip form, browser at about 1360 px wide.

## Script

**0:00 The pitch (15 s)**

> "Planning a trip means twenty tabs and a spreadsheet. Tripwright is a team of agents that does the research in parallel, shows its evidence, and lets you approve every decision. Agents are built on the Strands Agents SDK, and everything runs on Akamai Cloud."

Click **Use the demo trip**, then **Plan my trip**.

**0:15 Picks (20 s)**

The ideas agent's list of places appears, grouped by category.

> "I never typed what I wanted to see. The ideas agent researched Japan and gave me a menu. I mark what I must do, what interests me, and what's not for me, and everyone I invite marks the same list."

Mark Tokyo Disneyland and Fushimi Inari **Must do**, teamLab Planets **Interested**, then **Save my picks**.

**0:35 Timeframe (20 s)**

Three date windows appear, each with typical weather, crowd level and the cheapest fare the agent actually found. The timeframe agent was working while you picked.

> "I didn't give dates. The timeframe agent researched crowds and seasons, then checked real fares and three years of weather history for each window. The cheapest window is hundreds of dollars below the others. Behind every number is a source URL and a snapshot of the page, saved to Akamai Object Storage."

Click **Choose these dates** on the first window, then **Everyone's in: plan the trip**.

**0:55 Agents in parallel (35 s)**

The route planner runs first, from your picks: point at its **attempt 2** if it appears (it usually proposes Tokyo then Kyoto, and the orchestrator sends it back to add a last night in Tokyo for the flight home).

The agent panel shows flight, lodging, attractions, transport and weather working side by side.

> "This is one Strands Graph. Five specialists run at once, each with its own headless browser session on our Akamai VM. Watch the status pills: working, under review, accepted. The orchestrator checks every result before accepting it: do the dates match, does every price trace back to a page we actually loaded, is it within that category's share of the budget. When something fails, it is sent back with specific feedback, up to twice. The model never types a price: it picks option ids, and code joins them to the scraped data."

Point at a **sent back** pill if one appears, and at the tool calls scrolling in a lane. Then budget, scheduler and validate run in sequence.

**1:30 Review (45 s)**

> "Every decision is a card with its price and the agent's reasoning. Nothing is booked. The link takes me to the provider to finish myself."

- Flight card: read one tradeoff line, open **Swap** to show the other two options.
- Lodging: "I was never asked hotel or Airbnb. The agent researched what most travelers pick here and why." Click **Switch to Airbnb**.

> "Only the lodging agent re-runs. Then budget, scheduler and validation run again. And that override is now a stated preference in my traveler profile for the next trip."

Point at the budget bar updating by category.

**2:15 Itinerary (30 s)**

Open the **Itinerary** tab.

> "The schedule is deterministic code, not the model: opening hours, travel time between stops, flight times, hotel check-in. Disneyland is outdoors, so it landed on the driest Tokyo day."

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
