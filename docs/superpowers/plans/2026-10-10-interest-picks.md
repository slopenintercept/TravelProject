# Interest Picks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the typed "need / want to see" fields with an agent-suggested list of places that each traveler marks must do / interested / not for me, and plan from those marks.

**Architecture:** A new `ideas` specialist (same `Spec` + `SpecialistNode` machinery as the others) runs in stage 1 and fills `TripState.ideas`. Marks are stored on each `Traveler` as the existing `need` / `want` name lists plus a new `skip` list, so the planning agents keep working from `wishes()`. The scheduler drops skippers from shared activities and lets them split off for their own picks.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic 2, Strands Agents 1.59.0, pytest; React 19 + TypeScript + Vite.

**Spec:** `docs/superpowers/specs/2026-10-10-interest-picks-design.md`

## Global Constraints

- Do not commit. The user asked for no commits; leave every change in the working tree. (This replaces the usual commit step in each task.)
- Run backend commands from `backend/` with `.\.venv\Scripts\python.exe -m pytest`; frontend from `frontend/` with `npx --no-install tsc --noEmit -p .` and `npm run build`.
- Marks: `must do` → `Traveler.need`, `interested` → `Traveler.want`, `not for me` → `Traveler.skip`. A name is in at most one of the three for a traveler.
- Ideas list size: 12-25 accepted; the agent is asked for 15-25.
- Places a person adds: `Idea.category = "Added by the group"`, `source = None`, `added_by = <traveler id>`.
- Picks and add-a-place are refused (400) once `stage` is `planning` or `review`, and while the ideas agent is still running.
- Existing tests keep passing; `TravelerIn.need` / `want` keep their `[]` defaults.

## Review Focus

1. Adding a place that differs only in case or spacing from one on the list ("tokyo  disneyland") → refused as a duplicate. Test in Task 3.
2. Adding a place or saving picks while the ideas agent is still working → refused with "Agents are still finding places", so the agent's result can't overwrite a person's added place. Test in Task 3.
3. Saving picks when the ideas list is empty (agent pending, no key) → allowed with empty lists; sets `picked`. Test in Task 3.
4. Everyone skips a place that is still on the list → it is never scheduled and nobody is charged. Test in Task 5.
5. A traveler who marked a place "not for me" is never put on it by a split-off or a shared item. Test in Task 5 (validator check).

---

### Task 1: Data model and wishes with skips

**Files:**
- Modify: `backend/tripwright/models.py` (`TravelerIn`, `Traveler`, `Attraction`, `TripState`; new `Idea`)
- Modify: `backend/tripwright/specialists.py` (`wishes`, `brief`)
- Test: `backend/tests/test_group.py`

**Interfaces:**
- Produces:
  - `class Idea(BaseModel)`: `id: str`, `name: str`, `city: str = ""`, `category: str = ""`, `why: str = ""`, `source: Source | None = None`, `added_by: str | None = None`
  - `Traveler.skip: list[str] = []`, `Traveler.picked: bool = False`
  - `Attraction.skip_by: list[str] = []`
  - `TripState.ideas: list[Idea] = []`
  - `wishes(state) -> list[tuple[str, str, list[str], list[str], list[str]]]` — `(wish id, text, need ids, want ids, skip ids)`
  - `same_place(a: str, b: str) -> bool` in `specialists.py`: case- and whitespace-insensitive name equality
- Note: `Traveler` inherits `TravelerIn`; put `skip` and `picked` on `Traveler` only (forms never send them).

- [ ] **Step 1: Update the existing wishes test and add a skip case**

In `test_wishes_merge_what_everyone_asked_for`, the expected tuples gain a fifth element `[]`. Add:

```python
def test_wishes_carry_who_is_skipping(group):
    group.travelers[1].skip.append("tokyo disneyland")
    assert wishes(group)[0] == ("w1", "Tokyo Disneyland", ["p1"], [], ["p2"])
    assert "Sam: not interested in tokyo disneyland" in brief(group).lower() or "not interested in: tokyo disneyland" in brief(group).lower()
```

