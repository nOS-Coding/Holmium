"""SIGTERM handler — shutdown memory consolidation."""

import asyncio
import json
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from ..memory.vector_store import VectorStore
from ..memory.sqlite_store import SQLiteStore
from ..memory.vision_docs import VisionDocStore
from .config import HolmiumConfig
from .logger import get_logger

logger = get_logger("shutdown")


class ShutdownHandler:
    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        sqlite_store: Optional[SQLiteStore] = None,
        config: Optional[HolmiumConfig] = None,
    ) -> None:
        self._vector_store = vector_store or VectorStore()
        self._sqlite_store = sqlite_store or SQLiteStore()
        self._config = config or HolmiumConfig.load()
        self._vision_docs = VisionDocStore(self._sqlite_store)
        self._shutting_down = False
        self._orig_sigterm: Any = None
        self._session_summary: Optional[str] = None

    def install(self) -> None:
        self._orig_sigterm = signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        logger.debug("Shutdown handler installed")

    def _handle_signal(self, signum: int, frame: Any) -> None:
        if self._shutting_down:
            logger.warning("Forced shutdown")
            if callable(self._orig_sigterm):
                self._orig_sigterm(signum, frame)
            return
        self._shutting_down = True
        logger.info("Received signal %d, starting graceful shutdown...", signum)
        asyncio.create_task(self.shutdown(signum, frame))

    async def shutdown(self, signum: int, frame: Any) -> None:
        logger.info("=== Holmium shutdown initiated ===")

        try:
            await self._consolidate_conversation_memory()
        except Exception as exc:
            logger.exception("Memory consolidation failed: %s", exc)

        try:
            await self._summarize_vision_docs()
        except Exception as exc:
            logger.exception("Vision doc summarization failed: %s", exc)

        try:
            await self._save_session_as_vision_doc()
        except Exception as exc:
            logger.exception("Session vision doc save failed: %s", exc)

        try:
            self._save_state()
        except Exception as exc:
            logger.exception("State save failed: %s", exc)

        try:
            self._vector_store._db = None
            logger.debug("LanceDB flushed")
        except Exception as exc:
            logger.warning("LanceDB flush failed: %s", exc)

        logger.info("Holmium signing off.")

    async def _consolidate_conversation_memory(self) -> None:
        recent = self._vector_store.get_recent(n=50)
        if not recent:
            logger.debug("No recent turns to consolidate")
            return

        turns_text = "\n".join(f"{t['role']}: {t['content'][:200]}" for t in recent)
        prompt = (
            "Summarize the key information from these recent conversation turns. "
            "Focus on facts about the user, tasks discussed, and decisions made.\n\n"
            f"{turns_text}\n\nSummary:"
        )

        transport = httpx.AsyncHTTPTransport(uds=self._config.vllm_socket, retries=1)
        async with httpx.AsyncClient(transport=transport, timeout=60.0) as client:
            resp = await client.post(
                "http://localhost/v1/chat/completions",
                json={
                    "model": self._config.vllm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1024,
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            summary = data["choices"][0]["message"]["content"].strip()

        if summary:
            self._session_summary = summary
            self._sqlite_store.fact_set("shutdown_summary", summary)
            logger.info("Saved shutdown summary (%d chars)", len(summary))

    async def _save_session_as_vision_doc(self) -> None:
        summary = self._session_summary or self._sqlite_store.fact_get("shutdown_summary")
        if not summary:
            logger.debug("No session summary to save as vision doc")
            return
        recent_count = len(self._vector_store.get_recent(n=0))
        now = datetime.now(timezone.utc)
        content = (
            f"## Session Log — {now.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
            f"**Messages this session:** ~{recent_count}\n\n"
            f"**Summary:**\n{summary}\n\n"
            "_Auto-saved on shutdown for weekly fine-tuning data._"
        )
        title = f"Session {now.strftime('%Y-%m-%d %H:%M')}"
        self._vision_docs.create_vision_doc(title, content)
        logger.info("Session saved as vision doc: %s", title)

    async def _summarize_vision_docs(self) -> None:
        docs = self._vision_docs.list_vision_docs()
        for doc in docs[:5]:
            content = self._vision_docs.get_vision_doc(doc["slug"])
            if content and len(content) > 100:
                decision_key = f"vision_decision_{doc['slug']}"
                existing = self._sqlite_store.fact_get(decision_key)
                if not existing:
                    summary = content[:500]
                    self._sqlite_store.fact_set(decision_key, summary)
                    logger.debug("Summarized vision doc: %s", doc["slug"])

    def _save_state(self) -> None:
        state = {
            "shutdown_time": datetime.now(timezone.utc).isoformat(),
            "mode": self._config.mode_default,
            "version": "1.0.0",
        }
        state_file = Path("/var/holmium/shutdown_state.json")
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state, indent=2))
        logger.info("Shutdown state saved")
