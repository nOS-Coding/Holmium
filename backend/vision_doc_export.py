"""Vision doc export — single markdown or zipped archive."""

import io
import zipfile
from pathlib import Path
from typing import Optional

from ..memory.vision_docs import VisionDocStore
from .logger import get_logger

logger = get_logger("vision_doc_export")


def export_vision_doc(slug: str) -> Optional[str]:
    store = VisionDocStore()
    content = store.get_vision_doc(slug)
    if content is None:
        logger.warning("Vision doc not found: %s", slug)
        return None
    return content


def export_all_vision_docs() -> Optional[bytes]:
    store = VisionDocStore()
    docs = store.list_vision_docs()
    if not docs:
        logger.info("No vision docs to export")
        return None

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc in docs:
            slug = doc.get("slug", "")
            content = store.get_vision_doc(slug)
            if content:
                filename = f"{slug}.md"
                zf.writestr(filename, content)
                logger.debug("Added %s to export zip", filename)

    result = buf.getvalue()
    logger.info("Exported %d vision docs (%d bytes)", len(docs), len(result))
    return result
