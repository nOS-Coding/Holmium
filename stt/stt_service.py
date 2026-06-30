import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.auth import require_token
from backend.logger import get_logger

from .whisper_stt import WhisperSTT, AUDIO_DIR

logger = get_logger("stt")

stt_router = APIRouter(prefix="/stt", dependencies=[])

_stt_engine: WhisperSTT | None = None


def get_stt_engine() -> WhisperSTT:
    global _stt_engine
    if _stt_engine is None:
        _stt_engine = WhisperSTT()
    return _stt_engine


@stt_router.on_event("startup")
async def _init_engine():
    logger.info("Initialising Whisper STT engine")
    get_stt_engine()


@stt_router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)) -> dict:
    """Accept a WAV/WebM upload, transcribe, return JSON with transcript."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "audio.wav").suffix or ".wav"
    dest = AUDIO_DIR / f"{uuid.uuid4().hex}{ext}"

    try:
        content = await file.read()
        dest.write_bytes(content)
        logger.info("Saved audio to %s (%d bytes)", dest, len(content))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save audio: {exc}")

    try:
        engine = get_stt_engine()
        transcript = engine.transcribe(str(dest))
        logger.info("Transcription result: %r", transcript[:80])
    except Exception as exc:
        logger.error("Transcription failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")
    finally:
        dest.unlink(missing_ok=True)

    return {"transcript": transcript}
