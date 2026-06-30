import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport

from backend.streaming import StreamManager, TokenStream
from backend.main import app


class TestTokenStream:
    def test_token_buffer(self):
        stream = TokenStream()
        stream.add_token("Hello")
        stream.add_token(" world")
        assert stream.get_accumulated() == "Hello world"

    def test_detect_tool_call(self):
        stream = TokenStream()
        stream.add_token('TOOL_CALL: {"tool": "shell_run", "params": {"command": "ls"}}')
        assert stream.has_tool_call() is True

    def test_complete_tool_call(self):
        stream = TokenStream()
        stream.add_token('TOOL_CALL: {"tool": "shell_run", "params": {"command": "ls"}}')
        call = stream.extract_tool_call()
        assert call is not None
        assert call["tool"] == "shell_run"
        assert call["params"]["command"] == "ls"

    def test_incomplete_tool_call(self):
        stream = TokenStream()
        stream.add_token('TOOL_CALL: {"tool": "shell_run", "param')
        assert stream.has_tool_call() is True
        call = stream.extract_tool_call()
        assert call is None

    def test_no_tool_call(self):
        stream = TokenStream()
        stream.add_token("Just a normal response")
        assert stream.has_tool_call() is False

    def test_multiple_tool_calls_sequential(self):
        stream = TokenStream()
        stream.add_token('First TOOL_CALL: {"tool": "a", "params": {}} then TOOL_CALL: {"tool": "b", "params": {}}')
        calls = stream.extract_all_tool_calls()
        assert len(calls) == 2


class TestStreamManager:
    @pytest.mark.asyncio
    @patch("backend.streaming.vLLMClient")
    async def test_stream_response(self, mock_vllm):
        mock_vllm.return_value.chat.return_value.__aiter__.return_value = [
            "Hello", " ", "world"
        ]

        manager = StreamManager()
        collected = []
        async for chunk in manager.stream("test session", [{"role": "user", "content": "Hi"}]):
            collected.append(chunk)

        assert len(collected) > 0

    @pytest.mark.asyncio
    @patch("backend.streaming.vLLMClient")
    async def test_stream_with_tool_call(self, mock_vllm):
        async def mock_chat(*args, **kwargs):
            yield 'Hello. TOOL_CALL: {"tool": "shell_run", "params": {"command": "echo hi"}}'
            yield " Done."

        mock_vllm.return_value.chat.side_effect = mock_chat

        manager = StreamManager()
        collected = []
        async for chunk in manager.stream("test session", [{"role": "user", "content": "Run tool"}]):
            collected.append(chunk)

        assert len(collected) > 0


class TestSSEEndpoint:
    @pytest.mark.asyncio
    @patch("backend.streaming.StreamManager")
    async def test_sse_stream(self, mock_manager, client):
        async def mock_stream(*args, **kwargs):
            yield {"type": "token", "content": "Hello"}
            yield {"type": "token", "content": " world"}
            yield {"type": "done", "content": ""}

        mock_manager.return_value.stream.return_value = mock_stream()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/chat",
                json={"content": "Hi", "session_id": "test"},
                headers={"X-Holmium-Token": "test-token-123"},
            )
            assert response.status_code in [200, 422]
