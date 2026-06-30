from search.duckduckgo import web_search as duckduckgo_search
from search.ddg_fallback import web_search_fallback
from search.searxng import web_search as searxng_search
from search.search_tool import register_search_tools

__all__ = [
    "duckduckgo_search",
    "web_search_fallback",
    "searxng_search",
    "register_search_tools",
]
