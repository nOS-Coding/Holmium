"""Web browsing tools using httpx, BeautifulSoup, and html2text."""

from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup
import html2text

from tools.registry import register_tool
from tools.browser_state import add_to_history

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _fetch_html(url: str) -> str:
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        resp = client.get(url, headers=_HEADERS)
        resp.raise_for_status()
        return resp.text


def _extract_content(html: str, url: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    if soup.title:
        title = soup.title.get_text(strip=True)

    converter = html2text.HTML2Text()
    converter.body_width = 0
    converter.ignore_links = False
    converter.ignore_images = False
    markdown = converter.handle(html)

    links: List[Dict[str, str]] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if text and href and not href.startswith("#"):
            links.append({"text": text, "href": href})

    images: List[str] = []
    for img in soup.find_all("img", src=True):
        src = img["src"]
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            from urllib.parse import urlparse
            parsed = urlparse(url)
            src = f"{parsed.scheme}://{parsed.netloc}{src}"
        images.append(src)

    add_to_history(url, title)
    return {
        "title": title,
        "content_markdown": markdown[:10000],
        "links": links[:100],
        "images": images[:20],
        "url": url,
    }


@register_tool(
    "browse_url",
    "Fetch a URL and return its content as markdown with links and images.",
    params_schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Full URL to browse",
            },
        },
        "required": ["url"],
    },
)
def browse_url(url: str) -> Dict[str, Any]:
    """Fetch a URL and return title, markdown content, links, and images."""
    try:
        html = _fetch_html(url)
        return _extract_content(html, url)
    except Exception as e:
        return {"error": str(e), "url": url}


@register_tool(
    "browse_search_and_open",
    "Search DuckDuckGo and open the top result automatically.",
    params_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
        },
        "required": ["query"],
    },
)
def browse_search_and_open(query: str) -> Dict[str, Any]:
    """Search DuckDuckGo, get the top result, and browse it."""
    try:
        search_url = f"https://html.duckduckgo.com/html/?q={httpx.utils.quote(query)}"
        html = _fetch_html(search_url)
        soup = BeautifulSoup(html, "html.parser")

        result_link = soup.select_one("a.result__a")
        if result_link and result_link.get("href"):
            href = result_link["href"]
            top_url = href
            if top_url.startswith("//"):
                top_url = "https:" + top_url
            result_html = _fetch_html(top_url)
            return _extract_content(result_html, top_url)

        return {"error": "No search results found", "query": query}
    except Exception as e:
        return {"error": str(e), "query": query}


@register_tool(
    "browse_follow_link",
    "Follow a link by visible text on a page and return its content.",
    params_schema={
        "type": "object",
        "properties": {
            "base_url": {
                "type": "string",
                "description": "URL of the page containing the link",
            },
            "link_text": {
                "type": "string",
                "description": "Visible text of the link to follow",
            },
        },
        "required": ["base_url", "link_text"],
    },
)
def browse_follow_link(base_url: str, link_text: str) -> Dict[str, Any]:
    """Find a link by text on a page and follow it."""
    try:
        html = _fetch_html(base_url)
        soup = BeautifulSoup(html, "html.parser")

        target = None
        for a in soup.find_all("a", href=True):
            if link_text.lower() in a.get_text(strip=True).lower():
                target = a["href"]
                break

        if target is None:
            return {"error": f"Link text '{link_text}' not found on page", "base_url": base_url}

        from urllib.parse import urljoin
        full_url = urljoin(base_url, target)
        result_html = _fetch_html(full_url)
        return _extract_content(result_html, full_url)
    except Exception as e:
        return {"error": str(e), "base_url": base_url, "link_text": link_text}


@register_tool(
    "browse_extract_table",
    "Extract HTML tables from a URL as a list of dicts.",
    params_schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL containing HTML tables",
            },
        },
        "required": ["url"],
    },
)
def browse_extract_table(url: str) -> List[Dict[str, Any]]:
    """Extract all HTML tables from a URL as JSON objects."""
    try:
        html = _fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        tables: List[Dict[str, Any]] = []

        for i, table in enumerate(soup.find_all("table")):
            headers: List[str] = []
            rows: List[List[str]] = []

            thead = table.find("thead")
            if thead:
                headers = [th.get_text(strip=True) for th in thead.find_all("th")]

            for tr in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cells:
                    rows.append(cells)

            if not headers and rows:
                headers = rows[0]
                rows = rows[1:]

            if not headers:
                headers = [f"col_{j}" for j in range(len(rows[0]))] if rows else []

            data: List[Dict[str, str]] = []
            for row in rows:
                row_data: Dict[str, str] = {}
                for j, cell in enumerate(row):
                    if j < len(headers):
                        row_data[headers[j]] = cell
                if row_data:
                    data.append(row_data)

            tables.append({"table_index": i, "headers": headers, "rows": data, "row_count": len(data)})

        return tables
    except Exception as e:
        return [{"error": str(e)}]
