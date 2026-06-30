import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


class ActionHistory:
    """Records every tool call into the SQLite ``action_history`` table."""

    def __init__(self, store: Optional[SQLiteStore] = None) -> None:
        self._store = store or SQLiteStore()

    def log_action(
        self,
        tool_name: str,
        parameters: Any,
        result_summary: str,
        session_id: str,
        success: bool,
    ) -> str:
        action_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        params_str = (
            str(parameters)[:2000] if parameters is not None else None
        )
        result_str = str(result_summary)[:500] if result_summary else ""

        self._store.log_action(
            action_id=action_id,
            timestamp=timestamp,
            tool_name=tool_name,
            parameters=params_str,
            result_summary=result_str,
            session_id=session_id,
            success=success,
        )
        logger.debug("Action logged: %s — %s", action_id[:8], tool_name)
        return action_id

    def get_recent_actions(self, n: int = 50) -> List[Dict[str, Any]]:
        return self._store.get_recent_actions(n=n)

    def search_actions(self, query: str) -> List[Dict[str, Any]]:
        return self._store.search_actions(query)
