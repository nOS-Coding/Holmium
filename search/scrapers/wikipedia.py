from __future__ import annotations

from typing import Any

import httpx

_WIKI_API = "https://en.wikipedia.org/w/api.php"
_USER_AGENT = "HolmiumAI/1.0 (holmium-vercetti; +https://github.com/nospc/holmium)"


def scrape_wikipedia(query: str) -> dict[str, Any]:
    params: dict[str, str | int] = {
        "action": "query",
        "format": "json",
        "titles": query,
        "prop": "extracts|pageprops",
        "exintro": 1,
        "explaintext": 1,
        "rvprop": "content",
        "redirects": 1,
    }

    headers = {"User-Agent": _USER_AGENT}

    try:
        resp = httpx.get(_WIKI_API, params=params, headers=headers, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return {"title": "", "summary": "", "sections": [], "url": ""}

    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return {"title": "", "summary": "", "sections": [], "url": ""}

    page_id = next(iter(pages))
    page = pages[page_id]

    if "missing" in page:
        return {"title": "", "summary": "", "sections": [], "url": ""}

    title = page.get("title", "")
    extract = page.get("extract", "")
    page_id_str = str(page.get("pageid", ""))
    url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}" if title else ""

    lines = extract.split("\n") if extract else []
    summary = ""
    sections: list[dict[str, str]] = []
    current_section: dict[str, str] | None = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if not summary:
            summary = stripped
            continue
        if stripped.startswith("==") and stripped.endswith("=="):
            section_title = stripped.strip("=").strip()
            if current_section:
                sections.append(current_section)
            current_section = {"title": section_title, "content": ""}
        elif current_section is not None:
            if current_section["content"]:
                current_section["content"] += "\n" + stripped
            else:
                current_section["content"] = stripped

    if current_section:
        sections.append(current_section)

    return {
        "title": title,
        "summary": summary[:1000],
        "sections": sections[:20],
        "url": url,
    }


def register_search_tools(registry: Any) -> None:
    registry.register(
        name="scrape_wikipedia",
        description="Search and retrieve a Wikipedia article summary with section breakdowns.",
        params_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The Wikipedia article title or search query",
                },
            },
            "required": ["query"],
        },
        handler=scrape_wikipedia,
    )
