import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .embeddings import ONNXEmbedding

logger = logging.getLogger(__name__)

_DB_URI = "/var/holmium/memory/lancedb"
_COLLECTION = "conversations"


class VectorStore:
    """LanceDB-backed vector store for conversation turns.

    Uses ``all-MiniLM-L6-v2`` (384d) via :class:`ONNXEmbedding` for
    semantic search over the ``conversations`` collection.
    """

    def __init__(self, db_uri: Optional[str] = None) -> None:
        self._db_uri = db_uri or _DB_URI
        self._embedder = ONNXEmbedding()
        self._db: Any = None
        self._table: Any = None
        self._init_db()

    def _init_db(self) -> None:
        import lancedb

        self._db = lancedb.connect(self._db_uri)
        tables = self._db.table_names()
        if _COLLECTION not in tables:
            self._db.create_table(
                _COLLECTION,
                data=[
                    {
                        "vector": self._embedder.embed("init"),
                        "role": "system",
                        "content": "initialised",
                        "timestamp": _now_iso(),
                    }
                ],
                mode="overwrite",
            )
            logger.info("Created LanceDB table '%s' at %s", _COLLECTION, self._db_uri)
        self._table = self._db.open_table(_COLLECTION)

    def add_turn(self, role: str, content: str, timestamp: str) -> None:
        vector = self._embedder.embed(content)
        self._table.add(
            [
                {
                    "vector": vector,
                    "role": role,
                    "content": content,
                    "timestamp": timestamp,
                }
            ]
        )

    def search_similar(self, query: str, n: int = 5) -> List[Dict[str, Any]]:
        vector = self._embedder.embed(query)
        results = (
            self._table.search(vector)
            .metric("cosine")
            .limit(n)
            .to_list()
        )
        out: List[Dict[str, Any]] = []
        for r in results:
            out.append({
                "role": r.get("role", ""),
                "content": r.get("content", ""),
                "timestamp": r.get("timestamp", ""),
                "_distance": r.get("_distance", 0.0),
            })
        return out

    def get_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        all_rows = self._table.to_list()
        sorted_rows = sorted(
            all_rows, key=lambda r: r.get("timestamp", ""), reverse=True
        )[:n]
        out: List[Dict[str, Any]] = []
        for r in sorted_rows:
            out.append({
                "role": r.get("role", ""),
                "content": r.get("content", ""),
                "timestamp": r.get("timestamp", ""),
            })
        return out


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
