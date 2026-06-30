"""Context assembly for vLLM calls — system prompt, memory, history, truncation."""

from pathlib import Path
from typing import Any, Optional

import tiktoken

from ..memory.vector_store import VectorStore
from ..memory.sqlite_store import SQLiteStore
from .config import HolmiumConfig
from .logger import get_logger
from .modes import MODES
from .planner import PlanManager
from .proactive import ProactiveEngine

logger = get_logger("context")

_SYSTEM_PROMPT_PATH = Path("/etc/holmium/system_prompt.txt")
_RESPONSE_RULES_PATH = Path("/etc/holmium/response_rules.txt")
_MAX_TOKENS = 48000
_ENCODING = "cl100k_base"

_COWORK_CONTEXT = """\
You are currently in HELP mode. You have a second cursor on the user's Mac via the cowork tools.
You can directly:
- Read, write, delete, move, and list files on the Mac
- Run shell commands and background processes
- List and kill processes
- Run full system diagnostics (CPU, RAM, disk, network, battery)
- Check real-time performance metrics
- Clean up Downloads, Desktop, temp files
- Analyze Mac state and suggest optimizations
- Run AppleScript to control any Mac app (Chrome, PowerPoint, Finder, etc.)
- Open/close Chrome tabs and create PowerPoint presentations
- Open apps and Finder windows
- Take screenshots
- Send macOS notifications and speak text aloud via TTS

You act as a collaborative partner. The user will ask you to do things on their Mac.
Do them immediately and report results concisely. Be proactive about suggesting improvements.
"""


class ContextAssembler:
    def __init__(
        self,
        config: HolmiumConfig,
        vector_store: Optional[VectorStore] = None,
        sqlite_store: Optional[SQLiteStore] = None,
    ) -> None:
        self._config = config
        self._vector_store = vector_store or VectorStore()
        self._sqlite_store = sqlite_store or SQLiteStore()
        self._planner = PlanManager(store=self._sqlite_store, config=config)
        self._proactive = ProactiveEngine(store=self._sqlite_store)
        self._tokenizer = tiktoken.get_encoding(_ENCODING)

    def assemble(self, user_message: str, session: Any, mode: str = "work") -> list[dict]:
        messages: list[dict] = []

        system = self._load_system_prompt()
        if self._config.user_name:
            system = system.replace("{user_name}", self._config.user_name)
        messages.append({"role": "system", "content": system})

        if mode == "help":
            messages.append({"role": "system", "content": _COWORK_CONTEXT.strip()})

        similar = self._vector_store.search_similar(user_message, n=5)
        for turn in similar:
            messages.append({"role": turn["role"], "content": turn["content"]})

        recent = self._vector_store.get_recent(n=20)
        seen = set()
        for turn in recent:
            dedup_key = f"{turn['role']}:{turn['content'][:100]}"
            if dedup_key not in seen:
                seen.add(dedup_key)
                messages.append({"role": turn["role"], "content": turn["content"]})

        facts = self._sqlite_store.fact_list()
        if facts:
            fact_block = "### Known Facts\n"
            for f in facts:
                fact_block += f"- {f['key']}: {f['value']}\n"
            messages.append({"role": "system", "content": fact_block.strip()})

        if session and hasattr(session, "messages"):
            for msg in session.messages[-50:]:
                messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        messages.append({"role": "user", "content": user_message})

        plan_context = self._planner.get_plan_context()
        if plan_context:
            messages.append({"role": "system", "content": plan_context})

        proactive_context = self._proactive.get_proactive_context()
        if proactive_context:
            messages.append({"role": "system", "content": proactive_context})

        rules = self._load_response_rules()
        if rules:
            messages.append({"role": "system", "content": rules})

        messages = self._truncate(messages)
        return messages

    @property
    def planner(self) -> PlanManager:
        return self._planner

    def count_tokens(self, text: str) -> int:
        return len(self._tokenizer.encode(text, disallowed_special=()))

    def _load_system_prompt(self) -> str:
        try:
            return _SYSTEM_PROMPT_PATH.read_text().strip()
        except FileNotFoundError:
            logger.warning("System prompt not found at %s", _SYSTEM_PROMPT_PATH)
            return "You are Holmium, a helpful AI assistant."
        except OSError as exc:
            logger.error("Failed to read system prompt: %s", exc)
            return "You are Holmium, a helpful AI assistant."

    def _load_response_rules(self) -> str:
        try:
            return _RESPONSE_RULES_PATH.read_text().strip()
        except FileNotFoundError:
            return ""
        except OSError as exc:
            logger.error("Failed to read response rules: %s", exc)
            return ""

    def _truncate(self, messages: list[dict]) -> list[dict]:
        total = sum(self.count_tokens(m.get("content", "")) for m in messages)
        if total <= _MAX_TOKENS:
            return messages

        logger.warning("Context exceeds %d tokens (%d), truncating oldest turns", _MAX_TOKENS, total)

        system_msgs = [m for m in messages if m["role"] == "system"]
        non_system = [m for m in messages if m["role"] != "system"]

        while non_system and total > _MAX_TOKENS:
            removed = non_system.pop(0)
            total -= self.count_tokens(removed.get("content", ""))

        result = system_msgs + non_system
        if not result:
            result = messages[-2:]

        return result
