"""Media control tools (stub) — FUTURE FEATURE."""

from tools.registry import register_tool

_STUB_RESPONSE = "Media control coming soon"


@register_tool(
    "media_play",
    "Play or resume media playback.",
)
def media_play() -> str:
    return _STUB_RESPONSE


@register_tool(
    "media_pause",
    "Pause current media playback.",
)
def media_pause() -> str:
    return _STUB_RESPONSE


@register_tool(
    "media_next",
    "Skip to next media track.",
)
def media_next() -> str:
    return _STUB_RESPONSE


@register_tool(
    "media_previous",
    "Go back to previous media track.",
)
def media_previous() -> str:
    return _STUB_RESPONSE


@register_tool(
    "media_volume",
    "Set media volume level.",
    params_schema={
        "type": "object",
        "properties": {
            "level": {
                "type": "integer",
                "description": "Volume level (0-100)",
                "minimum": 0,
                "maximum": 100,
            },
        },
        "required": ["level"],
    },
)
def media_volume(level: int) -> str:
    return _STUB_RESPONSE


@register_tool(
    "media_get_current",
    "Get currently playing media info.",
)
def media_get_current() -> str:
    return _STUB_RESPONSE


@register_tool(
    "media_spotify_search",
    "Search Spotify for tracks, albums, or artists.",
    params_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for Spotify",
            },
        },
        "required": ["query"],
    },
)
def media_spotify_search(query: str) -> str:
    return _STUB_RESPONSE