- [ ] **Step 2: Run, expect failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_group.py -k wishes -v` → FAIL (`skip` attribute / tuple length).

- [ ] **Step 3: Implement the model fields, `same_place`, `wishes` and `brief`**

`wishes` merges `need`, `want`, `skip` by normalized name exactly as it does now, with a third bucket. `brief` appends `not interested in: <names>` to each traveler's line when `skip` is non-empty. Update `attractions_task` and `build_attractions`, which unpack `wishes()`, to the 5-tuple (behavior unchanged in this task).

- [ ] **Step 4: Run the whole suite**

Run: `.\.venv\Scripts\python.exe -m pytest -q` → all pass.

---

### Task 2: The ideas agent

**Files:**
- Modify: `backend/tripwright/specialists.py` (new `IdeaOut`, `IdeasOut`, `build_ideas`, `ideas_task`, `SPECS["ideas"]`)
- Modify: `backend/tripwright/orchestrator.py` (`timeframe_graph`, module docstring)
- Test: `backend/tests/test_ideas.py` (create)

**Interfaces:**
- Consumes: `Idea`, `same_place` (Task 1); `RunContext.source(url) -> Source | None`.
- Produces:
  - `class IdeaOut(BaseModel)`: `name`, `city`, `category`, `why`, `source_url` (all `str`, with `Field(description=...)` like the other schemas)
  - `class IdeasOut(BaseModel)`: `ideas: list[IdeaOut]`
  - `async def build_ideas(state: TripState, ctx: RunContext, out: IdeasOut) -> list[Idea]`
  - `SPECS["ideas"] = Spec("ideas", "Ideas agent", "ideas", list[Idea], IdeasOut, ideas_task, build_ideas, lambda t: [t.web_research, t.read_source], lambda ideas: f"{len(ideas)} places to choose from")` (not judged)
  - `timeframe_graph()` nodes: `route`, `profile`, `timeframe`, `ideas`, with edges `route → profile`, `route → timeframe`, `route → ideas`.

- [ ] **Step 1: Write the failing tests** (`tests/test_ideas.py`)

Build `RunContext(agent="ideas", state=state)` and register `ctx.sources["example.com/a"] = Source(url="https://example.com/a")` as `test_group.py` does. Helper `idea(name, city="Tokyo", url="https://example.com/a")` returns an `IdeaOut` with category "Sights" and why "x".

```python
async def test_ideas_are_kept_with_their_sources(state):
    ideas = await build_ideas(state, ctx(state), IdeasOut(ideas=[idea(f"Place {i}") for i in range(15)]))
    assert len(ideas) == 15 and ideas[0].source.url == "https://example.com/a" and ideas[0].added_by is None

async def test_ideas_review_rejects(state):
    with pytest.raises(Rejected, match="was not returned by your tools"):
        await build_ideas(state, ctx(state), IdeasOut(ideas=[idea(f"P{i}") for i in range(14)] + [idea("Fake", url="https://nowhere.example")]))
    with pytest.raises(Rejected, match="at least 12"):
        await build_ideas(state, ctx(state), IdeasOut(ideas=[idea(f"P{i}") for i in range(5)]))
    with pytest.raises(Rejected, match="at most 25"):
        await build_ideas(state, ctx(state), IdeasOut(ideas=[idea(f"P{i}") for i in range(26)]))
    with pytest.raises(Rejected, match='"tokyo tower" is listed twice'):
        await build_ideas(state, ctx(state), IdeasOut(ideas=[idea(f"P{i}") for i in range(13)] + [idea("Tokyo Tower"), idea("tokyo  tower")]))
    with pytest.raises(Rejected, match="needs a city"):
        await build_ideas(state, ctx(state), IdeasOut(ideas=[idea(f"P{i}") for i in range(14)] + [idea("Nowhere", city="")]))

