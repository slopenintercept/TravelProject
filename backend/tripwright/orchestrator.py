"""The orchestrator: parallel dispatch on a Strands Graph, review, rejection loop, re-planning.

Stages (each one is a Graph run; nodes with no edge between them run in parallel):

    form submitted   route -> [profile | timeframe | ideas]   (ideas: the places everyone marks)
    everyone's in    route (from everyone's picks), then
                     [a flight agent per traveler | lodging | attractions | transport | weather]
                         -> scheduler -> budget -> validate
    any user change  [only the affected specialists] -> scheduler -> budget -> validate

Each traveler gets their own flight agent (own origin, own budget). One lodging agent
researches the options, and each traveler's room is then picked from them by that
traveler's own budget. Attractions are planned once for the group, from everyone's
needs and wants, by one agent per city working at the same time and reviewed as one list.

Each specialist is a custom graph node that wraps a Strands Agent with the review
loop: deterministic checks on every attempt, the orchestrator's LLM judgment on the
first, up to MAX_RETRIES send-backs with specific feedback, then a flagged fallback. A node never
raises, so one slow or failing specialist cannot stall the others.
"""

from __future__ import annotations

import asyncio
import re
from datetime import date, timedelta

from pydantic import BaseModel, Field
from strands import Agent
from strands.multiagent import GraphBuilder
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, Status
from strands.multiagent.graph import Graph, GraphState

from . import config, recorded, store
from .budget import apply_swaps
from .events import Bus, bus
from .llm import Activity, RateLimit, make_model
from .models import (
    Flag, Idea, RoutePlan, RouteSegment, Traveler, TravelerIn, TripDates, TripRequest, TripState, new_id,
)
from .scheduler import schedule
from .specialists import (
    NO_TOOLS, PREAMBLE, SPECS, WITH_TOOLS, Rejected, Spec, brief, fetch_weather, place_key, same_place,
)
from .toolbox import RunContext, Toolbox
from .tools import flights
from .validate import rebudget, validate_itinerary

SAVED_RESULT_TTL_S = 30 * 24 * 3600

PREF = {
    "airbnb": "Prefers Airbnb over hotels",
    "hotel": "Prefers hotels over Airbnb",
    "rental_car": "Prefers a rental car over public transit",
}

ORCHESTRATOR_ROLE = (
    "You are the orchestrator of Tripwright, a team of travel-planning agents. You review a specialist "
    "agent's result before it is accepted. Its sources, dates and budget have already been checked by code. "
    "Judge only plausibility and fit. Accept unless there is a concrete problem: a price or time that cannot "
    "be right, or a choice that clearly contradicts what a traveler needs or can afford. Do not reject "
    "because another option might be slightly better, for style, or for detail you were not shown. If you "
    "reject, say exactly what to fix in one or two sentences."
)


class Verdict(BaseModel):
    accept: bool
    feedback: str = Field(description="What to fix; empty when accepting")


def _result_key(spec: Spec, state: TripState, who: Traveler | None) -> str:
    """Where a specialist's last accepted result is kept. Flights depend on the traveler's origin; lodging and
    the list of places to choose from are the same wherever the travelers fly from."""
    origin = who.origin if who else "any" if spec.name in ("lodging", "ideas") else state.request.origin
    return f"result:{spec.name}:{origin}:{state.request.destination}:{state.request.days}".lower()


def _redate(payload: str, delta: timedelta) -> str:
    """Shift every date in a saved result (but not when its evidence was fetched)."""
    return re.sub(r'(?<!"fetched_at":")\d{4}-\d{2}-\d{2}',
                  lambda m: (date.fromisoformat(m[0]) + delta).isoformat(), payload)


