# Handoff: an agent that searches too long loses its task

Written 2026-10-11 at about 05:00 Central by the chat that diagnosed this. You implement the fix; that chat only checks on it.

## What happened

In a `DEMO_MODE` test run (trip created at 03:06 on 2026-10-11 on a throwaway server, route Tokyo, Kyoto, Osaka, Tokyo) the ideas agent was sent back once with

```
BadRequestError: Error code: 400 - {'error': {'message': 'No user query found in messages.', 'type': 'BadRequestError', 'param': None, 'code': 400}}
```

then timed out after 240 seconds, so the picks list was empty. The user suspected a server restart. It was not. The agent's own log from that run is in the screenshot `design/implemented/10-agents-working.jpg`: search after search for Kamakura, Osaka and Nara, and the line "The search keeps returning Kyoto results. Let me try a different".

## Why

1. **Demo mode answers with the wrong pages.** `replay` in `backend/tripwright/recorded.py` (line 39) returns the recorded result for the same call, or else the recorded call to the same tool that shares the most words. `backend/tripwright/fixtures/recorded.json` holds 80 recorded searches (keys starting `search:`): 41 mention Tokyo, 35 Kyoto, none Osaka, Nara or Kamakura. So those searches kept coming back with Kyoto pages and the agent kept searching.
2. **The conversation outgrows the model.** Each replayed result is 3,500 to 5,500 characters, and the endpoint's context is 32k tokens.
3. **Strands then drops the task.** Agents are built without a conversation manager (`backend/tripwright/orchestrator.py`, line 168), so they get Strands' default `SlidingWindowConversationManager` with a window of 40 messages. On a context overflow its `reduce_context` first shortens the oldest tool results, then removes the oldest messages. In a conversation that is all tool calls the only place it can cut is an assistant-tool-call / tool-result pair, so message 0, the agent's task, goes. The code is in `backend/.venv/lib/python3.13/site-packages/strands/agent/conversation_manager/sliding_window_conversation_manager.py`.
4. **The endpoint refuses a request with no user message.** Checked directly on 2026-10-11 with two small requests to the Akamai endpoint: system + assistant tool call + tool result gets exactly the 400 above; the same request with a user message in front gets a normal answer.
5. **The orchestrator treats the 400 as a result to send back** (`SpecialistNode._run`, `orchestrator.py` line 189), the agent carries on from the broken conversation, and the 240 seconds run out.

Step 2 was not replayed; the rest is from the code, the fixtures, the screenshot and the direct check in step 4.

The same manager also trims to 40 messages after every run (`apply_management`). An agent that used more than about 20 rounds of tool calls on its first attempt therefore starts a sent-back second attempt without its original task. The lodging agent on trip `trip_479d20ea` did 27 rounds that morning. That case still has a user message (the send-back), so it does not produce the 400, but the agent is working from the feedback alone.

## What the user approved

Keep the agent's task pinned in the conversation.

## Suggested change

`SlidingWindowConversationManager` in this Strands version (1.59.0) takes `pin_first`: "Number of messages at the start of the conversation to permanently pin. Pinned messages are protected from eviction during context reduction."

Pass `conversation_manager=SlidingWindowConversationManager(pin_first=1)` where the specialists are built, `orchestrator.py` line 168. That is one argument and one import. The reviewer (line 219) and the draft agent (`backend/tripwright/draft.py`, line 144) make a single call with no tools; leave them.

Confirm rather than assume that the conversation stays valid after a trim with the first message pinned: every tool result must still follow its tool call, or the endpoint will reject it for a different reason.

Out of scope: the fixtures, the time limit, any prompt, and making demo mode useful for routes outside Tokyo and Kyoto. There is also no recorded list of places for the demo trip (see "Without keys, and DEMO_MODE" in `README.md`); recording one is separate work.

## Ground rules

- Read "Start here" and "Gotchas" in `HANDOFF.md` first. The user's global rules apply: minimum code, surgical changes, verify against a concrete check.
- Several chats share this working folder. Uncommitted work that is not yours is in it: a payments chat's (`backend/tripwright/api.py`, `config.py`, `models.py`, `payments.py`, `backend/pyproject.toml`, `backend/tests/conftest.py`, `backend/tests/test_payments.py`, several frontend files) and deploy/docs changes. Another agent is changing lodging in `backend/tripwright/specialists.py`, `toolbox.py` and `tools/lodging.py` at the same time. Your files are `orchestrator.py` and a new test file. Make small targeted edits and leave everything else alone.
- Do not commit, push or deploy. The user decides that.
- Do not restart or stop the server on port 8000; it is the user's. Never print `.env` or `.env.hosted`.