def test_stage_one_runs_ideas_after_the_route():
    graph = orchestrator.timeframe_graph()
    assert {"route", "profile", "timeframe", "ideas"} == set(graph.nodes)
```

- [ ] **Step 2: Run, expect failure** — `pytest tests/test_ideas.py -v` → ImportError on `build_ideas`.

- [ ] **Step 3: Implement**

`build_ideas` collects all problems, then raises `Rejected(problems)`. Messages: `f"{name}: source_url was not returned by your tools"`, `f"suggest at least 12 places (you gave {n})"`, `f"suggest at most 25 places (you gave {n})"`, `f'"{normalized name}" is listed twice'`, `f"{name}: needs a city"`. Each accepted idea gets `id=new_id("i")`.

`ideas_task(state, who)` returns `brief(state)` plus: suggest 15-25 distinct places and experiences in the destination across varied categories (sights, food, nature, culture, nightlife, family, day trips), suited to the trip length and pace, each with the city it is in, a short category, a one-sentence why, and a `source_url` from `web_research`; one or two searches per category is enough.

- [ ] **Step 4: Run the suite** — `pytest -q` → all pass.

---

### Task 3: API — picks, add a place, and always re-plan the route

**Files:**
- Modify: `backend/tripwright/api.py`
- Modify: `backend/tripwright/orchestrator.py` (`plan_trip`; new `save_picks`, `add_idea`, `ideas_ready`)
- Test: `backend/tests/test_api.py`, `backend/tests/test_group.py`

**Interfaces:**
- Consumes: `Idea`, `same_place` (Task 1); `_acting`, `You` header alias already in `api.py`.
- Produces:
  - `orchestrator.ideas_ready(state) -> bool`: true unless `state.agents.get("ideas")` has status in `{"working", "under_review", "sent_back"}`
  - `orchestrator.save_picks(state, traveler_id, need, want, skip) -> None`: raises `ValueError` with `f"{name} is not on the list"` or `f"{name} is marked more than once"`; sets the three lists (names normalized to the list's spelling) and `picked = True`; `_saved(state)`
  - `orchestrator.add_idea(state, traveler_id, name, city) -> Idea`: raises `ValueError(f"{name} is already on the list")`; appends with `category="Added by the group"`; `_saved(state)`
  - `PUT /api/trips/{trip_id}/travelers/{traveler_id}/picks` body `PicksIn(need: list[str] = [], want: list[str] = [], skip: list[str] = [])`
  - `POST /api/trips/{trip_id}/ideas` body `IdeaIn(name: str = Field(min_length=1), city: str = "")`
  - Both: 400 `"Planning has already started for this trip"` in `planning`/`review`; 400 `"Agents are still finding places"` when not `ideas_ready`; `ValueError` → 400. Picks: 403 unless `X-Traveler == traveler_id`. Ideas: `_acting` required.
  - `plan_trip` always runs `route_graph()` then `_set_dates` (drop the `len(state.travelers) > 1` guard).

- [ ] **Step 1: Write the failing tests** (add to `tests/test_api.py`; reuse its `trip` fixture and `post`; add a `put` helper)

```python
@pytest.fixture
def picking(trip):
    trip.stage = "gathering"
    trip.ideas = [Idea(id="i1", name="Tokyo Disneyland", city="Tokyo"), Idea(id="i2", name="Kinkaku-ji", city="Kyoto")]
    return trip

def test_each_traveler_saves_only_their_own_picks(picking):
    ok = put(picking, "/travelers/p2/picks", {"need": ["tokyo disneyland"], "skip": ["Kinkaku-ji"]}, "p2")
    sam = picking.traveler("p2")
    assert ok.status_code == 200 and (sam.need, sam.want, sam.skip, sam.picked) == (["Tokyo Disneyland"], [], ["Kinkaku-ji"], True)
    assert put(picking, "/travelers/p2/picks", {"need": []}, "p1").status_code == 403

