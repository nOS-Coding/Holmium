# Adding Tools — Plugin API

Holmium has a plugin system that lets you add custom tools without modifying core code.

## Plugin Directory

Plugins go in `/etc/holmium/plugins/` as `.py` files. Each file is auto-loaded on startup.

## Writing a Plugin

```python
# /etc/holmium/plugins/my_tool.py
from tools.plugins import holmium_tool

@holmium_tool(
    name="get_time",
    description="Get current time for a timezone",
    params_schema={
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "IANA timezone name (e.g. UTC)"
            }
        },
        "required": ["timezone"]
    }
)
def get_time(timezone: str) -> dict:
    from datetime import datetime
    import zoneinfo
    tz = zoneinfo.ZoneInfo(timezone)
    now = datetime.now(tz)
    return {
        "timezone": timezone,
        "time": now.strftime("%H:%M:%S"),
        "date": now.strftime("%Y-%m-%d")
    }
```

## Tool Contract

Each tool function must:
1. Return a `dict` with at least a `success` key (bool)
2. Accept parameters matching the JSON schema
3. Be registered via the `@holmium_tool` decorator

## @holmium_tool Decorator

| Argument | Type | Description |
|----------|------|-------------|
| `name` | str | Unique tool name |
| `description` | str | What the tool does |
| `params_schema` | dict | JSON Schema for parameters |
| `category` | str | Optional category (default "custom") |

## Tool Result Format

```python
{
    "success": True,
    "result": "Tool output here"
}
```

On error:
```python
{
    "success": False,
    "error": "Error message"
}
```

## Testing a Plugin

```python
from tools.registry import registry
result = registry.execute("get_time", {"timezone": "UTC"})
print(result)
```

## Notes
- Plugins are loaded at startup. Restart `holmium-backend` to reload.
- All paths should be absolute.
- Tools run as the `holmium` user.
- No permission checks — tools execute immediately.