## How to check it

1. **Baseline first:** `cd backend && .venv/bin/python -m pytest -q` (about 5 seconds). Note what fails before you touch anything; the payments chat's tests may fail for reasons that are not yours.
2. **A new test, written before the change and failing without it,** in a new file `backend/tests/test_conversation.py`. Build a specialist's agent the way `SpecialistNode._run` does (`ScriptedModel` in `backend/tests/test_orchestrator.py` shows how the tests stand in for the model; pull the agent's construction into a small helper if the test needs to share it). Give it a task message followed by 30 assistant-tool-call / tool-result pairs with long results, then:
   - call `agent.conversation_manager.reduce_context(agent, e=ContextWindowOverflowException("too long"))` until messages have actually been removed, and assert the first message is still the task and that no tool result is left without its tool call;
   - call `agent.conversation_manager.apply_management(agent)` on more than 40 messages and assert the same.
3. **The whole suite passes** apart from anything that failed in the baseline.
4. **On the real endpoint, only if time allows** (a few minutes and some of the user's inference quota): a second backend on port **8013** with `DEMO_MODE=true DATA_DIR=<your scratch folder>` in front of the command, `/api/health` saying `sqlite`. Create a 7-day trip to somewhere the recordings do not cover, such as Osaka, and watch the ideas agent on the Agents tab with **Show details**. The "No user query found in messages" error must not appear. The agent may still time out or return a thin list, because the recordings only cover Tokyo and Kyoto. Report that if you see it; do not fix it here.

Then replace the "In the `DEMO_MODE` test run ..." bullet under "Not done or not verified" in `HANDOFF.md` with what is true now.

## When you finish

Add a section `## Result` at the bottom of this file: the files you changed, what you ran and what it showed, and anything left undone. Do the same if you stop early. Another chat reads this file every few minutes to see whether the work is done.

## Result

Done on 2026-10-11. Not committed, not pushed, not deployed. No server was started, stopped or restarted.

**Files changed**

- `backend/tripwright/orchestrator.py`: the specialist's `Agent(...)` call moved, unchanged, out of `SpecialistNode._run` into a module function `specialist_agent(spec, tools, node, events)` so the test builds the same agent the app does; it now also passes `conversation_manager=SlidingWindowConversationManager(pin_first=1)`. One new import. The reviewer and the draft agent are untouched.
- `backend/tests/test_conversation.py`: new, two tests.
- `HANDOFF.md`: the "In the `DEMO_MODE` test run ..." bullet under "Not done or not verified" replaced with what is true now. Nothing else in it touched.

**What was run and what it showed**

1. Baseline before any change: `119 passed`.
2. The two new tests, with the helper in place but without the pin: both failed, the conversation starting with an assistant tool call (the bug). With the pin: both pass. Each builds a task plus 30 tool call / tool result pairs with 4,900-character results, then checks the first message is still the task and every tool result still sits right after its tool call, once after `reduce_context(agent, e=ContextWindowOverflowException(...))` has removed messages and once after `apply_management` on 61 messages (41 are left: the task and the last 20 pairs).
3. Whole suite after the change: `126 passed`, nothing failing. (The count is above 119 + 2 because another chat added tests in the meantime.)
4. The pin is a `metadata` key on the message. Formatted with `OpenAIModel.format_request_messages`, the trimmed conversation goes out as system, user, assistant `tool_calls`, tool, ... with only `role` and `content` on the user message, so the endpoint never sees the pin.
5. Three small requests to the real endpoint (about 60 output tokens each):
   - task, tool call, result: answered.
   - task, send-back, tool call, result: answered. This shape is new with the pin. On a second or third attempt the trim can land on the send-back message, which leaves two user messages in a row; the endpoint accepts it.
   - tool call, result with no task: still `400 No user query found in messages`, as the diagnosis said.

**Left undone**

- Step 4, a whole trip on the real endpoint on port 8013, was not run. Starting a server needs an entry in `.claude/launch.json`, which has another chat's uncommitted changes in it. The checks in 5 cover what the endpoint accepts; nothing has shown a full agent run going through an overflow.
- The server on port 8000 still runs the old code until the user restarts it.
- Out of scope and unchanged: a demo-mode trip to cities outside Tokyo and Kyoto can still have its ideas agent search until the 240 seconds run out, because every search is answered with Tokyo or Kyoto pages. The agent will now keep its task while it does so; it may still return nothing.
