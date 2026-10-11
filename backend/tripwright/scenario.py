"""A ready-made group trip for trying the flow as an extra traveler.

Seven friends have joined a 7-day Japan trip and marked the shared list of places. There is a strong
shared core (Fushimi Inari, Tsukiji, teamLab, Arashiyama, a night out in Shinjuku) and a few pairs
who need the same side outing, so the plan will likely split and regroup:

    Maya + Priya    Ghibli Museum            Jordan + Chris   Hakone day trip
    Taylor + Sam    Tokyo DisneySea (a day)  Alex alone       sumo morning practice

Dates are set and the trip is waiting for people to join, so you can open the invite link, join as
the eighth traveler, mark the list and see how your picks fit with everyone else's. Alex is the host:
switch to Alex to start planning.

    cd backend
    .venv/Scripts/python -m tripwright.scenario     (Windows; .venv/bin/python elsewhere)

Each run creates a new trip and prints its links. No agents run until the host starts planning.
"""

from __future__ import annotations

from datetime import date

from . import store
from .models import (
    AgentStatus, Idea, RoutePlan, RouteSegment, Traveler, TripDates, TripRequest, TripState, new_id,
)

START = date(2027, 4, 5)  # cherry blossom season; 7 days: land Apr 6, fly home Apr 12

# name, city, category, why
PLACES = [
    ("Shibuya Crossing & Shibuya Sky", "Tokyo", "Sights", "The famous scramble crossing, then the rooftop deck above it at sunset."),
    ("Senso-ji Temple", "Tokyo", "Culture", "Tokyo's oldest temple, with the Nakamise street-food lane leading up to it."),
    ("Meiji Jingu Shrine", "Tokyo", "Culture", "A forested shrine in the middle of the city, a calm hour next to Harajuku."),
    ("teamLab Planets", "Tokyo", "Sights", "Walk-through digital art rooms, some knee-deep in water; book a time slot."),
    ("Tsukiji Outer Market", "Tokyo", "Food", "Morning sushi, tamagoyaki and grilled seafood from the market stalls."),
    ("Omoide Yokocho", "Tokyo", "Food", "A smoky alley of tiny yakitori counters by Shinjuku Station."),
    ("Shinjuku Golden Gai", "Tokyo", "Nightlife", "Six lanes of bars that seat eight people each; a classic group night out."),
    ("Karaoke night in Shinjuku", "Tokyo", "Nightlife", "A private karaoke room for the whole group, open until morning."),
    ("Ghibli Museum", "Tokyo", "Family", "Studio Ghibli's own museum in Mitaka; tickets sell out a month ahead."),
    ("Akihabara", "Tokyo", "Shopping", "Anime, retro games and arcades across several floors per building."),
    ("Harajuku & Takeshita Street", "Tokyo", "Shopping", "Street fashion, crepes and quirky shops in a short, packed street."),
    ("Tokyo DisneySea", "Tokyo", "Family", "The Disney park built for adults: a full day of rides and harbor shows."),
    ("Sumo morning practice", "Tokyo", "Culture", "Watch wrestlers train up close at a Ryogoku stable, early in the morning."),
    ("Shinjuku Gyoen", "Tokyo", "Nature", "A huge garden that is one of Tokyo's best cherry blossom spots in April."),
    ("Hakone day trip", "Hakone", "Day trips", "Hot springs, the ropeway over volcanic vents and Lake Ashi with Mt Fuji views."),
    ("Kamakura day trip", "Kamakura", "Day trips", "The Great Buddha, seaside temples and a coastal train ride."),
    ("Fushimi Inari Taisha", "Kyoto", "Culture", "Thousands of red torii gates winding up the mountain; go early or late."),
    ("Kinkaku-ji", "Kyoto", "Sights", "The Golden Pavilion reflected in its pond."),
    ("Arashiyama Bamboo Grove", "Kyoto", "Nature", "The bamboo forest path, with Tenryu-ji's garden right beside it."),
    ("Kiyomizu-dera", "Kyoto", "Culture", "A hillside temple with a wooden stage over the cherry trees."),
    ("Nishiki Market", "Kyoto", "Food", "Kyoto's covered food street: pickles, mochi, skewers and matcha."),
    ("Gion evening walk", "Kyoto", "Culture", "Lantern-lit lanes of the geisha district after dark."),
    ("Tea ceremony in Kyoto", "Kyoto", "Culture", "A short traditional tea ceremony in a Kyoto townhouse."),
    ("Nara day trip", "Nara", "Day trips", "Bowing deer in Nara Park and the giant Buddha at Todai-ji."),
]

