from __future__ import annotations

from datetime import datetime, timezone

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tools.plugins import holmium_tool


@holmium_tool(
    name="get_time",
    description="Get the current date and time for a given timezone. Supports common timezone names like 'US/Eastern', 'Europe/London', 'Asia/Tokyo', etc.",
    params_schema={
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "Timezone name (e.g. 'US/Eastern', 'UTC', 'Asia/Tokyo')",
            },
        },
        "required": ["timezone"],
    },
)
def get_time(timezone: str) -> dict:
    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        return {"error": f"Unknown timezone: {timezone}", "datetime": None, "timezone": timezone}
    now = datetime.now(tz)
    return {
        "datetime": now.isoformat(),
        "timezone": timezone,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "weekday": now.strftime("%A"),
        "utc_offset": str(now.utcoffset()),
    }
