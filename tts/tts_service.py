from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend.auth import require_token
from backend.logger import get_logger

from .piper_tts import PiperTTS

logger = get_logger("tts")

tts_router = APIRouter(prefix="/tts", dependencies=[])

_tts_engine: PiperTTS | None = None


def get_tts_engine() -> PiperTTS:
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = PiperTTS()
    return _tts_engine


@tts_router.on_event("startup")
async def _init_engine():
    logger.info("Initialising Piper TTS engine")
    get_tts_engine()


@tts_router.post("/synthesize")
async def synthesize_text(data: dict) -> Response:
    """Accept ``{"text": "..."}``, synthesise speech, return WAV audio."""
    text = data.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Missing 'text' field")

    if len(text) > 4096:
        raise HTTPException(status_code=400, detail="Text too long (max 4096 chars)")

    try:
        engine = get_tts_engine()
        wav_bytes = engine.synthesize(text)
        logger.info("Synthesised %d chars -> %d bytes WAV", len(text), len(wav_bytes))
    except Exception as exc:
        logger.error("TTS synthesis failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {exc}")

    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={"Content-Disposition": 'inline; filename="holmium.wav"'},
    )
