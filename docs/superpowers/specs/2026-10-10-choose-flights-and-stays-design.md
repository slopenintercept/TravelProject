# Choose flights and stays before activities

Date: 2026-10-10. Status: approved in conversation.

## Goal

Each traveler chooses their own flight and rooms before the trip's activities are planned, so the days are built around confirmed arrival and departure times and hotels. Activities are planned as soon as anyone confirms and adjust as others confirm.

## Decisions

| Question | Decision |
| --- | --- |
| When are activities planned in a group? | As soon as anyone confirms. Later confirms re-plan the days. |
| When do the activity agents run? | In the background at the same time as flights and lodging (they depend only on dates, route and picks). Their results are revealed and scheduled after the first confirm. |
| Who hasn't confirmed yet | Counts with the agent's top pick, and sees their Choose screen first even after the group's days exist. |
| Changes later | The review page's existing swaps still work and re-plan the days. |

## Flow

1. "Everyone's in: plan the trip" → the route is re-planned from everyone's picks (stage `planning`).
2. Stage `choosing`: flight per traveler, lodging, attractions, transport and weather run in parallel, without the scheduler.
3. Each traveler sees "Planning your flight and stays…" until their own flight and lodging agents finish, then **Choose your flight and stays**: flight options (top pick preselected), each stay's room options (budget-matched room preselected), and a running total "Flight + stays: $X of your $Y budget, leaving $Z for activities and getting around". Button: **Confirm my flight and stays**.
4. On confirm:
   - research still running → the choice is saved; the confirmer sees "Planning activities around your choices…"; when research ends, scheduler → budget → validate run and the stage becomes `review`;
   - research done → scheduler → budget → validate run now; stage `review`.
5. Each later confirm re-runs scheduler → budget → validate.
6. Unconfirmed travelers see their Choose screen first, with "The group's days are already planned; they'll adjust to your choices when you confirm." when the stage is `review`.

Failures: no flight options → the screen says so and the traveler confirms stays only. Saved-result fallbacks are flagged as today.

## Data and API

- `Traveler.confirmed: bool = False`. `TripState.stage` gains `"choosing"`.
- `orchestrator.confirm_choices(state, traveler_id, flight_id: str | None, stay_ids: list[str])` raises `ValueError` for: a flight id not among the traveler's options (`"That flight is not one of your options"`), a stay count that differs from the traveler's stays (`"Choose one room for each stay"`), a room not among that stay's options (`"That room is not an option for the {city} stay"`). Sets selections and `confirmed = True`.
- `planning_graph(specialists, schedule=True)`; `schedule=False` builds the research-only graph.
- `PUT /api/trips/{id}/travelers/{traveler_id}/choices` body `{flight_id: str | None, stay_ids: list[str]}`:
  - 403 unless `X-Traveler` is `traveler_id`;
  - 400 `"Planning hasn't started yet"` unless the stage is `choosing` or `review`;
  - 400 `"Your options are still being found"` while `flight:<traveler>` or `lodging` is working / under review / sent back;
  - research running (trip lock held) → save only; otherwise re-plan under the lock and set stage `review`.

## Testing

Backend: plan stops at `choosing` with nobody confirmed; plan schedules and reaches `review` when someone confirmed during research; confirm validation (flight, stay count, room); API ownership, pending options, stage gate, confirm after research schedules and moves to `review`, a second confirm re-schedules. Frontend: type-check, build, browser run.
