"""Vision tools — image analysis via vLLM multimodal and URL fetching."""

import base64
import json
import os
import uuid
from pathlib import Path
from typing import Optional

import httpx

from tools.registry import register_tool

VLLM_SOCKET = "/run/holmium/vllm.sock"
UPLOADS_DIR = Path("/var/holmium/uploads")


def _ensure_uploads_dir() -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _base64_encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _guess_mime(image_path: str) -> str:
    ext = Path(image_path).suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    return mime_map.get(ext, "image/png")


def _call_vllm_multimodal(base64_data: str, mime: str, question: Optional[str] = None) -> str:
    """Send base64 image + optional question to vLLM via Unix socket."""
    content = [
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64_data}"}},
    ]
    if question:
        content.append({"type": "text", "text": question})

    payload = {
        "model": "Qwen3.6-35B-A3B-AWQ",
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 2048,
        "temperature": 0.2,
    }

    transport = httpx.HTTPTransport(uds=VLLM_SOCKET)
    with httpx.Client(transport=transport, timeout=120) as client:
        resp = client.post("http://localhost/v1/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


@register_tool(
    "vision_analyze_file",
    "Analyze an image file — describe contents, answer a question about it, or extract text.",
    params_schema={
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Absolute path to the image file",
            },
            "question": {
                "type": "string",
                "description": "Optional question about the image",
            },
        },
        "required": ["image_path"],
    },
)
def analyze_image(image_path: str, question: Optional[str] = None) -> str:
    """Base64-encode image and send to vLLM multimodal via Unix socket."""
    if not os.path.isfile(image_path):
        return f"Error: image not found at {image_path}"

    try:
        b64 = _base64_encode_image(image_path)
        mime = _guess_mime(image_path)
        return _call_vllm_multimodal(b64, mime, question)
    except Exception as e:
        return f"Error analyzing image: {e}"


@register_tool(
    "vision_analyze_url",
    "Download an image from a URL and analyze it with vLLM vision.",
    params_schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL of the image to download and analyze",
            },
        },
        "required": ["url"],
    },
)
def fetch_url_image(url: str) -> str:
    """Download URL image to /var/holmium/uploads/, then analyze it."""
    _ensure_uploads_dir()

    try:
        resp = httpx.get(url, timeout=30, follow_redirects=True)
        resp.raise_for_status()

        ext = ".png"
        ct = resp.headers.get("content-type", "")
        if "jpeg" in ct or "jpg" in ct:
            ext = ".jpg"
        elif "gif" in ct:
            ext = ".gif"
        elif "webp" in ct:
            ext = ".webp"

        filename = f"{uuid.uuid4().hex}{ext}"
        path = UPLOADS_DIR / filename
        path.write_bytes(resp.content)

        b64 = base64.b64encode(resp.content).decode("utf-8")
        mime = _guess_mime(str(path))
        return _call_vllm_multimodal(b64, mime, None)
    except Exception as e:
        return f"Error fetching URL image: {e}"
