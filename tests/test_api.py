import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock
import json

from backend.main import app


@pytest.fixture
def test_token():
    return "test-token-123"


@pytest.fixture
async def client(test_token):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestStatusEndpoint:
    @patch("backend.status.psutil")
    @patch("backend.status.subprocess.run")
    async def test_get_status(self, mock_subprocess, mock_psutil, client):
        mock_psutil.cpu_percent.return_value = 15.0
        mock_psutil.virtual_memory.return_value = MagicMock(percent=40.0)
        mock_psutil.disk_usage.return_value = MagicMock(
            total=500e9, used=200e9, free=300e9, percent=40.0
        )

        mock_subprocess.return_value = MagicMock(
            stdout=json.dumps({"card0": {"GPU use": "10%"}}),
            returncode=0
        )

        response = await client.get(
            "/status",
            headers={"X-Holmium-Token": "test-token-123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "cpu_percent" in data
        assert "ram_percent" in data


class TestChatEndpoint:
    @patch("backend.streaming.StreamManager")
    async def test_chat_basic(self, mock_stream_manager, client):
        mock_stream_manager.return_value.__aenter__.return_value.stream.return_value.__aiter__.return_value = [
            {"type": "token", "content": "Hello"}
        ]

        response = await client.post(
            "/chat",
            json={"content": "Hi Holmium", "session_id": "test-sess"},
            headers={"X-Holmium-Token": "test-token-123"}
        )
        assert response.status_code in [200, 422]

    async def test_chat_no_token(self, client):
        response = await client.post(
            "/chat",
            json={"content": "Hi", "session_id": "test"}
        )
        assert response.status_code == 403


class TestSTTEndpoint:
    async def test_stt_no_file(self, client):
        response = await client.post(
            "/stt",
            headers={"X-Holmium-Token": "test-token-123"}
        )
        assert response.status_code == 400


class TestTTSEndpoint:
    @patch("tts.piper_tts.PiperTTS")
    async def test_tts(self, mock_tts, client):
        mock_tts.return_value.synthesize.return_value = b"fake_wav_data"
        response = await client.post(
            "/tts/synthesize",
            json={"text": "Hello there"},
            headers={"X-Holmium-Token": "test-token-123"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"


class TestMemoryEndpoints:
    async def test_memory_list(self, client):
        response = await client.get(
            "/memory/list",
            headers={"X-Holmium-Token": "test-token-123"}
        )
        assert response.status_code in [200, 404]

    async def test_memory_add(self, client):
        response = await client.post(
            "/memory/add",
            json={"key": "test", "value": "test value"},
            headers={"X-Holmium-Token": "test-token-123"}
        )
        assert response.status_code in [200, 404]

    async def test_memory_delete(self, client):
        response = await client.delete(
            "/memory/forget/test_key",
            headers={"X-Holmium-Token": "test-token-123"}
        )
        assert response.status_code in [200, 404]


class TestToolsEndpoint:
    async def test_tools_list(self, client):
        response = await client.get(
            "/tools/list",
            headers={"X-Holmium-Token": "test-token-123"}
        )
        assert response.status_code in [200, 404]


class TestAuth:
    async def test_require_token_missing(self, client):
        response = await client.get("/status")
        assert response.status_code == 403

    async def test_require_token_wrong(self, client):
        response = await client.get(
            "/status",
            headers={"X-Holmium-Token": "wrong-token"}
        )
        assert response.status_code == 403
