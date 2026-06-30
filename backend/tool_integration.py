"""vLLM Tool Call Integration — parse TOOL_CALL: JSON blocks from streaming output."""

import json
from typing import Any, Optional

from .logger import get_logger

logger = get_logger("tool_integration")

_TOOL_CALL_MARKER = "TOOL_CALL:"
_TOOL_RESULT_MARKER = "TOOL_RESULT:"


class ToolIntegration:
    def __init__(self) -> None:
        self._buffer: str = ""
        self._pending: bool = False
        self._tool_json: str = ""

    def process_stream(self, text_chunks: list[str]) -> list[dict]:
        results: list[dict] = []
        for chunk in text_chunks:
            self._buffer += chunk

            if not self._pending and _TOOL_CALL_MARKER in self._buffer:
                self._pending = True
                idx = self._buffer.index(_TOOL_CALL_MARKER)
                self._tool_json = self._buffer[idx + len(_TOOL_CALL_MARKER):]
                self._buffer = self._buffer[:idx]
            elif self._pending:
                self._tool_json += chunk

            if self._pending and self._is_complete_json(self._tool_json):
                tool_call = self._parse_json_safe(self._tool_json)
                if tool_call:
                    results.append({"type": "tool_call", **tool_call})
                self._reset()

        if results:
            logger.debug("Extracted %d tool call(s) from stream", len(results))
        return results

    def feed_chunk(self, chunk: str) -> None:
        if self._pending:
            self._tool_json += chunk

    def has_pending_tool(self) -> bool:
        return self._pending

    def is_tool_complete(self) -> bool:
        if not self._pending:
            return False
        return self._is_complete_json(self._tool_json)

    def parse_tool(self) -> Optional[dict]:
        return self._parse_json_safe(self._tool_json)

    def reset_pending(self) -> None:
        self._pending = False
        self._tool_json = ""

    def needs_continuation(self, tool_result: dict) -> bool:
        success = tool_result.get("success", False)
        if not success:
            return True
        result = tool_result.get("result", "")
        summary = str(result)[:200].lower()
        continuation_triggers = ["more", "continue", "next", "additional", "incomplete"]
        return any(t in summary for t in continuation_triggers)

    def detect_tool_call(self, text: str) -> Optional[dict]:
        if _TOOL_CALL_MARKER not in text:
            return None
        idx = text.index(_TOOL_CALL_MARKER)
        json_str = text[idx + len(_TOOL_CALL_MARKER):]
        return self._parse_json_safe(json_str)

    def _is_complete_json(self, s: str) -> bool:
        s = s.strip()
        if not s:
            return False
        try:
            json.loads(s)
            return True
        except json.JSONDecodeError:
            return False

    def _parse_json_safe(self, s: str) -> Optional[dict]:
        s = s.strip()
        if not s:
            return None
        try:
            return json.loads(s)
        except json.JSONDecodeError as exc:
            logger.debug("Incomplete tool JSON: %s", exc)
            return None

    def _reset(self) -> None:
        self._pending = False
        self._tool_json = ""