class SpecialistNode(MultiAgentBase):
    """One specialist agent plus the orchestrator's review of it, as a graph node.

    For per-traveler specialists (flight, lodging) there is one node per person, named
    like "flight:p2", and the result is written to that traveler.
    """

    def __init__(self, spec: Spec, traveler_id: str | None = None) -> None:
        super().__init__()
        self.spec, self.traveler_id = spec, traveler_id
        self.name = f"{spec.name}:{traveler_id}" if traveler_id else spec.name

    async def invoke_async(self, task, invocation_state=None, **kwargs) -> MultiAgentResult:
        state, events = invocation_state["state"], invocation_state["bus"]
        who = state.traveler(self.traveler_id) if self.traveler_id else None
        limit = config.AGENT_TIMEOUT_S + (self.spec.extra_time(state) if self.spec.extra_time else 0)
        try:
            await asyncio.wait_for(self._run(state, events, who), timeout=limit)
        except TimeoutError:
            self._fall_back(state, events, who, f"timed out after {limit}s")
        except Exception as e:
            self._fall_back(state, events, who, f"failed with {type(e).__name__}: {e}")
        return MultiAgentResult(status=Status.COMPLETED)

    def _store(self, state: TripState, who: Traveler | None, value) -> None:
        if self.spec.append:  # more places for the shared list, never replacing it
            current = getattr(state, self.spec.field)
            current += [v for v in value if not any(same_place(v.name, c.name) for c in current)]
        else:
            setattr(who or state, self.spec.field, value)
        if self.spec.after:
            self.spec.after(state)

    def _accept(self, state: TripState, events: Bus, who: Traveler | None, value) -> None:
        self._store(state, who, value)
        state.flags.pop(self.name, None)
        saved = {"start": state.dates and state.dates.start.isoformat(), "value": self.spec.dump(value)}
        store.cache_set(_result_key(self.spec, state, who), saved)
        if config.RECORD_FIXTURES:
            recorded.record(_result_key(self.spec, state, who), saved)
        events.status(state, self.name, "accepted", "Accepted by the orchestrator", found=self.spec.describe(value))

    def _fall_back(self, state: TripState, events: Bus, who: Traveler | None, reason: str) -> None:
        """Use the last accepted result for this trip (database, then demo fixtures), flagged for the user."""
        key = _result_key(self.spec, state, who)
        saved = (store.cache_get(key, SAVED_RESULT_TTL_S) or recorded.saved(key)) if self.spec.saved_fallback else None
        try:
            if saved is None:
                raise ValueError("there is no saved result")
            payload = saved["value"]
            if saved["start"] and state.dates:
                payload = _redate(payload, state.dates.start - date.fromisoformat(saved["start"]))
            value = self.spec.load(payload)
        except ValueError as e:
            state.flags[self.name] = Flag(kind="pending", reason=f"{reason}; {e}")
            events.status(state, self.name, "pending", f"No result yet: {reason}")
            return
        self._store(state, who, value)
        if self.spec.after_fallback:
            self.spec.after_fallback(state)
        state.flags[self.name] = Flag(kind="fallback", reason=f"Showing saved results: the live run {reason}.")
        events.status(state, self.name, "fallback", f"Using saved results: {reason}", found=self.spec.describe(value))

    async def _run(self, state: TripState, events: Bus, who: Traveler | None) -> None:
        spec = self.spec
        if spec.reuse and (saved := store.cache_get(_result_key(spec, state, who), SAVED_RESULT_TTL_S)):
            try:  # the same destination and length was researched before: nothing to wait for
                value = spec.load(saved["value"])
            except ValueError:
                value = None  # saved by an older version; research it again
            if value:
                self._store(state, who, value)
                state.flags.pop(self.name, None)
                return events.status(state, self.name, "accepted", "Reused from an earlier trip like this one", 1,
                                     spec.describe(value))
        if not config.OPENAI_API_KEY:
            return self._fall_back(state, events, who, "had no inference key (set OPENAI_API_KEY)")

        ctx = RunContext(agent=self.name, state=state, traveler=who)
        # Usually one agent; a split specialist has one per prompt, working at the same time on a shared context.
        prompts, agents, problems = spec.split(state) if spec.split else [spec.task(state, who)], [], []
        for _ in prompts:
            tools = spec.tools(Toolbox(ctx))
            agents.append(Agent(
                model=make_model(spec.max_tokens), name=spec.name, tools=tools,
                system_prompt=PREAMBLE.format(title=spec.title, tools=WITH_TOOLS if tools else NO_TOOLS),
                hooks=[RateLimit(), Activity(self.name, events.emit)], callback_handler=None,
            ))

        for attempt in range(1, config.MAX_RETRIES + 2):
            events.status(state, self.name, "working",
                          "Gathering data" if attempt == 1 else "Reworking after review", attempt)
            try:
                answers = await asyncio.gather(*(self._ask(a, p, events) for a, p in zip(agents, prompts)),
                                               return_exceptions=True)  # let every agent finish before a retry
                if failed := next((a for a in answers if isinstance(a, Exception)), None):
                    raise failed
                answer = spec.join(answers) if spec.join else answers[0]
                events.status(state, self.name, "under_review", "Orchestrator is checking sources, dates and budget")
                value = await spec.build(state, ctx, answer)
                if spec.judged and attempt == 1:  # one judgment call per result; code checks every attempt
                    await judge(state, spec, value, who)
            except Rejected as rejected:
                problems = rejected.problems
            except Exception as e:  # model errors and malformed structured output are sent back too
                problems = [f"{type(e).__name__}: {e}"]
            else:
                return self._accept(state, events, who, value)
            events.status(state, self.name, "sent_back", "; ".join(problems), attempt)
            yours = " the ones about your own places and requests" if len(agents) > 1 else " these"
            prompts = ["The orchestrator sent your result back:\n" + "\n".join(f"- {p}" for p in problems)
                       + f"\nFix{yours} and answer again."] * len(agents)
        self._fall_back(state, events, who, "failed review: " + "; ".join(problems))

    async def _ask(self, agent: Agent, prompt: str, events: Bus):
        """Run the agent, streaming its reasoning to the activity panel."""
        text, result = "", None
        async for event in agent.stream_async(prompt, structured_output_model=self.spec.schema):
            if "data" in event:
                text += event["data"]
                if len(text) >= 80:
                    events.emit("text", agent=self.name, text=text)
                    text = ""
            elif "result" in event:
                result = event["result"]
        if text:
            events.emit("text", agent=self.name, text=text)
        if result is None or result.structured_output is None:
            raise Rejected(["answer with the structured result"])
        return result.structured_output


