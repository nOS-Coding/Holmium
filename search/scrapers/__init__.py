from __future__ import annotations

from typing import TYPE_CHECKING, Any

from search.scrapers.wikipedia import scrape_wikipedia
from search.scrapers.weather import scrape_weather
from search.scrapers.github import scrape_github
from search.scrapers.youtube import scrape_youtube_transcript
from search.scrapers.trendyol import scrape_trendyol
from search.scrapers.news import scrape_news, scrape_reddit

if TYPE_CHECKING:
    Registry = Any

__all__ = [
    "scrape_wikipedia",
    "scrape_weather",
    "scrape_github",
    "scrape_youtube_transcript",
    "scrape_trendyol",
    "scrape_news",
    "scrape_reddit",
    "register_all_scrapers",
]


def register_all_scrapers(registry: Registry) -> None:
    from search.scrapers.wikipedia import register_search_tools as reg_wiki
    from search.scrapers.weather import register_search_tools as reg_weather
    from search.scrapers.github import register_search_tools as reg_github
    from search.scrapers.youtube import register_search_tools as reg_youtube
    from search.scrapers.trendyol import register_search_tools as reg_trendyol
    from search.scrapers.news import register_search_tools as reg_news

    reg_wiki(registry)
    reg_weather(registry)
    reg_github(registry)
    reg_youtube(registry)
    reg_trendyol(registry)
    reg_news(registry)
