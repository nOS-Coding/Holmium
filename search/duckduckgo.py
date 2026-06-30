from __future__ import annotations

import time
from typing import Any

from duckduckgo_search import DDGS

_MAX_RETRIES = 3
_RETRY_DELAY_S = 2.0


def web_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    for attempt in range(_MAX_RETRIES):
        try:
            with DDGS() as ddgs:
                raw = list(ddgs.text(query, max_results=max_results))
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                }
                for r in raw
            ]
        except Exception:
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_DELAY_S * (attempt + 1))
                continue
            return []
    return []
