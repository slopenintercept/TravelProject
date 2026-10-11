"""The ideas agent: the shared list of places every traveler marks."""

import pytest

from tripwright import orchestrator
from tripwright.models import Idea, Source
from tripwright.specialists import SPECS, IdeaOut, IdeasOut, Rejected, build_ideas, build_more_ideas
from tripwright.toolbox import RunContext


def ctx(state, who=None):
    run = RunContext(agent="ideas", state=state, traveler=who)
    run.sources["example.com/a"] = Source(url="https://example.com/a")
    return run


def idea(name, city="Tokyo", url="https://example.com/a"):
    return IdeaOut(name=name, city=city, category="Sights", why="x", source_url=url)


def places(n):
    return [idea(f"Place {i}") for i in range(n)]


async def test_ideas_are_kept_with_their_sources(state):
    ideas = await build_ideas(state, ctx(state), IdeasOut(ideas=places(15)))
    assert len(ideas) == 15
    assert (ideas[0].name, ideas[0].city, ideas[0].source.url, ideas[0].added_by) == ("Place 0", "Tokyo", "https://example.com/a", None)


async def test_ideas_review_rejects(state):
    with pytest.raises(Rejected, match="Fake: source_url was not returned by your tools"):
        await build_ideas(state, ctx(state), IdeasOut(ideas=places(14) + [idea("Fake", url="https://nowhere.example")]))
    with pytest.raises(Rejected, match="suggest at least 12 places"):
        await build_ideas(state, ctx(state), IdeasOut(ideas=places(5)))
    with pytest.raises(Rejected, match="suggest at most 25 places"):
        await build_ideas(state, ctx(state), IdeasOut(ideas=places(26)))
    with pytest.raises(Rejected, match='"tokyo tower" is listed twice'):
        await build_ideas(state, ctx(state), IdeasOut(ideas=places(13) + [idea("Tokyo Tower"), idea("tokyo  tower")]))
    with pytest.raises(Rejected, match="Nowhere: needs a city"):
        await build_ideas(state, ctx(state), IdeasOut(ideas=places(14) + [idea("Nowhere", city=" ")]))


@pytest.fixture
def listed(group):
    group.ideas = [Idea(id="i1", name="Tokyo Disneyland", city="Tokyo"), Idea(id="i2", name="Senso-ji", city="Tokyo")]
    group.travelers[0].skip = ["Senso-ji"]  # Alex
    return group


async def test_more_ideas_are_new_places_for_the_one_who_asked(listed):
    sam = listed.traveler("p2")
    more = await build_more_ideas(listed, ctx(listed, sam), IdeasOut(ideas=places(6)))
    assert [i.name for i in more] == [f"Place {i}" for i in range(6)]
    assert all(i.suggested_for == "p2" for i in more)


async def test_more_ideas_review_rejects(listed):
    sam = listed.traveler("p2")
    with pytest.raises(Rejected, match='"tokyo disneyland" is already on the list'):
        await build_more_ideas(listed, ctx(listed, sam), IdeasOut(ideas=places(5) + [idea("tokyo  Disneyland")]))
    with pytest.raises(Rejected, match="Sensō-ji Temple: Alex marked a place like it not for me"):
        await build_more_ideas(listed, ctx(listed, sam), IdeasOut(ideas=places(5) + [idea("Sensō-ji Temple")]))
    with pytest.raises(Rejected, match="suggest at least 5 places"):
        await build_more_ideas(listed, ctx(listed, sam), IdeasOut(ideas=places(3)))
    with pytest.raises(Rejected, match="suggest at most 10 places"):
        await build_more_ideas(listed, ctx(listed, sam), IdeasOut(ideas=places(11)))


def test_more_ideas_are_added_to_the_list(listed):
    node = orchestrator.SpecialistNode(SPECS["more_ideas"], "p2")
    node._store(listed, listed.traveler("p2"), [Idea(id="i9", name="Ghibli Museum", suggested_for="p2"),
                                                 Idea(id="i8", name="tokyo disneyland", suggested_for="p2")])
    assert [i.name for i in listed.ideas] == ["Tokyo Disneyland", "Senso-ji", "Ghibli Museum"]


def test_stage_one_runs_ideas_after_the_route():
    graph = orchestrator.timeframe_graph()
    assert set(graph.nodes) == {"route", "profile", "timeframe", "ideas"}
    assert {(e.from_node.node_id, e.to_node.node_id) for e in graph.edges} == {
        ("route", "profile"), ("route", "timeframe"), ("route", "ideas")}
