"""Briefing system — weather, todos, portfolio, email, notes, schedule → vLLM synthesis."""

import json
from typing import Any, Optional

import httpx

from ..memory.sqlite_store import SQLiteStore
from .config import HolmiumConfig
from .logger import get_logger

logger = get_logger("briefing")


async def generate_briefing() -> str:
    config = HolmiumConfig.load()
    sqlite_store = SQLiteStore()

    sections: list[str] = []

    weather = await _scrape_weather()
    if weather:
        sections.append(f"Weather: {weather}")

    overdue = sqlite_store.todos_list_overdue()
    if overdue:
        todos_text = "; ".join(f"{t['title']} (due: {t.get('due_date', 'unknown')})" for t in overdue[:5])
        sections.append(f"Overdue todos: {todos_text}")

    portfolio = _get_portfolio_summary(sqlite_store)
    if portfolio:
        sections.append(f"Portfolio: {portfolio}")

    emails = await _fetch_recent_emails()
    if emails:
        sections.append(f"Recent emails: {emails}")

    important_notes = _get_important_notes(sqlite_store)
    if important_notes:
        sections.append(f"Notes: {important_notes}")

    task_count = _get_upcoming_tasks(sqlite_store)
    if task_count > 0:
        sections.append(f"Scheduled tasks: {task_count} upcoming")

    if not sections:
        sections.append("No new information available.")

    raw_briefing = "\n".join(sections)
    logger.debug("Raw briefing data: %d chars", len(raw_briefing))

    synthesis = await _synthesize_briefing(raw_briefing, config)
    return synthesis or raw_briefing


async def _scrape_weather() -> Optional[str]:
    try:
        from ..search.scrapers.weather import get_weather
        result = get_weather()
        if result:
            return str(result)[:500]
        return None
    except ImportError:
        logger.debug("Weather scraper not available")
        return None
    except Exception as exc:
        logger.warning("Weather fetch failed: %s", exc)
        return None


def _get_portfolio_summary(store: SQLiteStore) -> Optional[str]:
    try:
        snapshots = store.portfolio_snapshot_list(n=50)
        if not snapshots:
            return None
        tickers: dict[str, list[float]] = {}
        for s in snapshots:
            t = s["ticker"]
            if t not in tickers:
                tickers[t] = []
            tickers[t].append(float(s["value"]))
        parts: list[str] = []
        for ticker, values in tickers.items():
            if values:
                latest = values[0]
                parts.append(f"{ticker}: ${latest:.2f}")
        return ", ".join(parts) if parts else None
    except Exception as exc:
        logger.warning("Portfolio summary failed: %s", exc)
        return None


async def _fetch_recent_emails() -> Optional[str]:
    try:
        from ..tools.email import list_emails
        emails = list_emails(max_results=5)
        if emails:
            lines = []
            for e in emails[:5]:
                lines.append(f"{e.get('from', '')}: {e.get('subject', '')}")
            return " | ".join(lines)
        return None
    except ImportError:
        logger.debug("Email tool not available")
        return None
    except Exception as exc:
        logger.warning("Email fetch failed: %s", exc)
        return None


def _get_important_notes(store: SQLiteStore) -> Optional[str]:
    try:
        notes = store.notes_list()
        if not notes:
            return None
        important = [n for n in notes if n.get("tags") and "important" in (n.get("tags", "") or "").lower()]
        if important:
            return "; ".join(n["title"][:100] for n in important[:3])
        return "; ".join(n["title"][:100] for n in notes[:3])
    except Exception as exc:
        logger.warning("Notes fetch failed: %s", exc)
        return None


def _get_upcoming_tasks(store: SQLiteStore) -> int:
    try:
        from .scheduler import TaskScheduler
        scheduler = TaskScheduler()
        return len(scheduler.list_tasks())
    except Exception:
        return 0


async def _synthesize_briefing(raw: str, config: HolmiumConfig) -> Optional[str]:
    prompt = (
        "You are Holmium, a helpful AI assistant. Summarize the following briefing information "
        "into a concise, friendly spoken briefing for the user. Keep it natural and conversational. "
        f"The user's name is {config.user_name or 'the user'}.\n\n"
        f"Briefing data:\n{raw}"
    )

    try:
        transport = httpx.AsyncHTTPTransport(uds=config.vllm_socket, retries=1)
        async with httpx.AsyncClient(transport=transport, timeout=60.0) as client:
            resp = await client.post(
                "http://localhost/v1/chat/completions",
                json={
                    "model": config.vllm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 512,
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except (httpx.HTTPError, httpx.TimeoutException, json.JSONDecodeError, KeyError) as exc:
        logger.warning("Briefing synthesis failed: %s", exc)
        return None
