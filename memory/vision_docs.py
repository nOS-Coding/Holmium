import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)

_DOCS_DIR = "/var/holmium/vision_docs"


class VisionDocStore:
    """Vision Doc storage — markdown files + SQLite fact summaries."""

    def __init__(self, store: Optional[SQLiteStore] = None) -> None:
        self._store = store or SQLiteStore()
        Path(_DOCS_DIR).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _slugify(title: str) -> str:
        slug = title.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        return slug or "untitled"

    @staticmethod
    def _now_ts() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    def create_vision_doc(self, title: str, content: str) -> str:
        slug = self._slugify(title)
        ts = self._now_ts()
        filename = f"{ts}_{slug}.md"
        path = os.path.join(_DOCS_DIR, filename)

        full_md = f"# {title}\n\n{content.strip()}\n"
        Path(path).write_text(full_md, encoding="utf-8")

        summary = content.strip()[:500]
        fact_key = f"vision_doc_{slug}"
        self._store.fact_set(fact_key, summary)

        logger.info("Vision doc created: %s", path)
        return slug

    def list_vision_docs(self) -> List[Dict[str, Any]]:
        docs: List[Dict[str, Any]] = []
        if not os.path.isdir(_DOCS_DIR):
            return docs

        for fname in sorted(os.listdir(_DOCS_DIR), reverse=True):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(_DOCS_DIR, fname)
            st = os.stat(fpath)
            slug = self._slug_from_filename(fname)
            fact = self._store.fact_get(f"vision_doc_{slug}")
            docs.append({
                "title": self._title_from_file(fpath) or fname,
                "path": fpath,
                "slug": slug,
                "created_at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                "summary": fact["value"] if fact and "value" in fact else "",
            })
        return docs

    def get_vision_doc(self, slug_or_path: str) -> Optional[str]:
        path = self._resolve_path(slug_or_path)
        if path is None:
            return None
        try:
            return Path(path).read_text(encoding="utf-8")
        except (OSError, FileNotFoundError):
            return None

    def delete_vision_doc(self, slug_or_path: str) -> bool:
        path = self._resolve_path(slug_or_path)
        if path is None:
            return False
        slug = self._slug_from_filename(os.path.basename(path))
        try:
            os.remove(path)
            self._store.fact_delete(f"vision_doc_{slug}")
            logger.info("Vision doc deleted: %s", path)
            return True
        except OSError:
            return False

    # ── helpers ────────────────────────────────────────────────────────────

    def _resolve_path(self, slug_or_path: str) -> Optional[str]:
        if os.path.isfile(slug_or_path):
            return slug_or_path
        slug = self._slugify(slug_or_path)
        if not os.path.isdir(_DOCS_DIR):
            return None
        for fname in os.listdir(_DOCS_DIR):
            if fname.endswith(".md") and self._slug_from_filename(fname) == slug:
                return os.path.join(_DOCS_DIR, fname)
        return None

    @staticmethod
    def _slug_from_filename(fname: str) -> str:
        # YYYYMMDD_HHMMSS_slug.md  →  slug
        parts = fname.replace(".md", "").split("_", 2)
        return parts[-1] if len(parts) == 3 else parts[0]

    @staticmethod
    def _title_from_file(fpath: str) -> str:
        try:
            with open(fpath, encoding="utf-8") as f:
                first = f.readline().strip()
            if first.startswith("# "):
                return first[2:].strip()
        except OSError:
            pass
        return ""
