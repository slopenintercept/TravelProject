"""A specialist's task stays in its conversation when Strands trims a long one (no network)."""

import pytest
from strands.types.exceptions import ContextWindowOverflowException

from test_orchestrator import ScriptedModel
from tripwright import orchestrator
from tripwright.events import bus

TASK = "Find places to see in Osaka."


@pytest.fixture
def agent(monkeypatch):
    """A specialist's agent after 30 searches with long results: the task, then 30 tool call / tool result pairs."""
    monkeypatch.setattr(orchestrator, "make_model", lambda max_tokens=None: ScriptedModel([]))
    agent = orchestrator.specialist_agent(orchestrator.SPECS["ideas"], [], "ideas", bus("trip_conversation"))
    agent.messages.append({"role": "user", "content": [{"text": TASK}]})
    for n in range(30):
        call = {"toolUseId": f"t{n}", "name": "web_research", "input": {"query": f"osaka sights {n}"}}
        result = {"toolUseId": f"t{n}", "status": "success", "content": [{"text": "Kyoto temple. " * 350}]}
        agent.messages.append({"role": "assistant", "content": [{"toolUse": call}]})
        agent.messages.append({"role": "user", "content": [{"toolResult": result}]})
    return agent


def assert_task_kept_and_tool_pairs_whole(messages):
    assert messages[0]["role"] == "user" and messages[0]["content"] == [{"text": TASK}]
    for i, message in enumerate(messages):
        for block in message["content"]:
            if "toolResult" in block:
                calls = [b["toolUse"]["toolUseId"] for b in messages[i - 1]["content"] if "toolUse" in b]
                assert block["toolResult"]["toolUseId"] in calls
            if "toolUse" in block:
                results = [b["toolResult"]["toolUseId"] for b in messages[i + 1]["content"] if "toolResult" in b]
                assert block["toolUse"]["toolUseId"] in results


def test_task_survives_a_context_overflow(agent):
    before = len(agent.messages)
    for _ in range(100):  # the first calls only shorten old tool results; messages go once those run out
        agent.conversation_manager.reduce_context(agent, e=ContextWindowOverflowException("too long"))
        if len(agent.messages) < before:
            break
    assert 1 < len(agent.messages) < before
    assert_task_kept_and_tool_pairs_whole(agent.messages)


def test_task_survives_the_trim_after_a_long_run(agent):
    assert len(agent.messages) > 40
    agent.conversation_manager.apply_management(agent)
    assert 1 < len(agent.messages) <= 41
    assert_task_kept_and_tool_pairs_whole(agent.messages)
