"""Shared agent hooks: a model that calls tools it doesn't have is stopped, not left looping."""

from types import SimpleNamespace

import pytest

from tripwright.llm import Activity, UnknownTools


def call(tool, known=("web_research",)):
    agent = SimpleNamespace(tool_names=list(known))
    return SimpleNamespace(agent=agent, selected_tool=None if tool not in known else object(),
                           tool_use={"name": tool, "input": {}}, cancel_tool=False)


def test_a_made_up_tool_is_cancelled_with_the_real_ones_named():
    hook = Activity("route", lambda *a, **k: None)
    event = call("WebSearch")
    hook.before_tool(event)
    assert event.cancel_tool == ("There is no tool named WebSearch. Your tools are: web_research. "
                                 "Answer now with the structured result if you have what you need.")


def test_a_real_tool_runs():
    hook = Activity("route", lambda *a, **k: None)
    event = call("web_research")
    hook.before_tool(event)
    assert event.cancel_tool is False


def test_repeated_made_up_tools_end_the_attempt():
    hook = Activity("route", lambda *a, **k: None)
    for _ in range(2):
        hook.before_tool(call("WebFetch", known=()))
    with pytest.raises(UnknownTools, match="called tools that don't exist: WebFetch"):
        hook.before_tool(call("WebFetch", known=()))