# name, flies from, budget, must do, interested, not for me
FRIENDS = [
    ("Alex", "Kansas City", 3000,
     ["Fushimi Inari Taisha", "Sumo morning practice", "Kinkaku-ji"],
     ["Tsukiji Outer Market", "Shinjuku Golden Gai", "Shibuya Crossing & Shibuya Sky", "Arashiyama Bamboo Grove",
      "Nishiki Market"],
     ["Harajuku & Takeshita Street"]),
    ("Maya", "Chicago", 2800,
     ["Fushimi Inari Taisha", "Ghibli Museum", "teamLab Planets"],
     ["Akihabara", "Tsukiji Outer Market", "Arashiyama Bamboo Grove", "Kiyomizu-dera", "Harajuku & Takeshita Street"],
     ["Sumo morning practice"]),
    ("Jordan", "Denver", 3500,
     ["Hakone day trip", "Fushimi Inari Taisha", "Shinjuku Golden Gai"],
     ["Arashiyama Bamboo Grove", "Tsukiji Outer Market", "Omoide Yokocho", "Karaoke night in Shinjuku"],
     ["Harajuku & Takeshita Street", "Akihabara", "Ghibli Museum"]),
    ("Priya", "New York", 3200,
     ["Ghibli Museum", "Fushimi Inari Taisha", "Tea ceremony in Kyoto"],
     ["teamLab Planets", "Kiyomizu-dera", "Gion evening walk", "Nishiki Market", "Meiji Jingu Shrine"],
     ["Shinjuku Golden Gai", "Karaoke night in Shinjuku"]),
    ("Chris", "Denver", 2600,
     ["Hakone day trip", "Arashiyama Bamboo Grove"],
     ["Fushimi Inari Taisha", "Tsukiji Outer Market", "Shinjuku Golden Gai", "Karaoke night in Shinjuku",
      "Shinjuku Gyoen"],
     ["Tokyo DisneySea", "Akihabara"]),
    ("Taylor", "Los Angeles", 4000,
     ["Tokyo DisneySea", "teamLab Planets", "Shibuya Crossing & Shibuya Sky"],
     ["Fushimi Inari Taisha", "Harajuku & Takeshita Street", "Shinjuku Golden Gai", "Karaoke night in Shinjuku",
      "Nishiki Market"],
     ["Sumo morning practice", "Hakone day trip"]),
    ("Sam", "Seattle", 2400,
     ["Tokyo DisneySea", "Fushimi Inari Taisha"],
     ["Tsukiji Outer Market", "teamLab Planets", "Akihabara", "Kinkaku-ji", "Nara day trip"],
     ["Tea ceremony in Kyoto"]),
]


def friend_trip() -> TripState:
    names = {name for name, *_ in PLACES}
    travelers = []
    for i, (name, origin, budget, need, want, skip) in enumerate(FRIENDS, 1):
        unknown = set(need + want + skip) - names
        assert not unknown, f"{name} marked places that aren't on the list: {unknown}"
        travelers.append(Traveler(id=f"p{i}", host=i == 1, name=name, origin=origin, budget_usd=budget,
                                  need=need, want=want, skip=skip, picked=True))
    host = travelers[0]
    request = TripRequest(name=host.name, origin=host.origin, budget_usd=host.budget_usd, destination="Japan", days=7,
                          start_date=START, pace="balanced")
    return TripState(
        id=new_id("trip"), request=request, stage="gathering", travelers=travelers,
        ideas=[Idea(id=f"i{n}", name=name, city=city, category=category, why=why)
               for n, (name, city, category, why) in enumerate(PLACES, 1)],
        # A first sketch; planning re-plans the route from everyone's picks and reads the landing day from flights.
        route=RoutePlan(segments=[RouteSegment(city="Tokyo", nights=3), RouteSegment(city="Kyoto", nights=2),
                                  RouteSegment(city="Tokyo", nights=1)], arrival_day_offset=1),
        dates=TripDates(start=START, arrival=date(2027, 4, 6), end=date(2027, 4, 12)),
        agents={"ideas": AgentStatus(agent="ideas", status="accepted", attempt=1, message="Seeded scenario",
                                     found=f"{len(PLACES)} places to choose from")},
    )


if __name__ == "__main__":
    state = friend_trip()
    store.save_trip(state)
    base = "http://localhost:8000/"
    print(f"Created {state.id}: {len(state.travelers)} friends, {len(state.ideas)} places, "
          f"{state.dates.start:%a %b %d} to {state.dates.end:%a %b %d}.")
    print(f"  Join as the 8th traveler:  {base}#{state.id}/join")
    print(f"  Host (Alex), to start:     {base}#{state.id}/p1")
    print(f"  See everyone:              {base}#{state.id}")
