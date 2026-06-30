"""Conversation modes (Think / Work / Image) with file persistence."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .logger import get_logger

logger = get_logger("modes")

_MODE_FILE = Path("/var/holmium/mode.json")


@dataclass
class ModeConfig:
    name: str
    temperature: float
    top_p: float
    enable_thinking: bool = False


MODES: dict[str, ModeConfig] = {
    "think": ModeConfig("think", 0.1, 0.85, enable_thinking=True),
    "work": ModeConfig("work", 0.5, 0.9),
    "image": ModeConfig("image", 0.8, 0.95),
    "help": ModeConfig("help", 0.3, 0.85),
}


class ModeManager:
    def __init__(self, mode_file: Optional[Path] = None) -> None:
        self._mode_file = mode_file or _MODE_FILE

    def get_current_mode(self) -> ModeConfig:
        try:
            if self._mode_file.exists():
                data = json.loads(self._mode_file.read_text())
                mode_name = data.get("mode", "work")
                return self.get_mode_config(mode_name)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read mode file: %s", exc)
        return self.get_mode_config("work")

    def set_mode(self, mode_name: str) -> ModeConfig:
        config = self.get_mode_config(mode_name)
        self._mode_file.parent.mkdir(parents=True, exist_ok=True)
        self._mode_file.write_text(
            json.dumps({"mode": mode_name, "temperature": config.temperature, "top_p": config.top_p}, indent=2)
        )
        logger.info("Mode set to %s (temp=%.2f, top_p=%.2f)", mode_name, config.temperature, config.top_p)
        return config

    def get_mode_config(self, mode_name: str) -> ModeConfig:
        if mode_name not in MODES:
            logger.warning("Unknown mode '%s', falling back to 'work'", mode_name)
            mode_name = "work"
        return MODES[mode_name]
