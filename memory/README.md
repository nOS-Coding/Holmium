# memory — SQLite + LanceDB Vector Store

Dual-store memory system. SQLite for structured/conversation data, LanceDB for vector embeddings (384d, cosine, all-MiniLM-L6-v2 ONNX). Memory consolidation on shutdown.

- `schema.sql` — SQLite schema
- `store.py` — LanceDB vector store logic
- `consolidate.py` — shutdown consolidation (flush + summary)
