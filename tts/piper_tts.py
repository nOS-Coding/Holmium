"""Piper TTS engine — fast, local, natural-sounding speech synthesis.

Uses piper-tts with ``en_US-lessac-medium`` (American male) voice.
Falls back to silent WAV if the piper package is unavailable.
"""

import io
import struct
import wave
from pathlib import Path
from typing import Any

import numpy as np

_VOICE = "en_US-lessac-medium"
_VOICE_URL = (
    f"https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/"
    f"{_VOICE}.onnx"
)
_VOICES_DIR = Path("/usr/lib/holmium/tts/voices")
_SAMPLE_RATE = 22050


class PiperTTS:
    """Piper TTS engine with ``en_US-lessac-medium`` (American male) voice.

    The model is downloaded on first use from HuggingFace and cached
    at ``/usr/lib/holmium/tts/voices/``.
    """

    def __init__(self, voice: str = _VOICE) -> None:
        self.voice = voice
        self._pipeline: Any = None
        self._load_pipeline()

    def _load_pipeline(self) -> None:
        try:
            import piper

            voice_path = _VOICES_DIR / f"{self.voice}.onnx"
            if not voice_path.exists():
                self._download_voice(voice_path)
            self._pipeline = piper.PiperVoice.load(str(voice_path))
        except ImportError:
            pass

    def _download_voice(self, dest: Path) -> None:
        import httpx

        dest.parent.mkdir(parents=True, exist_ok=True)
        with httpx.Client(follow_redirects=True, timeout=120) as client:
            resp = client.get(_VOICE_URL)
            resp.raise_for_status()
            dest.write_bytes(resp.content)

    def synthesize(self, text: str) -> bytes:
        """Synthesise text and return raw WAV bytes.

        Returns 22.05 kHz 16-bit signed mono PCM (standard WAV container).
        """
        if self._pipeline is None:
            return self._synthesize_fallback(text)

        import piper

        audio: np.ndarray = self._pipeline.synthesize(text)
        return self._numpy_to_wav(audio, _SAMPLE_RATE)

    def _synthesize_fallback(self, text: str) -> bytes:
        """Lightweight fallback when the piper package is unavailable.

        Generates a minimal silent WAV with the correct duration to
        preserve pipeline compatibility during development.
        """
        duration_s = max(len(text) * 0.06, 1.0)
        n_samples = int(_SAMPLE_RATE * duration_s)
        audio = np.zeros(n_samples, dtype=np.int16)
        return self._numpy_to_wav(audio, _SAMPLE_RATE)

    @staticmethod
    def _numpy_to_wav(audio: np.ndarray, sample_rate: int) -> bytes:
        """Convert a float32 [-1, 1] or int16 numpy array to WAV bytes."""
        if audio.dtype == np.float32:
            audio = np.clip(audio, -1.0, 1.0)
            audio = (audio * 32767).astype(np.int16)
        elif audio.dtype != np.int16:
            audio = audio.astype(np.int16)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio.tobytes())
        return buf.getvalue()
