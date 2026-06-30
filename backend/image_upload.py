"""File upload endpoint handler — save, detect, auto-summarize documents."""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from .config import HolmiumConfig
from .logger import get_logger

logger = get_logger("image_upload")

_UPLOADS_DIR = Path("/var/holmium/uploads")

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}
_DOCUMENT_EXTENSIONS = {".txt", ".md", ".pdf", ".csv", ".json", ".yaml", ".yml", ".xml", ".html", ".htm"}


async def handle_file_upload(filename: str, content: bytes, content_type: Optional[str] = None) -> dict:
    _UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    ext = os.path.splitext(filename)[1].lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    filepath = _UPLOADS_DIR / unique_name

    try:
        filepath.write_bytes(content)
    except OSError as exc:
        logger.error("Failed to save upload: %s", exc)
        return {"error": f"Failed to save file: {exc}"}

    file_size = len(content)
    logger.info("File uploaded: %s (%d bytes)", unique_name, file_size)

    base: dict = {
        "filename": unique_name,
        "original_name": filename,
        "path": str(filepath),
        "size_bytes": file_size,
        "content_type": content_type or _guess_mime(ext),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }

    if ext in _IMAGE_EXTENSIONS:
        base["type"] = "image"
        base["preview"] = f"data:{base['content_type']};base64,{_b64encode(content)}"
        return base

    if ext in _DOCUMENT_EXTENSIONS:
        base["type"] = "document"
        try:
            text = content.decode("utf-8")[:5000]
            summary = await _summarize_document(text, filename)
            base["summary"] = summary
            base["preview"] = text[:1000]
        except UnicodeDecodeError:
            base["summary"] = "Binary file, could not summarize"
        return base

    base["type"] = "other"
    return base


def _guess_mime(ext: str) -> str:
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".csv": "text/csv",
        ".json": "application/json",
        ".xml": "application/xml",
        ".html": "text/html",
        ".htm": "text/html",
    }
    return mime_map.get(ext, "application/octet-stream")


def _b64encode(data: bytes) -> str:
    import base64
    return base64.b64encode(data).decode("utf-8")


async def _summarize_document(text: str, filename: str) -> str:
    config = HolmiumConfig.load()
    prompt = (
        f"Summarize the following document (filename: {filename}) in 2-3 sentences:\n\n{text[:4000]}"
    )

    try:
        transport = httpx.AsyncHTTPTransport(uds=config.vllm_socket, retries=1)
        async with httpx.AsyncClient(transport=transport, timeout=60.0) as client:
            resp = await client.post(
                "http://localhost/v1/chat/completions",
                json={
                    "model": config.vllm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 256,
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            summary = data["choices"][0]["message"]["content"].strip()
            logger.debug("Document summarized: %s", filename)
            return summary
    except (httpx.HTTPError, httpx.TimeoutException, KeyError) as exc:
        logger.warning("Document summarization failed: %s", exc)
        return "Summarization unavailable"
