from __future__ import annotations

from typing import Any

from youtube_transcript_api import YouTubeTranscriptApi


def scrape_youtube_transcript(video_id: str) -> str:
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "tr"])
    except Exception:
        return ""

    lines: list[str] = []
    for entry in transcript_list:
        text = entry.get("text", "").strip()
        if text:
            lines.append(text)

    return " ".join(lines)


def register_search_tools(registry: Any) -> None:
    registry.register(
        name="scrape_youtube_transcript",
        description="Fetch the full text transcript of a YouTube video by its video ID. Supports English and Turkish.",
        params_schema={
            "type": "object",
            "properties": {
                "video_id": {
                    "type": "string",
                    "description": "The YouTube video ID (e.g. 'dQw4w9WgXcQ')",
                },
            },
            "required": ["video_id"],
        },
        handler=scrape_youtube_transcript,
    )
