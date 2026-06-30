"""
Validates HolmiumConfig on startup.

Checks required fields are non-empty and socket paths are usable.
"""

from pathlib import Path

from .config import HolmiumConfig
from .logger import get_logger

logger = get_logger("config_validator")


def validate_config(config: HolmiumConfig) -> bool:
    errors: list[str] = []

    if not config.user_name:
        errors.append("user_name is required and must be non-empty")

    if not config.holmium_token:
        errors.append("holmium_token is required and must be non-empty")

    socket_fields = [
        ("vllm_socket", config.vllm_socket),
        ("backend_socket", config.backend_socket),
    ]

    for name, path_str in socket_fields:
        path = Path(path_str)
        parent = path.parent
        if not parent.exists():
            errors.append(f"{name} parent directory {parent} does not exist")

    if errors:
        for err in errors:
            logger.error(f"Config validation failed: {err}")
        return False

    logger.info("Config validation passed")
    return True
