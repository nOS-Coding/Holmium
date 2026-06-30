from __future__ import annotations

from typing import TYPE_CHECKING, Any

from search.ddg_fallback import web_search_fallback
from search.duckduckgo import web_search as duckduckgo_search
from search.searxng import web_search as searxng_search

if TYPE_CHECKING:
    from collections.abc import Callable

    Registry = Any


def _format_results(results: list[dict[str, str]]) -> str:
    if not results:
        return "No results found."

    lines: list[str] = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "Untitled")
        url = r.get("url", "")
        snippet = r.get("snippet", "")
        lines.append(f"{i}. **{title}**")
        if url:
            lines.append(f"   {url}")
        if snippet:
            lines.append(f"   > {snippet}")
        lines.append("")
    return "\n".join(lines).strip()


def _web_search(query: str, max_results: int = 5) -> str:
    results = duckduckgo_search(query, max_results=max_results)
    if results:
        return _format_results(results)

    results = web_search_fallback(query, max_results=max_results)
    if results:
        return _format_results(results)

    results = searxng_search(query, max_results=max_results)
    if results:
        return _format_results(results)

    return "No results found."


def register_search_tools(registry: Registry) -> None:
    registry.register(
        name="web_search",
        description="Search the web for current information using DuckDuckGo (with fallback to SearXNG on Pi). Returns a numbered list of results with title, URL, and snippet.",
        params_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        handler=_web_search,
    )
