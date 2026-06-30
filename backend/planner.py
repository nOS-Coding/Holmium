"""Task planner — decompose requests into plans and execute steps."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from .config import HolmiumConfig
from .logger import get_logger
from ..memory.sqlite_store import SQLiteStore

logger = get_logger("planner")

_PLAN_PROMPT = """\
You are Holmium's planning system. Given a user request, decompose it into
a numbered execution plan. Each step should describe ONE concrete action.
Steps run sequentially — later steps can depend on earlier ones.

Return JSON:
{
  "plan": [
    {"step": 1, "action": "description of what to do"},
    {"step": 2, "action": "next action..."}
  ]
}

If the request is simple enough that no decomposition is needed,
return {"plan": [], "simple": true}.

Request: {request}
"""


class PlanManager:
    def __init__(
        self,
        store: Optional[SQLiteStore] = None,
        config: Optional[HolmiumConfig] = None,
    ) -> None:
        self._store = store or SQLiteStore()
        self._config = config or HolmiumConfig.load()

    async def detect_plan_intent(self, message: str) -> Optional[list[dict]]:
        """Ask vLLM whether this message needs a multi-step plan."""
        try:
            transport = httpx.AsyncHTTPTransport(
                uds=self._config.vllm_socket, retries=1
            )
            async with httpx.AsyncClient(
                transport=transport, timeout=30.0
            ) as client:
                resp = await client.post(
                    "http://localhost/v1/chat/completions",
                    json={
                        "model": self._config.vllm_model,
                        "messages": [
                            {
                                "role": "user",
                                "content": _PLAN_PROMPT.format(request=message),
                            }
                        ],
                        "max_tokens": 1024,
                        "temperature": 0.1,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                raw = data["choices"][0]["message"]["content"].strip()
                result = json.loads(raw)
                if result.get("simple"):
                    return None
                return result.get("plan", [])
        except Exception as exc:
            logger.warning("Plan detection failed: %s", exc)
            return None

    def create_plan(self, description: str, steps: list[dict]) -> str:
        plan_id = uuid.uuid4().hex[:12]
        plan = {
            "id": plan_id,
            "description": description,
            "steps_json": json.dumps(steps),
            "current_step": 0,
            "status": "active",
            "result": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._store.plan_save(plan)
        logger.info(
            "Plan %s created: %s (%d steps)",
            plan_id,
            description[:60],
            len(steps),
        )
        return plan_id

    def get_active_plan(self) -> Optional[dict]:
        return self._store.plan_get_active()

    def advance_plan(self, plan_id: str) -> Optional[dict]:
        plan = self._store.plan_get(plan_id)
        if not plan:
            return None
        steps: list[dict] = json.loads(plan["steps_json"])
        next_step = plan["current_step"] + 1
        if next_step >= len(steps):
            plan["status"] = "completed"
            plan["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._store.plan_save(plan)
            logger.info("Plan %s completed", plan_id)
            return None
        plan["current_step"] = next_step
        plan["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._store.plan_save(plan)
        return steps[next_step]

    def fail_plan(self, plan_id: str, error: str) -> None:
        plan = self._store.plan_get(plan_id)
        if plan:
            plan["status"] = "failed"
            plan["result"] = error
            plan["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._store.plan_save(plan)
            logger.warning("Plan %s failed: %s", plan_id, error)

    def cancel_plan(self, plan_id: str) -> None:
        plan = self._store.plan_get(plan_id)
        if plan:
            plan["status"] = "cancelled"
            plan["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._store.plan_save(plan)
            logger.info("Plan %s cancelled", plan_id)

    def get_plan_context(self) -> str:
        plan = self.get_active_plan()
        if not plan or plan["status"] != "active":
            return ""
        steps: list[dict] = json.loads(plan["steps_json"])
        current = plan["current_step"]
        lines = ["### Active Plan", f"Goal: {plan['description']}", "Progress:"]
        for i, step in enumerate(steps):
            prefix = "  [DONE]" if i < current else "  [NOW]" if i == current else "  [PENDING]"
            lines.append(f"{prefix} Step {step['step']}: {step['action']}")
        return "\n".join(lines)
