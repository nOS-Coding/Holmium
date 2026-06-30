import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)

_VLLM_SOCKET = "/run/holmium/vllm.sock"
_EXTRACT_PROMPT = """\
You are a fact extraction assistant. Given a conversation turn, extract
any factual information the user has shared. Return a JSON list of
[key, value] pairs. Only include information that is explicitly stated.

Examples:
Input: "My name is Nano and I live in Istanbul."
Output: [["user_name", "Nano"], ["user_location", "Istanbul"]]

Input: "I like coffee and my birthday is June 15th."
Output: [["user_preference_drink", "coffee"], ["user_birthday", "June 15th"]]

Input: "What time is it?"
Output: []

Conversation turn:
Role: {role}
Content: {content}

Return ONLY a valid JSON list of [key, value] pairs, nothing else.
"""


class FactExtractor:
    """Lightweight vLLM-based fact extractor.

    Calls the local vLLM instance via its Unix socket and upserts
    extracted facts into the SQLite facts table.
    """

    def __init__(
        self,
        store: Optional[SQLiteStore] = None,
        socket_path: str = _VLLM_SOCKET,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._store = store or SQLiteStore()
        self._socket_path = socket_path
        self._client = http_client or httpx.AsyncClient(
            transport=httpx.AsyncHTTPTransport(
                uds=self._socket_path,
                retries=1,
            ),
            timeout=httpx.Timeout(30.0),
        )

    async def extract_facts(self, conversation_turn: Dict[str, Any]) -> List[Tuple[str, str]]:
        role = conversation_turn.get("role", "user")
        content = conversation_turn.get("content", "")

        if not content.strip():
            return []

        prompt = _EXTRACT_PROMPT.format(role=role, content=content[:2000])

        payload = {
            "model": "default",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 512,
            "temperature": 0.0,
        }

        try:
            response = await self._client.post(
                "http://localhost/v1/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
            raw = (
                body.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
        except (httpx.HTTPError, httpx.TimeoutException, json.JSONDecodeError, KeyError) as exc:
            logger.warning("Fact extraction via vLLM failed: %s", exc)
            return []

        return self._parse_and_store(raw)

    def _parse_and_store(self, raw: str) -> List[Tuple[str, str]]:
        try:
            pairs: List[Tuple[str, str]] = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Fact extractor JSON parse error: %s", raw[:200])
            return []

        if not isinstance(pairs, list):
            return []

        extracted: List[Tuple[str, str]] = []
        for item in pairs:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            key, value = str(item[0]).strip(), str(item[1]).strip()
            if key and value:
                self._store.fact_set(key, value)
                extracted.append((key, value))

        if extracted:
            logger.info("Extracted %d facts from conversation turn", len(extracted))

        return extracted

    async def close(self) -> None:
        await self._client.aclose()
