"""FramePack video generation tool — image-to-video on local GPU."""

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Optional

from tools.registry import register_tool

VIDEOS_DIR = Path("/var/holmium/videos")
SCRIPT_DIR = Path(__file__).parent


def _ensure_dirs() -> None:
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)


def _check_framepack() -> Optional[str]:
    fp_dir = Path.home() / "FramePack"
    if not fp_dir.exists():
        return "FramePack repo not found at ~/FramePack. Clone it first: git clone https://github.com/lllyasviel/FramePack.git"
    script = SCRIPT_DIR / "framepack_generate.py"
    if not script.exists():
        return f"Generation script not found: {script}"
    return None


@register_tool(
    "video_generate",
    "Generate a video from an image and text prompt using FramePack.",
    params_schema={
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Path to the input image file",
            },
            "prompt": {
                "type": "string",
                "description": "Text prompt describing the desired video",
            },
            "duration": {
                "type": "number",
                "description": "Video length in seconds (1–120, default 5)",
                "default": 5.0,
            },
            "seed": {
                "type": "integer",
                "description": "Random seed for reproducibility (0 = random)",
                "default": 0,
            },
            "steps": {
                "type": "integer",
                "description": "Number of inference steps (default 25)",
                "default": 25,
            },
            "guidance_scale": {
                "type": "number",
                "description": "Distilled CFG scale (default 10.0)",
                "default": 10.0,
            },
            "negative_prompt": {
                "type": "string",
                "description": "Negative prompt",
                "default": "",
            },
        },
        "required": ["image_path", "prompt"],
    },
)
def video_generate(
    image_path: str,
    prompt: str,
    duration: float = 5.0,
    seed: int = 0,
    steps: int = 25,
    guidance_scale: float = 10.0,
    negative_prompt: str = "",
) -> dict:
    err = _check_framepack()
    if err:
        return {"success": False, "result": None, "error": err}

    if not os.path.isfile(image_path):
        return {"success": False, "result": None, "error": f"Image not found: {image_path}"}

    _ensure_dirs()
    job_id = uuid.uuid4().hex[:12]
    output_dir = VIDEOS_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    script = SCRIPT_DIR / "framepack_generate.py"

    try:
        proc = subprocess.run(
            [
                sys.executable, str(script),
                "--image", image_path,
                "--prompt", prompt,
                "--output", str(output_dir),
                "--duration", str(duration),
                "--seed", str(seed),
                "--steps", str(steps),
                "--cfg", str(guidance_scale),
                "--negative", negative_prompt,
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "result": None, "error": "Video generation timed out after 600 seconds"}
    except Exception as e:
        return {"success": False, "result": None, "error": f"Subprocess error: {e}"}

    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        try:
            parsed = json.loads(proc.stdout)
            return {"success": False, "result": None, "error": parsed.get("error", stderr)}
        except (json.JSONDecodeError, KeyError):
            return {"success": False, "result": None, "error": stderr or f"Process exited with code {proc.returncode}"}

    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"success": False, "result": None, "error": f"Failed to parse generation output: {proc.stdout[:200]}"}

    if not result.get("success"):
        return {"success": False, "result": None, "error": result.get("error", "Unknown error")}

    return {"success": True, "result": result, "error": None}


@register_tool(
    "video_list",
    "List previously generated videos.",
    params_schema={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Max videos to return (default 10)",
                "default": 10,
            },
        },
    },
)
def video_list(limit: int = 10) -> dict:
    _ensure_dirs()
    videos = []
    if VIDEOS_DIR.exists():
        entries = sorted(VIDEOS_DIR.iterdir(), key=os.path.getmtime, reverse=True)
        for entry in entries[:limit]:
            final = entry / "final.mp4"
            if final.exists():
                videos.append({
                    "id": entry.name,
                    "path": str(final),
                    "created": os.path.getmtime(final),
                })
    return {"success": True, "result": {"videos": videos, "count": len(videos)}, "error": None}