def test_picks_must_be_on_the_list_and_marked_once(picking):
    assert "not on the list" in put(picking, "/travelers/p2/picks", {"want": ["Mt Fuji"]}, "p2").json()["detail"]
    assert "more than once" in put(picking, "/travelers/p2/picks", {"need": ["Kinkaku-ji"], "skip": ["Kinkaku-ji"]}, "p2").json()["detail"]

def test_picks_with_an_empty_list_still_count_as_picked(picking):
    picking.ideas = []
    assert put(picking, "/travelers/p2/picks", {}, "p2").status_code == 200 and picking.traveler("p2").picked

def test_anyone_on_the_trip_adds_a_place_once(picking):
    added = post(picking, "/ideas", {"name": "Ghibli Museum", "city": "Tokyo"}, "p2")
    assert added.status_code == 200
    assert (picking.ideas[-1].name, picking.ideas[-1].added_by, picking.ideas[-1].category) == ("Ghibli Museum", "p2", "Added by the group")
    assert post(picking, "/ideas", {"name": "tokyo  DISNEYLAND"}, "p1").status_code == 400
    assert post(picking, "/ideas", {"name": "Somewhere"}).status_code == 403

def test_picks_wait_for_the_ideas_agent_and_stop_at_planning(picking):
    picking.agents["ideas"] = AgentStatus(agent="ideas", status="working")
    assert post(picking, "/ideas", {"name": "X"}, "p1").json()["detail"] == "Agents are still finding places"
    picking.agents["ideas"].status = "accepted"
    picking.stage = "review"
    assert put(picking, "/travelers/p1/picks", {}, "p1").status_code == 400
```

In `test_group.py`, add a test that a solo `plan_trip` calls the route graph: monkeypatch `orchestrator.run` with a recorder and `orchestrator._set_dates` with a no-op coroutine, run `asyncio.run(orchestrator.plan_trip(state))` on the solo `state` fixture, and assert the recorded stage names start with `["route", "planning"]`.

- [ ] **Step 2: Run, expect failure** — `pytest tests/test_api.py tests/test_group.py -q`.

- [ ] **Step 3: Implement** the orchestrator functions and endpoints above.

- [ ] **Step 4: Run the suite** — `pytest -q` → all pass.

---

### Task 4: Attractions respect skips

**Files:**
- Modify: `backend/tripwright/specialists.py` (`build_attractions`, `attractions_task`, `review_attractions`)
- Test: `backend/tests/test_group.py`

**Interfaces:**
- Consumes: `wishes()` 5-tuple, `same_place`, `Attraction.skip_by` (Task 1).
- Produces: attractions with `skip_by` set (traveler ids, in traveler order, excluding anyone in `need_by`/`want_by`).

- [ ] **Step 1: Write the failing tests** (next to `test_attractions_agent_result_is_tied_back_to_who_asked`, same `found()` helper and geocode monkeypatch)

```python
async def test_attractions_record_who_skips_and_never_add_a_skipped_extra(group, monkeypatch):
    # set up as in the existing test; Alex (p1) skips teamLab Planets, which Sam (p2) wants (w4)
    group.travelers[0].skip.append("teamLab Planets")
    plan = await build_attractions(group, ctx, AttractionsOut(attractions=[
        found("Tokyo Disneyland", "Tokyo", ["w1"]), found("Fushimi Inari", "Kyoto", ["w2"]),
        found("Ghibli Museum", "Tokyo", ["w3"]), found("teamLab Planets", "Tokyo", ["w4"])]))
    assert next(a for a in plan if a.name == "teamLab Planets").skip_by == ["p1"]

    group.travelers[1].skip.append("Senso-ji")
    with pytest.raises(Rejected, match="Senso-ji: Sam marked it not for me"):
        await build_attractions(group, ctx, AttractionsOut(attractions=[
            found("Tokyo Disneyland", "Tokyo", ["w1"]), found("Fushimi Inari", "Kyoto", ["w2"]),
            found("Ghibli Museum", "Tokyo", ["w3"]), found("Senso-ji", "Tokyo", [])]))
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement.** In `build_attractions`: `skip_by` = travelers who skip any linked wish, plus (for every attraction) travelers whose `skip` names match the attraction name by `same_place`, minus `need_by`/`want_by`. Reject an attraction with no `need_by`/`want_by` and a non-empty `skip_by` with `f"{a.name}: {names} marked it not for me"` (names joined with " and "). In `attractions_task`, each request line adds `skipped by: ...`, and the instructions say never to suggest a place anyone marked not for me. `review_attractions` adds `; skipped by …` when non-empty.

