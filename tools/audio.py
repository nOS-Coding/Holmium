"""Audio system control tools via pactl (PulseAudio/PipeWire)."""

import subprocess
import re
from typing import Any, Dict, List, Optional

from tools.registry import register_tool


def _pactl(args: List[str]) -> str:
    return subprocess.check_output(["pactl"] + args, text=True, stderr=subprocess.PIPE)


def _get_default_sink() -> str:
    out = _pactl(["get-default-sink"])
    return out.strip()


@register_tool(
    "audio_get_volume",
    "Get the current audio volume level (0-100).",
)
def audio_get_volume() -> int:
    try:
        sink = _get_default_sink()
        out = _pactl(["get-sink-volume", sink])
        match = re.search(r"(\d+)%", out)
        if match:
            return int(match.group(1))
        return 0
    except Exception:
        return 0


@register_tool(
    "audio_set_volume",
    "Set the audio volume level (0-100).",
    params_schema={
        "type": "object",
        "properties": {
            "percent": {
                "type": "integer",
                "description": "Volume percentage (0-100)",
                "minimum": 0,
                "maximum": 100,
            },
        },
        "required": ["percent"],
    },
)
def audio_set_volume(percent: int) -> bool:
    try:
        sink = _get_default_sink()
        _pactl(["set-sink-volume", sink, f"{percent}%"])
        return True
    except Exception:
        return False


@register_tool(
    "audio_mute",
    "Mute all audio output.",
)
def audio_mute() -> bool:
    try:
        sink = _get_default_sink()
        _pactl(["set-sink-mute", sink, "1"])
        return True
    except Exception:
        return False


@register_tool(
    "audio_unmute",
    "Unmute all audio output.",
)
def audio_unmute() -> bool:
    try:
        sink = _get_default_sink()
        _pactl(["set-sink-mute", sink, "0"])
        return True
    except Exception:
        return False


@register_tool(
    "audio_toggle_mute",
    "Toggle audio mute state.",
)
def audio_toggle_mute() -> bool:
    try:
        sink = _get_default_sink()
        _pactl(["set-sink-mute", sink, "toggle"])
        return True
    except Exception:
        return False


@register_tool(
    "audio_list_outputs",
    "List all available audio output sinks.",
)
def audio_list_outputs() -> List[Dict[str, Any]]:
    try:
        out = _pactl(["list-sinks"])
        sinks: List[Dict[str, Any]] = []
        current: Dict[str, Any] = {}

        for line in out.split("\n"):
            if "Sink #" in line:
                if current:
                    sinks.append(current)
                current = {"name": "", "description": "", "volume": 0, "muted": False}
            elif "Name:" in line and current:
                current["name"] = line.split(":", 1)[1].strip()
            elif "Description:" in line and current:
                current["description"] = line.split(":", 1)[1].strip()
            elif "Mute:" in line and current:
                current["muted"] = "yes" in line.lower()
            elif "Volume:" in line and current:
                m = re.search(r"(\d+)%", line)
                if m:
                    current["volume"] = int(m.group(1))

        if current:
            sinks.append(current)
        return sinks
    except Exception as e:
        return [{"error": str(e)}]


@register_tool(
    "audio_set_output",
    "Set the default audio output sink.",
    params_schema={
        "type": "object",
        "properties": {
            "sink": {
                "type": "string",
                "description": "Sink name or index to set as default",
            },
        },
        "required": ["sink"],
    },
)
def audio_set_output(sink: str) -> bool:
    try:
        if sink.isdigit():
            _pactl(["set-default-sink", sink])
        else:
            sinks = audio_list_outputs()
            for s in sinks:
                if s["name"] == sink or sink in s.get("description", ""):
                    _pactl(["set-default-sink", s["name"]])
                    return True
        return True
    except Exception:
        return False


@register_tool(
    "audio_get_current_output",
    "Get the current default audio output sink info.",
)
def audio_get_current_output() -> Dict[str, Any]:
    try:
        default = _get_default_sink()
        sinks = audio_list_outputs()
        for s in sinks:
            if s["name"] == default:
                return s
        return {"name": default, "description": default, "volume": 0, "muted": False}
    except Exception as e:
        return {"error": str(e)}
