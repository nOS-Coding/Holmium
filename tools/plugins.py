from __future__ import annotations

import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from typing import Any, Callable

from tools.registry import registry

logger = logging.getLogger("holmium.tools.plugins")

PLUGIN_DIR = Path("/etc/holmium/plugins")

_tool_decorators: list[dict[str, Any]] = []


def holmium_tool(
    name: str,
    description: str,
    params_schema: dict | None = None,
) -> Callable:
    def decorator(func: Callable) -> Callable:
        schema = params_schema or {"type": "object", "properties": {}, "required": []}
        registry.register(name, description, schema, func)
        _tool_decorators.append({
            "name": name,
            "description": description,
            "params_schema": schema,
            "handler": func,
        })
        logger.debug("Registered plugin tool: %s from %s", name, func.__module__)
        return func

    return decorator


def scan_plugins() -> list[str]:
    if not PLUGIN_DIR.exists():
        logger.info("Plugin directory %s does not exist — skipping", PLUGIN_DIR)
        return []
    loaded: list[str] = []
    for pyfile in sorted(PLUGIN_DIR.glob("*.py")):
        if pyfile.name.startswith("_"):
            continue
        module_name = f"holmium_plugin_{pyfile.stem}"
        if module_name in sys.modules:
            loaded.append(pyfile.stem)
            continue
        try:
            spec = importlib.util.spec_from_file_location(module_name, pyfile)
            if spec is None or spec.loader is None:
                logger.warning("Could not load plugin: %s", pyfile)
                continue
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)
            loaded.append(pyfile.stem)
            logger.info("Loaded plugin: %s", pyfile.stem)
        except Exception:
            logger.exception("Failed to load plugin %s", pyfile)
    return loaded


def get_plugin_tools() -> list[dict[str, Any]]:
    return list(_tool_decorators)


def get_tool_decorator() -> Callable:
    return holmium_tool