async def judge(state: TripState, spec: Spec, value, who: Traveler | None) -> None:
    """The orchestrator's LLM judgment call. Raises Rejected with feedback for the specialist."""
    reviewer = Agent(model=make_model(), name="orchestrator", system_prompt=ORCHESTRATOR_ROLE,
                     hooks=[RateLimit()], callback_handler=None)
    shown = spec.review(state, value) if spec.review else spec.describe(value)
    whose = f" for {who.name} only (flying from {who.origin}, budget ${who.budget_usd:,.0f})" if who else ""
    try:
        result = await reviewer.invoke_async(
            f"{brief(state)}\n\nResult from the {spec.title}{whose}:\n{shown}",
            structured_output_model=Verdict,
        )
    except Exception:
        return  # the deterministic checks already passed; a failed judgment call doesn't block the result
    verdict = result.structured_output
    if verdict and not verdict.accept:
        raise Rejected([verdict.feedback or "the orchestrator judged this implausible"])


class StepNode(MultiAgentBase):
    """A deterministic step (no LLM) as a graph node."""

    def __init__(self, name: str, step) -> None:
        super().__init__()
        self.name, self.step = name, step

    async def invoke_async(self, task, invocation_state=None, **kwargs) -> MultiAgentResult:
        state, events = invocation_state["state"], invocation_state["bus"]
        events.status(state, self.name, "working", attempt=1)
        try:
            found = await self.step(state)
            state.flags.pop(self.name, None)
            events.status(state, self.name, "accepted", found=found)
        except Exception as e:
            state.flags[self.name] = Flag(kind="pending", reason=str(e))
            events.status(state, self.name, "pending", f"{type(e).__name__}: {e}")
        return MultiAgentResult(status=Status.COMPLETED)


async def weather_step(state: TripState) -> str:
    state.weather = await fetch_weather(state)
    driest = min(state.weather, key=lambda w: w.precip_prob or 0, default=None)
    return f"{len(state.weather)} days" + (f"; driest is {driest.day:%a %b %d}" if driest else "")


async def scheduler_step(state: TripState) -> str:
    schedule(state)
    placed = sum(i.kind == "attraction" for i in state.itinerary)
    left = f"; {len(state.unscheduled)} did not fit" if state.unscheduled else ""
    note = f". {state.plan_note}" if state.plan_note else ""
    return f"{placed} activities over {len({i.day for i in state.itinerary})} days{left}{note}"