- [ ] **Step 4: Run the suite.**

---

### Task 5: Scheduler, plan note, validation and review cards

**Files:**
- Modify: `backend/tripwright/scheduler.py` (`schedule`, `_plan_note`)
- Modify: `backend/tripwright/validate.py` (`validate_itinerary`)
- Modify: `backend/tripwright/cards.py` (`Card.skip_by`, attraction cards)
- Test: `backend/tests/test_group.py`

**Interfaces:**
- Consumes: `Attraction.skip_by`.
- Produces: `Card.skip_by: list[str] = []` (names); violation code `"SKIPPED_BUT_GOING"`, message `f"{name} marked {a.name} not for me but is going."`.

- [ ] **Step 1: Write the failing tests** (use the `group` fixture and `replan`, `going()` helpers already in `test_group.py`)

```python
def test_a_traveler_who_skips_a_place_is_free_and_does_not_pay(group):
    group.attractions[0].skip_by = ["p2"]  # Sam skips Tokyo Disneyland
    replan(group)
    assert going(group, "a_disney") == ["p1"]
    assert group.budgets["p2"].by_category["attractions"] == 28 + 4  # teamLab + Kinkaku-ji, no Disneyland
    assert "Sam skips Tokyo Disneyland on" in group.plan_note

def test_a_skipper_splits_off_for_their_own_pick_during_it(group):
    # Ghibli only opens on Disneyland day (as in the split-off test); Sam needs Ghibli and skips Disneyland.
    ...same Ghibli setup as test_traveler_splits_off_for_a_need_that_does_not_fit_and_regroups...
    group.attractions[0].skip_by = ["p2"]
    replan(group)
    assert going(group, "a_ghibli") == ["p2"] and going(group, "a_disney") == ["p1"]
    assert group.violations == []

def test_a_place_everyone_skips_is_not_scheduled(group):
    group.attractions[1].skip_by = ["p1", "p2"]  # Senso-ji
    replan(group)
    assert all(i.ref_id != "a_sensoji" for i in group.itinerary)

def test_going_to_a_skipped_place_is_a_conflict(group):
    replan(group)
    group.attractions[1].skip_by = ["p2"]
    assert "Sam marked Senso-ji not for me but is going." in [v.message for v in validate_itinerary(group)]

def test_attraction_cards_name_who_is_skipping(group):
    group.attractions[2].skip_by = ["p1"]
    replan(group)
    assert next(c for c in review_cards(group) if c.title == "teamLab Planets").skip_by == ["Alex"]
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement.**
  - Shared pass: `who = [t for t in everyone if t not in a.skip_by]`; if `who` is empty, skip the attraction (not scheduled, not listed as unscheduled). Use `who` for the item.
  - `fit_split`: a traveler in `who` is available during `host` if they are on `host.travelers` and didn't need/want `during`, or if they are in `during.skip_by`. Require at least one traveler to remain on `host` after the split. When splitting, remove `who` from `host.travelers` as now (a no-op for skippers).
  - `_plan_note`: list skips (one phrase per shared item whose `travelers` exclude a `skip_by` traveler: `f"{names} skip{'s' if one} {title} on {day:%a %b} {day.day}"`) together with split-off phrases. With neither, keep the current "One shared itinerary" sentence.
  - `validate_itinerary`: report `SKIPPED_BUT_GOING` for every visit whose `travelers` include someone in that attraction's `skip_by`.
  - `cards.py`: `skip_by=state.names(a.skip_by)`.

- [ ] **Step 4: Run the suite.**

---

### Task 6: Frontend

**Files:**
- Create: `frontend/src/components/Picks.tsx`
- Modify: `frontend/src/types.ts`, `frontend/src/api.ts`, `frontend/src/App.tsx`, `frontend/src/components/TripForm.tsx`, `frontend/src/components/TravelerForm.tsx`, `frontend/src/components/Review.tsx`, `frontend/src/styles.css`

**Interfaces:**
- Consumes: the endpoints from Task 3; `Idea`, `Traveler.skip`, `Traveler.picked`, `Attraction.skip_by`, `Card.skip_by`.
- Produces:
  - `types.ts`: `interface Idea { id; name; city; category; why; source: Source | null; added_by: string | null }`; `TripState.ideas: Idea[]`; `Traveler.skip: string[]`; `Traveler.picked: boolean`; `Attraction.skip_by: string[]`; `Card.skip_by: string[]`. Remove `need`/`want` from `TravelerIn`; put them on `Traveler`.
  - `api.ts`: `savePicks(id, travelerId, picks: { need: string[]; want: string[]; skip: string[] })` (PUT) and `addIdea(id, name, city)`.
  - `Picks({ state, you, busy, onSave, onAdd })`: `onSave(picks) => Promise<boolean>`, `onAdd(name, city) => Promise<boolean>`.

- [ ] **Step 1: Types, API client, forms.** Remove the two fields and their demo values from `TripForm` and `TravelerForm`.

- [ ] **Step 2: `Picks.tsx`.** Heading "What sounds good?". Ideas grouped by `category` (in list order). Each row: name, city, why, a three-button segmented control (Must do / Interested / Not for me; clicking the active one clears it), and chips of other travelers' marks. Local state starts from `you.need/want/skip`. While `state.agents.ideas?.status` is working/under_review/sent_back, show "Agents are finding places…" with the spinner and disable everything. With no ideas and the agent finished, show "The agents couldn't suggest places for this trip. Add the places you want below." An "Add a place" form (name, optional city). A primary "Save my picks" button.

- [ ] **Step 3: `App.tsx`.** Before `planning`/`review`, render `Picks` when `!you.picked` or the person clicked "Edit my picks" (header link shown before planning; local `editingPicks` state, cleared on save and on hash change). Saving calls `act(api.savePicks(...))`.

- [ ] **Step 4: `Review.tsx`.** Add `<Chips label="Skipping" items={card.skip_by} />` in the `who` block.

- [ ] **Step 5: Verify.** `npx --no-install tsc --noEmit -p .` → exit 0; `npm run build` → built. In the browser pane: create a trip (no form need/want fields), see the Picks screen, add a place, mark it, save, reach the dates screen; join as a second person from another tab, see the same list with the host's marks, save, reach "Who's coming?".

---

### Task 7: Docs

**Files:**
- Modify: `README.md` (intro sentence about describing must-sees; stage diagram adds `ideas`; `Agent` table/features if it lists specialists)
- Modify: `DEMO.md` (the form step and the new picks step)
- Modify: `docs/superpowers/specs/2026-10-10-interest-picks-design.md` (ideas review: "city is not empty", not "in the destination")

- [ ] **Step 1: Update the passages.** Keep the existing voice; describe what the user now does.
- [ ] **Step 2: Final check.** `pytest -q` all pass; frontend type-check and build pass.
