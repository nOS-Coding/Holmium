import os
import tempfile
from pathlib import Path

AUDIO_DIR = Path("/var/holmium/audio")


class WhisperSTT:
    """Whisper large-v3 STT engine running on ROCm.

    Loads the model once on startup and keeps it in GPU memory.
    Uses ``whisper`` package with ROCm device detection.
    """

    def __init__(self, model_size: str = "large-v3") -> None:
        self.model_size = model_size
        self._model = None
        self._device = self._detect_device()
        self._load_model()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_device() -> str:
        """Return ``"cuda"`` if ROCm/CUDA is available, else ``"cpu"``."""
        import torch

        if torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def _load_model(self) -> None:
        """Load the Whisper model onto the detected device."""
        import whisper

        self._model = whisper.load_model(self.model_size, device=self._device)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transcribe(self, audio_path: str) -> str:
        """Transcribe an audio file and return the transcript text.

        Parameters
        ----------
        audio_path : str
            Path to a WAV or WebM audio file.

        Returns
        -------
        str
            Transcribed text.
        """
        if self._model is None:
            raise RuntimeError("Whisper model is not loaded")

        AUDIO_DIR.mkdir(parents=True, exist_ok=True)

        result = self._model.transcribe(audio_path, language="en")
        return result.get("text", "").strip()

    def unload(self) -> None:
        """Unload the model from GPU memory."""
        if self._model is not None:
            import gc
            import torch

            del self._model
            self._model = None
            if self._device == "cuda":
                torch.cuda.empty_cache()
            gc.collect()