async def budget_step(state: TripState) -> str:
    rebudget(state)
    lines = [f"{t.name} ${state.budgets[t.id].spent_usd:,.0f} of ${t.budget_usd:,.0f}" for t in state.travelers]
    swaps = sum(len(p.swaps) for p in state.budget_proposals.values())
    return "; ".join(lines) + (f"; proposing {swaps} swap(s)" if swaps else "")


async def validate_step(state: TripState) -> str:
    state.violations = validate_itinerary(state)
    return f"{len(state.violations)} issue(s)" if state.violations else "No conflicts"


def _node(name: str) -> MultiAgentBase:
    """`name` is a specialist ("attractions"), a traveler's specialist ("flight:p2"), or "weather"."""
    if name == "weather":
        return StepNode("weather", weather_step)
    spec, _, traveler_id = name.partition(":")
    return SpecialistNode(SPECS[spec], traveler_id or None)


def research_nodes(state: TripState) -> list[str]:
    """Everything that runs in parallel once everyone is in."""
    return [f"flight:{t.id}" for t in state.travelers] + ["lodging", "attractions", "transport", "weather"]


def _all_done(names: list[str]):
    def ready(state: GraphState) -> bool:
        return all(n in state.results and state.results[n].status == Status.COMPLETED for n in names)
    return ready


def timeframe_graph() -> Graph:
    builder = GraphBuilder()
    for name in ("route", "profile", "timeframe", "ideas"):
        builder.add_node(_node(name), name)
    for name in ("profile", "timeframe", "ideas"):
        builder.add_edge("route", name)
    builder.set_execution_timeout(config.AGENT_TIMEOUT_S * 2 + 30)
    return builder.build()


def planning_graph(specialists: list[str], schedule: bool = True) -> Graph:
    """The given specialists in parallel, then scheduler -> budget -> validate. `schedule=False` is the
    research run, before anyone has chosen their flight and rooms."""
    builder = GraphBuilder()
    for name in specialists:
        builder.add_node(_node(name), name)
    if schedule:
        for name, step in (("scheduler", scheduler_step), ("budget", budget_step), ("validate", validate_step)):
            builder.add_node(StepNode(name, step), name)
        for name in specialists:
            builder.add_edge(name, "scheduler", condition=_all_done(specialists))
        builder.add_edge("scheduler", "budget")
        builder.add_edge("budget", "validate")
    # Each specialist keeps to its own limit (more for a big group's attractions); this is only a backstop.
    builder.set_execution_timeout(config.AGENT_TIMEOUT_S * 3 + 60)
    return builder.build()


def route_graph() -> Graph:
    builder = GraphBuilder()
    builder.add_node(_node("route"), "route")
    builder.set_execution_timeout(config.AGENT_TIMEOUT_S + 30)
    return builder.build()


async def run(state: TripState, graph: Graph, stage: str) -> None:
    events = bus(state.id)
    events.emit("stage", stage=stage, status="started")
    async for event in graph.stream_async(stage, invocation_state={"state": state, "bus": events}):
        if event.get("type") == "multiagent_node_stop":
            store.save_trip(state)
            events.emit("state")
    store.save_trip(state)
    events.emit("stage", stage=stage, status="finished")
    events.emit("state")


# --- the user flow ---------------------------------------------------------------

def _saved(state: TripState) -> None:
    store.save_trip(state)
    bus(state.id).emit("state")


def new_trip(request: TripRequest) -> TripState:
    host = Traveler(id="p1", host=True, **request.model_dump(include=set(TravelerIn.model_fields)))
    state = TripState(id=new_id("trip"), request=request, travelers=[host], profile=store.load_profile(), stage="timeframe")
    preferences = state.profile.stated_preferences if state.profile else []
    if PREF["airbnb"] in preferences:
        state.lodging_override = "airbnb"
    host.rental_car = PREF["rental_car"] in preferences
    store.save_trip(state)
    return state


async def plan_timeframe(state: TripState) -> None:
    try:
        await run(state, timeframe_graph(), "timeframe")
        if state.profile:
            store.save_profile(state.profile)
    finally:  # even if the stage failed, the host can still pick their own dates
        state.stage = "awaiting_dates"
        _saved(state)


