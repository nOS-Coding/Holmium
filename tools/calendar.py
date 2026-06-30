"""Calendar and reminder tools — Holmium's internal scheduling system."""

from datetime import datetime, timezone, timedelta
from typing import Optional

from tools.registry import register_tool
from memory.sqlite_store import SQLiteStore


def _store() -> SQLiteStore:
    return SQLiteStore()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@register_tool(
    "event_add",
    "Add a calendar event.",
    params_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Event title"},
            "start_time": {"type": "string", "description": "ISO 8601 start datetime"},
            "end_time": {"type": "string", "description": "ISO 8601 end datetime (optional)"},
            "description": {"type": "string", "description": "Event description"},
            "location": {"type": "string", "description": "Event location"},
            "all_day": {"type": "boolean", "description": "All-day event"},
            "recurrence": {"type": "string", "description": "Cron expression for recurrence"},
            "reminder_minutes": {"type": "integer", "description": "Minutes before event to remind"},
            "tag": {"type": "string", "description": "Event tag/category"},
        },
        "required": ["title", "start_time"],
    },
)
def event_add(
    title: str,
    start_time: str,
    end_time: Optional[str] = None,
    description: str = "",
    location: str = "",
    all_day: bool = False,
    recurrence: str = "",
    reminder_minutes: int = 15,
    tag: str = "",
) -> dict:
    db = _store()
    event_id = db.event_insert(
        title=title,
        start_time=start_time,
        end_time=end_time,
        description=description,
        location=location,
        all_day=all_day,
        recurrence=recurrence,
        reminder_minutes=reminder_minutes,
        tag=tag,
    )
    return {"success": True, "result": {"id": event_id, "title": title}, "error": None}


@register_tool(
    "event_get",
    "Get a calendar event by ID.",
    params_schema={
        "type": "object",
        "properties": {
            "event_id": {"type": "integer", "description": "Event ID"},
        },
        "required": ["event_id"],
    },
)
def event_get(event_id: int) -> dict:
    db = _store()
    event = db.event_get(event_id)
    if not event:
        return {"success": False, "result": None, "error": "Event not found"}
    return {"success": True, "result": event, "error": None}


@register_tool(
    "event_update",
    "Update a calendar event.",
    params_schema={
        "type": "object",
        "properties": {
            "event_id": {"type": "integer", "description": "Event ID"},
            "title": {"type": "string"},
            "start_time": {"type": "string"},
            "end_time": {"type": "string"},
            "description": {"type": "string"},
            "location": {"type": "string"},
            "all_day": {"type": "boolean"},
            "recurrence": {"type": "string"},
            "reminder_minutes": {"type": "integer"},
            "tag": {"type": "string"},
            "status": {"type": "string", "enum": ["confirmed", "cancelled", "tentative"]},
        },
        "required": ["event_id"],
    },
)
def event_update(event_id: int, **kwargs) -> dict:
    db = _store()
    updated = db.event_update(event_id, **kwargs)
    if not updated:
        return {"success": False, "result": None, "error": "Event not found or no changes"}
    return {"success": True, "result": {"id": event_id, "updated": True}, "error": None}


@register_tool(
    "event_delete",
    "Delete a calendar event.",
    params_schema={
        "type": "object",
        "properties": {
            "event_id": {"type": "integer", "description": "Event ID"},
        },
        "required": ["event_id"],
    },
)
def event_delete(event_id: int) -> dict:
    db = _store()
    deleted = db.event_delete(event_id)
    if not deleted:
        return {"success": False, "result": None, "error": "Event not found"}
    return {"success": True, "result": {"deleted": True}, "error": None}


@register_tool(
    "event_list",
    "List calendar events in a date range.",
    params_schema={
        "type": "object",
        "properties": {
            "start_date": {"type": "string", "description": "ISO date to start from"},
            "end_date": {"type": "string", "description": "ISO date to end at"},
        },
    },
)
def event_list(start_date: str = "", end_date: str = "") -> dict:
    db = _store()
    events = db.event_list(start_date, end_date)
    return {"success": True, "result": {"events": events, "count": len(events)}, "error": None}


@register_tool(
    "event_search",
    "Search calendar events by title, description, or tag.",
    params_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
        },
        "required": ["query"],
    },
)
def event_search(query: str) -> dict:
    db = _store()
    events = db.event_search(query)
    return {"success": True, "result": {"events": events, "count": len(events)}, "error": None}


@register_tool(
    "event_upcoming",
    "List upcoming confirmed events.",
    params_schema={
        "type": "object",
        "properties": {
            "n": {"type": "integer", "description": "Number of events (default 10)"},
        },
    },
)
def event_upcoming(n: int = 10) -> dict:
    db = _store()
    events = db.event_upcoming(n)
    return {"success": True, "result": {"events": events, "count": len(events)}, "error": None}
