from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("holmium.tools.registry")


@dataclass
class ToolDef:
    name: str
    description: str
    params_schema: dict
    handler: Callable[..., Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}

    def register(
        self,
        name: str,
        description: str,
        params_schema: dict,
        handler: Callable[..., Any],
    ) -> None:
        if name in self._tools:
            logger.warning("Tool %r already registered — overwriting", name)
        self._tools[name] = ToolDef(
            name=name,
            description=description,
            params_schema=params_schema,
            handler=handler,
        )
        logger.debug("Registered tool: %s", name)

    def get(self, name: str) -> ToolDef:
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        return self._tools[name]

    def list_tools(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "params_schema": t.params_schema,
            }
            for t in sorted(self._tools.values(), key=lambda x: x.name)
        ]

    def execute(self, name: str, params: dict) -> dict:
        try:
            tool = self.get(name)
            result = tool.handler(**params)
            return {"success": True, "result": result, "error": None}
        except KeyError as e:
            return {"success": False, "result": None, "error": str(e)}
        except Exception as e:
            logger.exception("Tool %r failed with params %r", name, params)
            return {"success": False, "result": None, "error": f"{type(e).__name__}: {e}"}

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


registry = ToolRegistry()


def register_tool(name: str, description: str, params_schema: dict | None = None):
    """Decorator that registers a tool function in the global registry."""
    def decorator(func):
        registry.register(name, description, params_schema or {}, func)
        return func
    return decorator