async def _set_dates(state: TripState, start: date) -> None:
    """Fix the trip dates. The landing day comes from real flight results, not from the model's guess."""
    if state.route is None:
        state.route = RoutePlan(segments=[RouteSegment(city=state.request.destination, nights=state.request.days)])
    end = start + timedelta(days=state.request.days)
    try:
        found = await flights.search_flights(state.request.origin, state.route.segments[0].city, start, end)
        offsets = [(date.fromisoformat(o["arrive_at"][:10]) - start).days for o in found["options"]]
        state.route.arrival_day_offset = max(set(offsets), key=offsets.count)  # the usual one
    except Exception:
        pass  # keep the route planner's estimate; the flight review still checks the landing day
    _fit_nights(state.route, state.request.days)
    state.dates = TripDates(start=start, arrival=start + timedelta(days=state.route.arrival_day_offset), end=end)


def _fit_nights(route: RoutePlan, days: int) -> None:
    """Nights follow the landing day: the longest stay absorbs the difference."""
    longest = max(route.segments, key=lambda s: s.nights)
    longest.nights += days - route.arrival_day_offset - sum(s.nights for s in route.segments)


def fit_route_to_dates(state: TripState) -> None:
    """A route re-planned after the dates were set keeps the landing day those dates already have."""
    state.route.arrival_day_offset = (state.dates.arrival - state.dates.start).days
    _fit_nights(state.route, state.request.days)


async def choose_dates(state: TripState, start: date) -> None:
    """The host picks the dates; the trip then waits for everyone invited to add their preferences."""
    await _set_dates(state, start)
    state.stage = "gathering"
    _saved(state)


def join(state: TripState, traveler: TravelerIn) -> Traveler:
    number = 1 + max(int(t.id[1:]) for t in state.travelers)
    joined = Traveler(id=f"p{number}", **traveler.model_dump())
    state.travelers.append(joined)
    _saved(state)
    return joined


def leave(state: TripState, traveler_id: str) -> None:
    if state.traveler(traveler_id).host:
        raise ValueError("The host can't be removed from the trip")
    state.travelers = [t for t in state.travelers if t.id != traveler_id]
    _saved(state)


def ideas_ready(state: TripState) -> bool:
    """The ideas agent has finished (or never ran), so the list can be marked and added to."""
    status = state.agents.get("ideas")
    return status is None or status.status not in ("working", "under_review", "sent_back")


def save_picks(state: TripState, traveler_id: str, need: list[str], want: list[str], skip: list[str],
               picked: bool = True) -> None:
    """One traveler's marks on the ideas list, stored by the list's own spelling of each place.
    `picked=False` keeps their marks without finishing the step (they asked for more places first)."""
    listed = {place_key(i.name): i.name for i in state.ideas}
    marked: dict[str, list[str]] = {"need": [], "want": [], "skip": []}
    seen: set[str] = set()
    for kind, names in (("need", need), ("want", want), ("skip", skip)):
        for name in names:
            key = place_key(name)
            if key not in listed:
                raise ValueError(f"{name} is not on the list")
            if key in seen:
                raise ValueError(f"{listed[key]} is marked more than once")
            seen.add(key)
            marked[kind].append(listed[key])
    traveler = state.traveler(traveler_id)
    traveler.need, traveler.want, traveler.skip = marked["need"], marked["want"], marked["skip"]
    traveler.picked = traveler.picked or picked
    _saved(state)


def finding_more(state: TripState, traveler_id: str) -> bool:
    status = state.agents.get(f"more_ideas:{traveler_id}")
    return status is not None and status.status in ("working", "under_review", "sent_back")


async def suggest_more(state: TripState, traveler_id: str) -> None:
    """More places for one traveler, like what they marked; added to the shared list for everyone."""
    builder = GraphBuilder()
    name = f"more_ideas:{traveler_id}"
    builder.add_node(_node(name), name)
    builder.set_execution_timeout(config.AGENT_TIMEOUT_S + 30)
    await run(state, builder.build(), "more_ideas")


def add_idea(state: TripState, traveler_id: str, name: str, city: str) -> Idea:
    """A place someone wants that the agents did not suggest; it is researched with everything else at planning."""
    if any(same_place(i.name, name) for i in state.ideas):
        raise ValueError(f"{name} is already on the list")
    idea = Idea(id=new_id("i"), name=name.strip(), city=city.strip(), category="Added by the group", added_by=traveler_id)
    state.ideas.append(idea)
    _saved(state)
    return idea


