from __future__ import annotations

import re
import time
from typing import Any

import html2text
import httpx

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
_REQUEST_DELAY_S = 1.5


def web_search_fallback(query: str, max_results: int = 5) -> list[dict[str, str]]:
    url = "https://html.duckduckgo.com/html/"
    params: dict[str, str] = {"q": query}

    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://html.duckduckgo.com/",
    }

    time.sleep(_REQUEST_DELAY_S)

    try:
        resp = httpx.get(url, params=params, headers=headers, follow_redirects=True, timeout=15.0)
        resp.raise_for_status()
    except httpx.HTTPError:
        return []

    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.ignore_emphasis = False
    markdown = converter.handle(resp.text)

    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    link_pattern = re.compile(r"\[([^\]]*?)\]\((https?://[^\)]+)\)")
    lines = markdown.splitlines()

    current_title = ""
    current_url = ""
    current_snippet_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        m = link_pattern.search(stripped)
        if m:
            title = m.group(1).strip()
            url = m.group(2).strip()

            if title and url and url not in seen_urls:
                if current_title and current_url:
                    snippet = " ".join(current_snippet_lines).strip()[:300]
                    results.append({
                        "title": current_title,
                        "url": current_url,
                        "snippet": snippet,
                    })
                    current_snippet_lines = []

                current_title = title
                current_url = url
                seen_urls.add(url)

                after_link = stripped[m.end():].strip()
                if after_link:
                    current_snippet_lines.append(after_link)

                if len(results) >= max_results:
                    break
        else:
            if current_title:
                current_snippet_lines.append(stripped)

    if current_title and current_url and len(results) < max_results:
        snippet = " ".join(current_snippet_lines).strip()[:300]
        results.append({
            "title": current_title,
            "url": current_url,
            "snippet": snippet,
        })

    return results[:max_results]
