"""
Holmium configuration management.

Loads and saves /etc/holmium/config.json as a typed dataclass.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path("/etc/holmium/config.json")

_MODE_TEMPS_DEFAULT = {
    "think": {"temp": 0.1, "top_p": 0.85},
    "work": {"temp": 0.5, "top_p": 0.9},
    "image": {"temp": 0.8, "top_p": 0.95},
}


@dataclass
class HolmiumConfig:
    user_name: str = ""
    wifi_ssid: str = ""
    holmium_token: str = ""
    tts_voice: str = "am_michael"
    stt_model: str = "large-v3"
    vllm_model: str = ""
    vllm_socket: str = "/run/holmium/vllm.sock"
    backend_socket: str = "/run/holmium/backend.sock"
    wireguard_subnet: str = "10.0.0.0/24"
    ntfy_topic: str = ""
    github_token: str = ""
    timezone: str = "UTC"
    mode_default: str = "work"
    debian_user: str = ""
    mode_temps: dict = field(default_factory=lambda: _MODE_TEMPS_DEFAULT.copy())
    nas_enabled: bool = True
    nas_path: str = "/"
    nas_port: int = 8766
    nas_user: str = "holmium"
    nas_password: str = ""

    @classmethod
    def load(cls) -> "HolmiumConfig":
        if not CONFIG_PATH.exists():
            return cls()
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
        mode_temps = data.get("mode_temps")
        if mode_temps is None:
            mode_temps = _MODE_TEMPS_DEFAULT.copy()
        return cls(
            user_name=data.get("user_name", ""),
            wifi_ssid=data.get("wifi_ssid", ""),
            holmium_token=data.get("holmium_token", ""),
            tts_voice=data.get("tts_voice", "am_michael"),
            stt_model=data.get("stt_model", "large-v3"),
            vllm_model=data.get("vllm_model", ""),
            vllm_socket=data.get("vllm_socket", "/run/holmium/vllm.sock"),
            backend_socket=data.get("backend_socket", "/run/holmium/backend.sock"),
            wireguard_subnet=data.get("wireguard_subnet", "10.0.0.0/24"),
            ntfy_topic=data.get("ntfy_topic", ""),
            github_token=data.get("github_token", ""),
            timezone=data.get("timezone", "UTC"),
            mode_default=data.get("mode_default", "work"),
            debian_user=data.get("debian_user", ""),
            mode_temps=mode_temps,
            nas_enabled=data.get("nas_enabled", True),
            nas_path=data.get("nas_path", "/"),
            nas_port=data.get("nas_port", 8766),
            nas_user=data.get("nas_user", "holmium"),
            nas_password=data.get("nas_password", ""),
        )

    def save(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        with open(CONFIG_PATH, "w") as f:
            json.dump(data, f, indent=2)
