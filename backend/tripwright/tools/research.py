"""Web research through the Strands Tavily tools, trimmed to fit a 32k-token context.

The vended tavily_search/tavily_extract return the raw API response as text; here it is
cut down to title, URL and a short excerpt per result, and each result's text is saved
as an evidence snapshot so every researched fact links back to what was read.
"""

from __future__ import annotations

import ast
from datetime import datetime

from strands_tools.tavily import tavily_extract, tavily_search

from .. import evidence
from ..recorded import cached

MAX_RESULTS = 5
EXCERPT_CHARS = 700
PAGE_CHARS = 5000
WEEK = 7 * 24 * 3600


def _payload(result: dict) -> dict:
    text = result["content"][0]["text"]
    if result["status"] != "success":
        raise RuntimeError(text)
    data = ast.literal_eval(text)  # the tool returns str(dict)
    if "results" not in data:
        raise RuntimeError(str(data)[:300])
    return data


async def search(query: str) -> list[dict]:
    """Search the web. Returns [{title, url, excerpt, evidence_url, fetched_at}]."""

    async def fetch():
        data = _payload(await tavily_search(query=query, max_results=MAX_RESULTS, search_depth="basic"))
        results = []
        for r in data["results"]:
            snapshot = f"{r.get('title', '')}\n{r['url']}\n\n{r.get('content', '')}"
            results.append({
                "title": r.get("title", ""), "url": r["url"], "excerpt": r.get("content", "")[:EXCERPT_CHARS],
                "evidence_url": await evidence.save(f"search {r['url']}", snapshot.encode(), "txt"),
                "fetched_at": datetime.now().isoformat(),
            })
        return results

    return await cached(f"search:{query}".lower(), fetch, ttl_s=WEEK)


async def read(url: str) -> dict:
    """Read one page. Returns {url, text, evidence_url, fetched_at}."""

    async def fetch():
        data = _payload(await tavily_extract(urls=[url], extract_depth="basic", format="markdown"))
        if not data["results"]:
            raise RuntimeError(f"Could not read {url}")
        text = data["results"][0].get("raw_content", "")
        return {"url": url, "text": text[:PAGE_CHARS], "fetched_at": datetime.now().isoformat(),
                "evidence_url": await evidence.save(f"page {url}", text.encode(), "txt")}

    return await cached(f"read:{url}".lower(), fetch, ttl_s=WEEK, fuzzy=False)
