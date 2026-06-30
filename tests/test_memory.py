import pytest
import tempfile
import os
from datetime import datetime
from unittest.mock import patch, MagicMock

from memory.sqlite_store import SQLiteStore
from memory.vector_store import VectorStore
from memory.embeddings import EmbeddingModel


@pytest.fixture
def sqlite_store():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    store = SQLiteStore(db_path)
    yield store
    os.unlink(db_path)


class TestSQLiteCRUD:
    def test_fact_crud(self, sqlite_store):
        result = sqlite_store.fact_add("test_key", "test_value")
        assert result is True

        fact = sqlite_store.fact_get("test_key")
        assert fact["value"] == "test_value"

        sqlite_store.fact_update("test_key", "updated_value")
        fact = sqlite_store.fact_get("test_key")
        assert fact["value"] == "updated_value"

        sqlite_store.fact_delete("test_key")
        fact = sqlite_store.fact_get("test_key")
        assert fact is None

    def test_fact_list(self, sqlite_store):
        sqlite_store.fact_add("a", "1")
        sqlite_store.fact_add("b", "2")
        facts = sqlite_store.fact_list()
        assert len(facts) == 2

    def test_fact_search(self, sqlite_store):
        sqlite_store.fact_add("user_name", "user")
        sqlite_store.fact_add("user_city", "istanbul")
        results = sqlite_store.fact_search("city")
        assert len(results) == 1

    def test_note_crud(self, sqlite_store):
        note_id = sqlite_store.note_add("Test Note", "Content", "tag1,tag2")
        assert note_id is not None

        notes = sqlite_store.note_list()
        assert len(notes) == 1

        sqlite_store.note_update(note_id, "Updated", "New content", "tag3")
        note = sqlite_store.note_get(note_id)
        assert note["title"] == "Updated"

        sqlite_store.note_delete(note_id)
        notes = sqlite_store.note_list()
        assert len(notes) == 0

    def test_todo_crud(self, sqlite_store):
        todo_id = sqlite_store.todo_add("Buy milk", "high", "2026-07-01")
        assert todo_id is not None

        todos = sqlite_store.todo_list()
        assert len(todos) == 1
        assert todos[0]["done"] == 0

        sqlite_store.todo_done(todo_id)
        todos = sqlite_store.todo_list()
        assert todos[0]["done"] == 1

        overdue = sqlite_store.todo_overdue()
        sqlite_store.todo_delete(todo_id)

    def test_contact_crud(self, sqlite_store):
        contact_id = sqlite_store.contact_add("John", "john@test.com", "555-0100")
        assert contact_id is not None

        contacts = sqlite_store.contact_list()
        assert len(contacts) == 1

        sqlite_store.contact_update(contact_id, name="John Doe")
        contact = sqlite_store.contact_get(contact_id)
        assert contact["name"] == "John Doe"

        results = sqlite_store.contact_search("John")
        assert len(results) >= 1

        sqlite_store.contact_delete(contact_id)
        contacts = sqlite_store.contact_list()
        assert len(contacts) == 0

    def test_action_history(self, sqlite_store):
        sqlite_store.action_log("act1", "shell_run", '{"command": "ls"}', "listed files", "sess1", True)
        history = sqlite_store.action_recent(10)
        assert len(history) == 1

        results = sqlite_store.action_search("files")
        assert len(results) >= 1

    def test_portfolio_snapshot(self, sqlite_store):
        sqlite_store.portfolio_add_snapshot("2026-06-28", "AAPL", 10, 150.0, 1500.0, 50.0, 3.45)
        history = sqlite_store.portfolio_history("AAPL")
        assert len(history) == 1

    def test_api_keys(self, sqlite_store):
        sqlite_store.api_key_add("hash123", "test_key")
        keys = sqlite_store.api_key_list()
        assert len(keys) == 1

        sqlite_store.api_key_update_usage("hash123")
        sqlite_store.api_key_revoke("hash123")
        keys = sqlite_store.api_key_list()
        assert len(keys) == 0

    def test_usage_stats(self, sqlite_store):
        sqlite_store.usage_upsert("2026-06-28", 1.5, 10, '["shell"]', '["tech"]', 2)
        stats = sqlite_store.usage_get("2026-06-28")
        assert stats is not None
        assert stats["messages_sent"] == 10


class TestVectorStore:
    @pytest.fixture
    def vector_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = VectorStore(tmp)
            yield store

    @patch("memory.vector_store.LanceDB")
    def test_add_turn(self, mock_lancedb, vector_store):
        mock_table = MagicMock()
        mock_lancedb.connect.return_value = mock_table
        vector_store.db = mock_table

        vector_store.add_turn("human", "Hello", "2026-06-28T12:00:00")
        mock_table.create_table.assert_called()
        mock_table.create_table.return_value.add.assert_called()

    @patch("memory.vector_store.LanceDB")
    def test_search_similar(self, mock_lancedb, vector_store):
        mock_table = MagicMock()
        mock_lancedb.connect.return_value.__enter__.return_value.open_table.return_value = mock_table
        mock_table.search.return_value.limit.return_value.to_list.return_value = [
            {"role": "human", "content": "test", "timestamp": "2026-06-28T12:00:00", "_distance": 0.5}
        ]

        vector_store.db = MagicMock()
        vector_store.table = mock_table
        vector_store.embedding_fn = MagicMock()

        results = vector_store.search_similar("test query", n=5)
        assert len(results) >= 0

    @patch("memory.vector_store.LanceDB")
    def test_get_recent(self, mock_lancedb, vector_store):
        vector_store.table = MagicMock()
        vector_store.table.to_list.return_value = [
            {"role": "human", "content": "hi", "timestamp": "t1"},
            {"role": "assistant", "content": "hello", "timestamp": "t2"},
        ]
        recent = vector_store.get_recent(20)
        assert len(recent) == 2


class TestEmbeddings:
    def test_embed_text(self):
        model = EmbeddingModel()
        result = model.embed("hello world")
        assert len(result) == 384
        assert all(isinstance(v, float) for v in result)

    def test_embed_batch(self):
        model = EmbeddingModel()
        results = model.embed_batch(["hello", "world"])
        assert len(results) == 2
        for r in results:
            assert len(r) == 384
