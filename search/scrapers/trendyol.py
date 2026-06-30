from __future__ import annotations

import re
import time
from typing import Any

import httpx
from bs4 import BeautifulSoup

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
_REQUEST_DELAY_S = 2.0


def scrape_trendyol(query: str) -> list[dict[str, str]]:
    url = "https://www.trendyol.com/taranan"
    params = {"q": query}

    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.trendyol.com/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
    }

    time.sleep(_REQUEST_DELAY_S)

    try:
        resp = httpx.get(url, params=params, headers=headers, follow_redirects=True, timeout=20.0)
        resp.raise_for_status()
    except httpx.HTTPError:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results: list[dict[str, str]] = []

    product_cards = soup.select(
        "div.product-card, div.p-card-wrppr, div[class*='product'], div[class*='card'], div[class*='p-card'], a[class*='product']"
    )

    if not product_cards:
        product_cards = soup.find_all("div", class_=True)

    seen_urls: set[str] = set()

    for card in product_cards:
        if len(results) >= 10:
            break

        link_tag = card.find("a") if card.name == "div" else card
        if not link_tag or not link_tag.name == "a":
            link_tag = card.find("a")
        if not link_tag or not link_tag.name == "a":
            continue

        href = link_tag.get("href", "")
        if not href or href.startswith("#"):
            continue

        product_url = f"https://www.trendyol.com{href}" if href.startswith("/") else href
        if product_url in seen_urls:
            continue
        seen_urls.add(product_url)

        name_tag = link_tag.find(
            lambda t: t.name in ("span", "h3", "h4", "div", "p")
            and t.get("class")
            and any(c in " ".join(t.get("class", [])).lower() for c in ["name", "title", "product", "brand", "desc"])
        )
        name = name_tag.get_text(strip=True) if name_tag else ""

        if not name:
            all_spans = link_tag.find_all("span")
            for s in all_spans:
                txt = s.get_text(strip=True)
                if len(txt) > 5:
                    name = txt
                    break

        price_tag = link_tag.find(
            lambda t: t.name in ("span", "div", "p")
            and t.get("class")
            and any(c in " ".join(t.get("class", [])).lower() for c in ["price", "prc", "fiyat", "cost", "sale"])
        )
        price = price_tag.get_text(strip=True) if price_tag else ""

        if not price:
            divs = card.find_all(["span", "div"])
            for d in divs:
                txt = d.get_text(strip=True)
                if "TL" in txt or "₺" in txt:
                    price = txt
                    break

        if not price:
            price_tag = card.find(["span", "div", "p"], class_=re.compile(r"(price|prc|fiyat)", re.I))
            if price_tag:
                price = price_tag.get_text(strip=True)

        results.append({
            "name": name[:200] if name else "Unknown Product",
            "price": price[:100] if price else "",
            "url": product_url,
        })

    return results[:10]


def register_search_tools(registry: Any) -> None:
    registry.register(
        name="scrape_trendyol",
        description="Search Trendyol (Turkish e-commerce) for products. Returns product name, price, and URL.",
        params_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Product search query",
                },
            },
            "required": ["query"],
        },
        handler=scrape_trendyol,
    )