async def plan_trip(state: TripState) -> None:
    """Everyone's in: re-plan the route from everyone's picks, then run every specialist in parallel.

    Activities, transport and weather don't depend on anyone's flight or rooms, so they research at the
    same time; the days are only scheduled once someone has chosen their flight and rooms."""
    state.stage = "planning"
    try:
        await run(state, route_graph(), "route")  # the first route was planned before anyone picked places
        await _set_dates(state, state.dates.start)
        state.stage = "choosing"
        _saved(state)
        await run(state, planning_graph(research_nodes(state), schedule=False), "research")
    finally:  # even if a stage failed, show what was found, with the gaps flagged
        if any(t.confirmed for t in state.travelers):
            await schedule_choices(state)
        else:
            state.stage = "choosing"
            _saved(state)


def recover(state: TripState) -> None:
    """A trip loaded after a server restart: whatever was running then is gone. Mark those agents stopped and
    put the trip back where people can carry on (pick dates, or start planning again)."""
    for name, status in state.agents.items():
        if status.status in ("working", "under_review", "sent_back"):
            status.status, status.message = "failed", "Stopped when the server restarted"
            state.flags.setdefault(name, Flag(kind="pending", reason="Stopped when the server restarted"))
    if state.stage == "timeframe":
        state.stage = "awaiting_dates"
    elif state.stage == "planning":
        state.stage = "gathering"


UNFINISHED = ("fallback", "pending", "failed")


def unfinished(state: TripState) -> list[str]:
    """Research agents that ended on saved results or nothing (timed out, failed review, site blocked)."""
    return [n for n in research_nodes(state) if n in state.agents and state.agents[n].status in UNFINISHED]


async def retry(state: TripState) -> list[str]:
    """Run again only the research agents that didn't finish, so they have the browser and model to themselves.
    New flight or room options undo the affected travelers' confirmations: they choose again from the new ones."""
    names = unfinished(state)
    for name in names:
        if name == "lodging":
            for t in state.travelers:
                t.confirmed = False
        elif name.startswith("flight:"):
            state.traveler(name.partition(":")[2]).confirmed = False
    _saved(state)
    await run(state, planning_graph(names, schedule=False), "retry")
    if state.stage == "review" or any(t.confirmed for t in state.travelers):
        await schedule_choices(state)
    return names


async def schedule_choices(state: TripState) -> None:
    """Plan the days around everyone's flights and rooms (the agents' top picks for anyone who hasn't chosen)."""
    await run(state, planning_graph([]), "schedule")
    state.stage = "review"
    _saved(state)


def options_ready(state: TripState, traveler_id: str) -> bool:
    """This traveler's flight and lodging agents have finished (accepted, or fell back), so they can choose."""
    if state.stage == "review":
        return True
    working = ("idle", "working", "under_review", "sent_back")
    return all(a in state.agents and state.agents[a].status not in working for a in (f"flight:{traveler_id}", "lodging"))


def confirm_choices(state: TripState, traveler_id: str, flight_id: str | None, stay_ids: list[str]) -> None:
    """A traveler's own flight and one room per stay, from their options."""
    traveler = state.traveler(traveler_id)
    if traveler.flights and not any(o.id == flight_id for o in traveler.flights.options):
        raise ValueError("That flight is not one of your options")
    stays = traveler.lodging.stays if traveler.lodging else []
    if len(stay_ids) != len(stays):
        raise ValueError("Choose one room for each stay")
    for stay, room_id in zip(stays, stay_ids):
        if not any(o.id == room_id for o in stay.options):
            raise ValueError(f"That room is not an option for the {stay.city} stay")
    if traveler.flights:
        traveler.flights.selected_id = flight_id
    for stay, room_id in zip(stays, stay_ids):
        stay.selected_id = room_id
    traveler.confirmed = True
    _saved(state)


def _learn(state: TripState, preference: str | None, forget: list[str]) -> None:
    """Overrides on the review screen become the host's stated preferences for future trips."""
    profile = state.profile or store.load_profile()
    if profile is None:
        return
    kept = [p for p in profile.stated_preferences if p not in forget and p != preference]
    profile.stated_preferences = kept + ([preference] if preference else [])
    state.profile = profile
    store.save_profile(profile)


