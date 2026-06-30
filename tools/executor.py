from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from tools.registry import registry

logger = logging.getLogger("holmium.tools.executor")

try:
    from memory.action_history import log_action
except ImportError:

    async def log_action(
        action_id: str,
        tool_name: str,
        parameters: dict,
        result_summary: str,
        session_id: str,
        success: bool,
    ) -> None:
        pass


def execute_tool(name: str, params: dict) -> dict:
    result = registry.execute(name, params)
    return result


def execute_with_logging(name: str, params: dict, session_id: str) -> dict:
    result = execute_tool(name, params)
    try:
        import asyncio

        result_summary = str(result.get("result", ""))[:500] if result.get("success") else str(result.get("error", ""))[:500]
        asyncio.create_task(
            log_action(
                action_id=str(uuid.uuid4()),
                tool_name=name,
                parameters=params,
                result_summary=result_summary,
                session_id=session_id,
                success=result.get("success", False),
            )
        )
    except Exception:
        logger.exception("Failed to log action for tool %s", name)
    return result
