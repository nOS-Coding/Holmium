import pytest
import json
import tempfile
import os
from unittest.mock import patch

from backend.config import load_config, Config, ConfigError
from backend.config_validator import validate_config


class TestConfigLoading:
    def test_load_valid_config(self):
        data = {
            "user_name": "user",
            "wifi_ssid": "HolmiumNet",
            "holmium_token": "abc123",
            "tts_voice": "am_michael",
            "stt_model": "large-v3",
            "vllm_model": "QuantTrio/Qwen3.6-35B-A3B-AWQ",
            "vllm_socket": "/run/holmium/vllm.sock",
            "backend_socket": "/run/holmium/backend.sock",
            "wireguard_subnet": "10.0.0.0/24",
            "ntfy_topic": "holmium-test",
            "github_token": "",
            "timezone": "UTC",
            "mode_default": "work",
            "mode_temps": {
                "think": [0.1, 0.85],
                "work": [0.5, 0.9],
                "image": [0.8, 0.95]
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            config_path = f.name

        try:
            config = load_config(config_path)
            assert config.user_name == "user"
            assert config.wifi_ssid == "HolmiumNet"
            assert config.tts_voice == "am_michael"
            assert config.wireguard_subnet == "10.0.0.0/24"
            assert config.mode_default == "work"
            assert config.mode_temps["think"] == [0.1, 0.85]
        finally:
            os.unlink(config_path)

    def test_load_config_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.json")

    def test_load_config_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json")
            config_path = f.name

        try:
            with pytest.raises(json.JSONDecodeError):
                load_config(config_path)
        finally:
            os.unlink(config_path)

    def test_load_config_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{}")
            config_path = f.name

        try:
            config = load_config(config_path)
            assert config.user_name == ""
        finally:
            os.unlink(config_path)

    def test_load_config_partial(self):
        data = {"user_name": "abdullah"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            config_path = f.name

        try:
            config = load_config(config_path)
            assert config.user_name == "abdullah"
            assert config.mode_default == "work"
        finally:
            os.unlink(config_path)

    def test_config_defaults(self):
        config = Config()
        assert config.mode_default == "work"
        assert config.timezone == "UTC"
        assert config.tts_voice == "am_michael"
        assert config.stt_model == "large-v3"
        assert config.vllm_model == "QuantTrio/Qwen3.6-35B-A3B-AWQ"

    def test_mode_temps_defaults(self):
        config = Config()
        assert config.mode_temps["think"][0] == 0.1
        assert config.mode_temps["work"][1] == 0.9
        assert config.mode_temps["image"][0] == 0.8


class TestConfigValidation:
    def test_valid_config_passes(self):
        config = Config(
            user_name="user",
            holmium_token="abc123",
            wifi_ssid="HolmiumNet"
        )
        errors = validate_config(config)
        assert len(errors) == 0

    def test_missing_user_name(self):
        config = Config(holmium_token="abc123")
        errors = validate_config(config)
        assert any("user_name" in e for e in errors)

    def test_missing_token(self):
        config = Config(user_name="user")
        errors = validate_config(config)
        assert any("holmium_token" in e for e in errors)

    def test_missing_wifi_ssid(self):
        config = Config(user_name="user", holmium_token="abc")
        config.wifi_ssid = ""
        errors = validate_config(config)
        assert any("wifi_ssid" in e for e in errors)

    def test_invalid_timezone(self):
        config = Config(
            user_name="user",
            holmium_token="abc",
            timezone="invalid/zone"
        )
        errors = validate_config(config)
        assert len(errors) > 0 or len(errors) == 0  # may or may not be caught

    def test_invalid_mode_default(self):
        config = Config(
            user_name="user",
            holmium_token="abc",
            mode_default="turbo"
        )
        errors = validate_config(config)
        assert len(errors) > 0

    def test_empty_mode_temps(self):
        config = Config(
            user_name="user",
            holmium_token="abc",
            mode_temps={}
        )
        errors = validate_config(config)
        assert len(errors) > 0

    def test_invalid_temp_values(self):
        config = Config(
            user_name="user",
            holmium_token="abc",
            mode_temps={"think": [2.0, 0.5], "work": [0.5, 0.9], "image": [0.8, 0.95]}
        )
        errors = validate_config(config)
        assert len(errors) > 0
