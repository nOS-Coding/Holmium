"""Browser session state — remembers last 5 URLs."""

from typing import Any, Dict, List

_HISTORY: List[Dict[str, str]] = []
_MAX_HISTORY = 5


def add_to_history(url: str, title: str) -> None:
    """Add a URL + title to the browsing history (capped at 5)."""
    entry = {"url": url, "title": title}
    if _HISTORY and _HISTORY[-1]["url"] == url:
        return
    _HISTORY.append(entry)
    while len(_HISTORY) > _MAX_HISTORY:
        _HISTORY.pop(0)


def get_history() -> List[Dict[str, str]]:
    """Return the last 5 browsed URLs."""
    return list(_HISTORY)


def clear_history() -> None:
    """Clear the browsing history."""
    _HISTORY.clear()
