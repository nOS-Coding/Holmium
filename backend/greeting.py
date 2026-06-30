"""Boot greeting — generate casual vLLM greeting and play via Piper TTS."""

import asyncio
from datetime import datetime
from typing import Optional

import httpx

from .config import HolmiumConfig
from .logger import get_logger

logger = get_logger("greeting")


async def generate_greeting() -> str:
    config = HolmiumConfig.load()
    hour = datetime.now().hour

    if hour < 12:
        time_greeting = "morning"
    elif hour < 18:
        time_greeting = "afternoon"
    else:
        time_greeting = "evening"

    name = config.user_name or "there"

    prompt = (
        f"Generate a very short, casual greeting for {name}. "
        f"It's {time_greeting}. Keep it to one sentence, under 20 words. "
        "Be warm but brief. You are Holmium."
    )

    try:
        transport = httpx.AsyncHTTPTransport(uds=config.vllm_socket, retries=1)
        async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
            resp = await client.post(
                "http://localhost/v1/chat/completions",
                json={
                    "model": config.vllm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 64,
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            greeting = data["choices"][0]["message"]["content"].strip()
            if greeting:
                logger.info("Greeting generated: %s", greeting)
                return greeting
    except (httpx.HTTPError, httpx.TimeoutException, KeyError) as exc:
        logger.warning("Greeting generation failed: %s", exc)

    fallback = f"Good {time_greeting}, {name}."
    logger.info("Using fallback greeting: %s", fallback)
    return fallback


async def play_greeting() -> None:
    try:
        from ..tts.piper_tts import PiperTTS

        greeting = await generate_greeting()
        engine = PiperTTS()
        wav_bytes = engine.synthesize(greeting)

        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "aplay", tmp_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=30)
            logger.debug("Greeting played via aplay")
        except (FileNotFoundError, asyncio.TimeoutError) as exc:
            logger.warning("Failed to play greeting: %s", exc)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        logger.info("Greeting played: %s", greeting[:50])
    except ImportError:
        logger.debug("Piper TTS not available, skipping greeting audio")
    except Exception as exc:
        logger.warning("Greeting playback failed: %s", exc)
