"""Model provider and the Strands hooks every agent shares.

All agents talk to Akamai's hosted inference endpoint through Strands' OpenAI
provider. The endpoint only exposes chat completions (no Responses API), allows
60 requests/min per team and has a 32k-token context, which is why the hooks below
pace requests and trim oversized tool results.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque

from strands.hooks import AfterToolCallEvent, BeforeModelCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry
from strands.models.openai import OpenAIModel

from . import config

TOOL_RESULT_CHARS = 6000


def make_model() -> OpenAIModel:
    return OpenAIModel(
        client_args={"api_key": config.OPENAI_API_KEY, "base_url": config.OPENAI_BASE_URL, "timeout": 180},
        model_id=config.CHAT_MODEL,
        params={"max_tokens": config.MODEL_MAX_TOKENS, "temperature": 0.2},
    )


class RateLimit(HookProvider):
    """Keeps all agents together under the endpoint's requests-per-minute limit."""

    _recent: deque[float] = deque()
    _lock = asyncio.Lock()

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(BeforeModelCallEvent, self.pace)

    async def pace(self, event: BeforeModelCallEvent) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                while self._recent and now - self._recent[0] > 60:
                    self._recent.popleft()
                if len(self._recent) < config.MODEL_RPM:
                    break
                await asyncio.sleep(60 - (now - self._recent[0]) + 0.1)
            self._recent.append(time.monotonic())


class Activity(HookProvider):
    """Streams each tool call to the activity panel and caps tool results at a safe size."""

    def __init__(self, agent: str, emit) -> None:
        self.agent, self.emit = agent, emit

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(BeforeToolCallEvent, self.before_tool)
        registry.add_callback(AfterToolCallEvent, self.after_tool)

    def before_tool(self, event: BeforeToolCallEvent) -> None:
        self.emit("tool", agent=self.agent, tool=event.tool_use["name"], input=event.tool_use.get("input", {}))

    def after_tool(self, event: AfterToolCallEvent) -> None:
        for block in event.result.get("content", []):
            if len(block.get("text", "")) > TOOL_RESULT_CHARS:
                block["text"] = block["text"][:TOOL_RESULT_CHARS] + "\n[truncated]"
