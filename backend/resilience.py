"""Graceful degradation — retry, fallback, and failover for vLLM, search, TTS."""

import asyncio
from typing import Any, Callable, Optional

import httpx

from .config import HolmiumConfig
from .logger import get_logger

logger = get_logger("resilience")


class ResilienceHandler:
    def __init__(self, config: Optional[HolmiumConfig] = None) -> None:
        self._config = config or HolmiumConfig.load()

    async def with_vllm_retry(self, func: Callable, timeout: int = 120) -> Any:
        deadline = asyncio.get_event_loop().time() + timeout
        last_exc: Optional[Exception] = None

        while asyncio.get_event_loop().time() < deadline:
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func()
                return func()
            except (httpx.HTTPError, httpx.TimeoutException, ConnectionError) as exc:
                last_exc = exc
                logger.warning("vLLM call failed, retrying in 5s: %s", exc)
                await asyncio.sleep(5)

        logger.error("vLLM retry exhausted after %ds", timeout)
        raise last_exc or TimeoutError("vLLM retry exhausted")

    async def with_search_fallback(self, query: str) -> list[dict]:
        results: list[dict] = []

        try:
            from ..search.duckduckgo import web_search as ddg_search
            results = ddg_search(query, max_results=5)
            if results:
                return results
        except Exception as exc:
            logger.warning("DuckDuckGo search failed: %s", exc)

        try:
            from ..search.searxng import web_search as searxng_search
            results = searxng_search(query, max_results=5)
            if results:
                return results
        except Exception as exc:
            logger.warning("SearXNG search failed: %s", exc)

        try:
            from ..search.ddg_fallback import web_search_fallback as fallback
            results = fallback(query, max_results=5)
            if results:
                return results
        except Exception as exc:
            logger.warning("Fallback search failed: %s", exc)

        return []

    async def with_tts_fallback(self, text: str) -> Optional[str]:
        try:
            from ..tts.piper_tts import PiperTTS

            engine = PiperTTS()
            wav_bytes = engine.synthesize(text)

            import tempfile

            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.write(wav_bytes)
            tmp.close()
            return tmp.name
        except ImportError:
            logger.info("Piper TTS not available, returning text-only")
            return None
        except Exception as exc:
            logger.warning("TTS failed, returning text-only: %s", exc)
            return None
