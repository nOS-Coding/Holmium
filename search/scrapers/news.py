from __future__ import annotations

import itertools
import time
from typing import Any

import httpx
from bs4 import BeautifulSoup

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
_REQUEST_DELAY_S = 1.0


def _fetch_html(url: str, params: dict[str, str] | None = None) -> str | None:
    time.sleep(_REQUEST_DELAY_S)
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
    }
    try:
        resp = httpx.get(url, params=params, headers=headers, follow_redirects=True, timeout=20.0)
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPError:
        return None


def scrape_news(query: str, max_results: int = 5) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []

    html = _fetch_html("https://lite.cnn.com/search", {"q": query})
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a[href*='/article/']"):
            href = link.get("href", "")
            title = link.get_text(strip=True)
            if title and href:
                results.append({
                    "title": title[:200],
                    "url": href if href.startswith("http") else f"https://lite.cnn.com{href}",
                    "source": "CNN Lite",
                })
                if len(results) >= max_results:
                    break

    if len(results) < max_results:
        html = _fetch_html("https://news.google.com/search", {"q": query, "hl": "en-US"})
        if html:
            soup = BeautifulSoup(html, "html.parser")
            seen_urls: set[str] = {r["url"] for r in results}

            for article in soup.select("article") or soup.select("div[class*='article']"):
                links = article.find_all("a")
                for a in links:
                    href = a.get("href", "")
                    title = a.get_text(strip=True)
                    if title and len(title) > 20 and href and href not in seen_urls:
                        if href.startswith("./"):
                            href = "https://news.google.com" + href[1:]
                        elif href.startswith("/"):
                            href = "https://news.google.com" + href
                        results.append({
                            "title": title[:200],
                            "url": href,
                            "source": "Google News",
                        })
                        seen_urls.add(href)
                        break
                if len(results) >= max_results:
                    break

    if not results:
        duck_url = "https://html.duckduckgo.com/html/"
        html = _fetch_html(duck_url, {"q": query})
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for result in soup.select(".result"):
                link = result.select_one(".result__a")
                snippet = result.select_one(".result__snippet")
                if link:
                    href = link.get("href", "")
                    title = link.get_text(strip=True)
                    if title and href:
                        results.append({
                            "title": title[:200],
                            "url": href,
                            "source": snippet.get_text(strip=True)[:150] if snippet else "DuckDuckGo",
                        })
                        if len(results) >= max_results:
                            break

    return results[:max_results]


def scrape_reddit(
    query: str,
    subreddit: str = "",
    sort: str = "relevance",
    limit: int = 10,
) -> list[dict[str, Any]]:
    if subreddit:
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params: dict[str, str | int] = {"q": query, "sort": sort, "limit": limit, "restrict_sr": "on"}
    else:
        url = "https://www.reddit.com/search.json"
        params = {"q": query, "sort": sort, "limit": limit}

    headers = {"User-Agent": "HolmiumAI/1.0 (Linux; Arch; OpenRC)"}
    time.sleep(_REQUEST_DELAY_S)

    try:
        resp = httpx.get(url, params=params, headers=headers, follow_redirects=True, timeout=20.0)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return []

    children = data.get("data", {}).get("children", [])
    results: list[dict[str, Any]] = []

    for child in children:
        post = child.get("data", {})
        permalink = post.get("permalink", "")
        results.append({
            "title": post.get("title", ""),
            "url": f"https://www.reddit.com{permalink}",
            "score": post.get("score", 0),
            "num_comments": post.get("num_comments", 0),
            "subreddit": post.get("subreddit", ""),
            "author": post.get("author", ""),
            "created_utc": post.get("created_utc", 0),
            "selftext": (post.get("selftext", "") or "")[:500],
        })
        if len(results) >= limit:
            break

    return results


def register_search_tools(registry: Any) -> None:
    registry.register(
        name="scrape_news",
        description="Search for latest news on a topic. Aggregates from Google News, CNN Lite, and DuckDuckGo.",
        params_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "News topic to search for",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        handler=scrape_news,
    )

    registry.register(
        name="scrape_reddit",
        description="Search Reddit for posts matching a query, optionally restricted to a subreddit.",
        params_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "subreddit": {
                    "type": "string",
                    "description": "Subreddit name (without r/), optional",
                },
                "sort": {
                    "type": "string",
                    "description": "Sort order: relevance, hot, top, new (default relevance)",
                    "default": "relevance",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results (default 10)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
        handler=scrape_reddit,
    )