def _rental_car(state: TripState, traveler: Traveler, wanted: bool) -> None:
    traveler.rental_car = wanted
    if traveler.host:
        _learn(state, PREF["rental_car"] if wanted else None, [PREF["rental_car"]])


async def decide(state: TripState, action: str, card: str, option_id: str | None = None) -> None:
    """Apply one review-screen decision, then re-run only what it affects."""
    kind, _, ref = card.partition(":")
    rerun: list[str] = []
    if action == "approve":
        state.approvals[card] = "approved"
        return _saved(state)
    state.approvals.pop(card, None)

    if action == "swap" and kind == "flight":
        state.traveler(ref).flights.selected_id = option_id
    elif action == "swap" and kind == "stay":
        traveler_id, _, index = ref.partition(":")
        state.traveler(traveler_id).lodging.stays[int(index)].selected_id = option_id
    elif action in ("remove", "restore") and kind == "attraction":
        next(a for a in state.attractions if a.id == ref).included = action == "restore"
    elif action in ("swap", "remove", "restore") and kind == "leg":  # one traveler's own leg
        traveler_id, _, leg_id = ref.partition(":")
        traveler = state.traveler(traveler_id)
        at = next(i for i, leg in enumerate(traveler.legs) if leg.id == leg_id)
        leg = traveler.legs[at]
        if action == "swap":  # another way to make the same trip; the one they had becomes an alternative
            options = [leg.model_copy(update={"alternatives": []}), *leg.alternatives]
            chosen = next(o for o in options if o.id == option_id)
            traveler.legs[at] = chosen.model_copy(update={"alternatives": [o for o in options if o.id != option_id]})
        else:
            leg.included = action == "restore"
            if leg.kind == "rental_car":
                _rental_car(state, traveler, leg.included)
    elif action == "switch" and kind == "lodging":
        current = state.lodging_override or state.lodging.common_choice.choice
        state.lodging_override = "hotel" if current == "airbnb" else "airbnb"
        _learn(state, PREF[state.lodging_override], [PREF["airbnb"], PREF["hotel"]])
        rerun = ["lodging"]
    elif action == "switch" and kind == "transport":  # one traveler adds a rental car
        traveler = state.traveler(ref)
        _rental_car(state, traveler, True)
        cars = [leg for leg in traveler.legs if leg.kind == "rental_car"]
        for leg in cars:
            leg.included = True
        if not cars:  # nobody has asked for one before, so the agent has to price it
            rerun = ["transport"]
    else:
        raise ValueError(f"Cannot {action} {card}")
    await run(state, planning_graph(rerun), "replan")


async def apply_budget_proposal(state: TripState, traveler_id: str) -> None:
    proposal = state.budget_proposals.get(traveler_id)
    if proposal:
        apply_swaps(state.traveler(traveler_id), proposal)
        await run(state, planning_graph([]), "replan")


async def move_item(state: TripState, item_id: str, day: date) -> str:
    """Calendar drag: pin the activity to `day`, re-schedule around it and re-validate."""
    item = next(i for i in state.itinerary if i.id == item_id)
    if item.locked:
        raise ValueError("Flights and intercity travel can't be moved")
    item.day, item.pinned = day, True
    await run(state, planning_graph([]), "replan")
    missed = next((u for u in state.unscheduled if u.attraction_id == item.ref_id), None)
    on_day = any(i.ref_id == item.ref_id and i.day == day for i in state.itinerary)
    if on_day:
        return ""
    # It can't go there (closed, no time, wrong city): the pin is gone, so re-plan puts it back.
    await run(state, planning_graph([]), "replan")
    return f"Couldn't move {item.title} to {day:%a %b %d}: {missed.reason if missed else 'it does not fit that day'}."


async def swap_item(state: TripState, item_id: str, attraction_id: str) -> None:
    """Calendar swap: replace one activity with another attraction on the same day."""
    item = next(i for i in state.itinerary if i.id == item_id)
    for a in state.attractions:
        if a.id == item.ref_id:
            a.included = False
        if a.id == attraction_id:
            a.included = True
    state.itinerary = [i for i in state.itinerary if i.id != item_id]
    state.itinerary.append(item.model_copy(update={"ref_id": attraction_id, "pinned": True}))
    await run(state, planning_graph([]), "replan")
