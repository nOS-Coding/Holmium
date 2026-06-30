from __future__ import annotations

import json
from json import JSONDecoder
from typing import Any

TOOL_CALL_MARKER = "TOOL_CALL:"


def _extract_json_objects(text: str, start: int = 0) -> list[dict[str, Any]]:
    decoder = JSONDecoder()
    results: list[dict[str, Any]] = []
    pos = start
    while pos < len(text):
        marker_idx = text.find(TOOL_CALL_MARKER, pos)
        if marker_idx == -1:
            break
        json_start = marker_idx + len(TOOL_CALL_MARKER)
        while json_start < len(text) and text[json_start] in (" ", "\t", "\n", "\r"):
            json_start += 1
        if json_start >= len(text) or text[json_start] != "{":
            pos = json_start
            continue
        try:
            obj, idx = decoder.raw_decode(text, json_start)
            if isinstance(obj, dict) and "tool" in obj and "params" in obj:
                results.append(obj)
            pos = idx
        except (json.JSONDecodeError, ValueError):
            pos = json_start + 1
    return results


def find_tool_calls(text: str) -> list[dict[str, Any]]:
    return _extract_json_objects(text)


def has_tool_call(text: str) -> bool:
    return TOOL_CALL_MARKER in text


def parse_tool_call(text: str) -> dict[str, Any] | None:
    calls = _extract_json_objects(text)
    return calls[0] if calls else None
