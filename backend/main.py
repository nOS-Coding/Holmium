"""Holmium Backend — main FastAPI application entrypoint.

Ties together ALL Holmium backend modules:
config, auth, logger, sessions, modes, context, streaming,
status, backup, alerts, greeting, api_keys, usage_stats,
vision_doc_export, memory, tools, search, stt, tts, notifications.
"""

import asyncio
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, AsyncGenerator

import httpx
import uvicorn
from fastapi import FastAPI, Request, Depends, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, Response

# ── Backend modules ────────────────────────────────────────────────────────────
from backend.config import HolmiumConfig
from backend.auth import require_token
from backend.logger import get_logger
from backend.sessions import SessionManager
from backend.modes import ModeManager
from backend.context import ContextAssembler
from backend.streaming import StreamingPipeline
from backend.status import get_system_status
from backend.backup import run_backup
from backend.alerts import send_alert, get_alert_history
from backend.greeting import generate_greeting, play_greeting
from backend.api_keys import api_key_create, api_key_list, api_key_revoke
from backend.usage_stats import UsageStats
from backend.vision_doc_export import export_vision_doc, export_all_vision_docs
from backend.config_validator import validate_config
from backend.boot_diagnostics import BootDiagnostics
from backend.shutdown import ShutdownHandler
from backend.scheduler import TaskScheduler
from backend.scheduler_runner import SchedulerRunner
from backend.benchmark import run_benchmark, get_benchmark_history
from backend.updater import check_for_updates, perform_update
from backend.perf_monitor import PerfMonitor
from backend.resilience import ResilienceHandler
from backend.briefing import generate_briefing
from backend.image_upload import handle_file_upload

# ── Memory modules ─────────────────────────────────────────────────────────────
from memory.sqlite_store import SQLiteStore
from memory.vector_store import VectorStore
from memory.vision_docs import VisionDocStore
from memory.action_history import ActionHistory
from memory.fact_extractor import FactExtractor

# ── Tools modules ──────────────────────────────────────────────────────────────
from tools.registry import registry
from tools.executor import execute_tool, execute_with_logging
from tools.parser import find_tool_calls, has_tool_call, parse_tool_call, TOOL_CALL_MARKER
from tools.plugins import scan_plugins
import tools.calendar  # noqa: F401 — registers calendar tools via decorators
import tools.containers  # noqa: F401 — registers container tools via decorators
import tools.github  # noqa: F401 — registers GitHub tools via decorators
import tools.video  # noqa: F401 — registers video tools via decorators
import tools.debian_bridge  # noqa: F401 — registers debian bridge tools via decorators
import tools.git_local  # noqa: F401 — registers local git tools via decorators
import tools.nas  # noqa: F401 — registers NAS tools via decorators

# ── Search ─────────────────────────────────────────────────────────────────────
from search.search_tool import register_search_tools
from search.scrapers import register_all_scrapers

# ── STT / TTS ──────────────────────────────────────────────────────────────────
from stt.stt_service import stt_router
from tts.tts_service import tts_router

# ── Notifications (optional) ───────────────────────────────────────────────────
try:
    from notifications.ntfy_push import send_notification as ntfy_send
except ImportError:
    async def ntfy_send(title: str, message: str) -> None:
        pass

try:
    from notifications.mac_notify import send_mac_notification as mac_send
except ImportError:
    async def mac_send(title: str, message: str) -> None:
        pass

# ── Logger ─────────────────────────────────────────────────────────────────────
logger = get_logger("main")

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Holmium Backend",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Global state (initialised during startup) ──────────────────────────────────
config: HolmiumConfig
sqlite_store: SQLiteStore
vector_store: VectorStore
embeddings_model: Any = None
session_manager: SessionManager
mode_manager: ModeManager
context_assembler: ContextAssembler
streaming_pipeline: StreamingPipeline
scheduler: TaskScheduler
scheduler_runner: SchedulerRunner
shutdown_handler: ShutdownHandler
usage_stats: UsageStats
action_history: ActionHistory
vision_doc_store: VisionDocStore
perf_monitor: PerfMonitor
resilience_handler: ResilienceHandler
nas_server: Optional["NasServer"] = None
_connected_websockets: set[WebSocket] = set()
_notification_websockets: set[WebSocket] = set()


# ═══════════════════════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup():
    global config, sqlite_store, vector_store, embeddings_model
    global session_manager, mode_manager, context_assembler
    global streaming_pipeline, scheduler, scheduler_runner
    global shutdown_handler, usage_stats, action_history
    global vision_doc_store, perf_monitor, resilience_handler, nas_server

    logger.info("=== Holmium Backend starting up ===")

    # 1. Load config
    config = HolmiumConfig.load()
    logger.info("Config loaded for user: %s", config.user_name or "(not set)")

    # 2. Validate config
    if not validate_config(config):
        logger.error("Config validation failed — continuing with defaults where possible")

    # 3. Init logger (already done by backend.logger on import)

    # 4. Init SQLite store
    sqlite_store = SQLiteStore()
    logger.info("SQLite store initialised")

    # 5. Init LanceDB vector store
    vector_store = VectorStore()
    logger.info("LanceDB vector store initialised")

    # 6. Init embedding model (loaded by VectorStore internally)

    # 7. Init tool registry + register all tools
    register_search_tools(registry)
    register_all_scrapers(registry)
    _register_builtin_tools()
    logger.info("Tool registry populated (%d tools)", len(registry))

    # 8. Scan plugins
    plugin_names = scan_plugins()
    if plugin_names:
        logger.info("Plugins loaded: %s", ", ".join(plugin_names))

    # 9. Init session manager
    session_manager = SessionManager()
    logger.info("Session manager initialised")

    # 10. Init mode manager
    mode_manager = ModeManager()
    logger.info("Mode manager initialised (current: %s)", mode_manager.get_current_mode().name)

    # 11. Init scheduler
    scheduler = TaskScheduler()
    scheduler_runner = SchedulerRunner(scheduler)
    asyncio.create_task(scheduler_runner.run())
    logger.info("Scheduler + runner initialised")

    # Schedule weekly fine-tuning check (Sunday 9 AM)
    scheduler.add_task(
        task_description="Weekly fine-tuning check",
        tool_calls=[{"name": "check_fine_tuning", "params": {}}],
        schedule="0 9 * * 0",
        repeat=True,
    )
    logger.info("Weekly fine-tuning check scheduled")

    # Schedule first-boot fine-tuning if flag exists
    first_ft_flag = Path("/etc/holmium/first_boot_finetune")
    if first_ft_flag.exists():
        logger.info("First-boot fine-tuning flag detected — scheduling one-shot task")
        scheduler.add_task(
            task_description="First-boot fine-tuning",
            tool_calls=[{"name": "run_finetune", "params": {}}],
            schedule=datetime.now(timezone.utc).isoformat(),
            repeat=False,
        )
        first_ft_flag.unlink()
        logger.info("First-boot fine-tuning scheduled (will run within ~60s)")

    # 12. Init context assembler
    context_assembler = ContextAssembler(config, vector_store, sqlite_store)
    logger.info("Context assembler initialised")

    # 13. Init streaming pipeline
    streaming_pipeline = StreamingPipeline(config, context_assembler)
    logger.info("Streaming pipeline initialised")

    # 14. Register SIGTERM handler
    shutdown_handler = ShutdownHandler(vector_store, sqlite_store, config)
    shutdown_handler.install()
    logger.info("Shutdown handler installed")

    # 15. Run boot diagnostics
    diagnostics = BootDiagnostics(config)
    diag_results = await diagnostics.run_all()
    critical = diagnostics.critical_failures(diag_results)
    for r in diag_results:
        status_icon = "PASS" if r["status"] == "pass" else "FAIL" if r["status"] == "fail" else "WARN"
        logger.info("  [%s] %s — %s", status_icon, r["check"], r["detail"])
    if critical:
        logger.warning("%d critical check(s) failed — system may be degraded", len(critical))
    else:
        logger.info("All critical checks passed")

    # 16. Init remaining utilities
    usage_stats = UsageStats(sqlite_store)
    action_history = ActionHistory(sqlite_store)
    vision_doc_store = VisionDocStore(sqlite_store)
    perf_monitor = PerfMonitor()
    resilience_handler = ResilienceHandler(config)
    logger.info("Utility services initialised")

    # 17. Start NAS (WebDAV) server
    from backend.nas_server import NasServer
    nas_server = NasServer(config)
    if nas_server.enabled:
        asyncio.create_task(nas_server.start())
        logger.info("NAS server start initiated (WebDAV on port %d, path: %s)", nas_server.port, nas_server.nas_path)
    else:
        logger.info("NAS server is disabled in config")

    # 17. Generate + play greeting
    try:
        greeting = await generate_greeting()
        logger.info("Boot greeting: %s", greeting)
        asyncio.create_task(play_greeting())
    except Exception as exc:
        logger.warning("Greeting generation failed: %s", exc)

    logger.info("=== Holmium Backend startup complete ===")


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/chat")
async def chat(request: Request, token=Depends(require_token)):
    body = await request.json()
    message = body.get("message", "").strip()
    session_id = body.get("session_id", "")
    mode_name = body.get("mode", "")

    if not message:
        return JSONResponse({"error": "Missing 'message' field"}, status_code=400)

    if mode_name:
        mode_manager.set_mode(mode_name)

    session = session_manager.get_session(session_id) if session_id else None
    if session is None:
        session = session_manager.create_session("api")

    session_manager.add_message(session.session_id, "user", message)
    usage_stats.record_message()

    asyncio.create_task(
        FactExtractor(store=sqlite_store).extract_facts(
            {"role": "user", "content": message}
        )
    )

    current_mode = mode_manager.get_current_mode().name if not mode_name else mode_name
    return StreamingResponse(
        streaming_pipeline.stream_chat(message, session, mode=current_mode),
        media_type="text/event-stream",
        headers={
            "X-Session-Id": session.session_id,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    _connected_websockets.add(websocket)
    session = session_manager.create_session("websocket")
    usage_stats.record_session()

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            message = payload.get("message", "").strip()
            mode_name = payload.get("mode", "")

            if not message:
                continue

            if mode_name:
                mode_manager.set_mode(mode_name)

            session_manager.add_message(session.session_id, "user", message)
            usage_stats.record_message()

            current_mode = mode_manager.get_current_mode().name if not mode_name else mode_name
            async for event in streaming_pipeline.stream_chat(message, session, mode=current_mode):
                await websocket.send_text(event)

            await websocket.send_text("data: [DONE]\n\n")
    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected: %s", session.session_id[:8])
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
    finally:
        _connected_websockets.discard(websocket)
        session_manager.close_session(session.session_id)


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTERS
# ═══════════════════════════════════════════════════════════════════════════════

app.include_router(stt_router, dependencies=[Depends(require_token)])
app.include_router(tts_router, dependencies=[Depends(require_token)])


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/status")
async def status(token=Depends(require_token)):
    try:
        status_data = await get_system_status()
        status_data["mode"] = mode_manager.get_current_mode().name
        status_data["sessions_active"] = len(session_manager._sessions) if hasattr(session_manager, "_sessions") else 0
        status_data["tools_count"] = len(registry)
        status_data["uptime_daemon"] = time.monotonic()
        return status_data
    except Exception as exc:
        logger.exception("Status endpoint failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


# ═══════════════════════════════════════════════════════════════════════════════
# LOGS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/logs")
async def stream_logs(token=Depends(require_token)):
    log_file = Path("/var/log/holmium/holmium.log")

    async def _tail_log() -> AsyncGenerator[str, None]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "tail", "-f", "-n", "100", str(log_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            assert proc.stdout is not None
            try:
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    yield f"data: {line.decode('utf-8', errors='replace').rstrip()}\n\n"
            except asyncio.CancelledError:
                proc.terminate()
                await proc.wait()
        except FileNotFoundError:
            yield "data: Log file not found\n\n"
        except Exception as exc:
            yield f"data: Error: {exc}\n\n"

    return StreamingResponse(_tail_log(), media_type="text/event-stream")


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/memory/add")
async def memory_add(request: Request, token=Depends(require_token)):
    body = await request.json()
    key = body.get("key", "").strip()
    value = body.get("value", "").strip()
    if not key or not value:
        return JSONResponse({"error": "Missing 'key' or 'value'"}, status_code=400)
    sqlite_store.fact_set(key, value)
    logger.info("Memory fact set: %s", key)
    return {"status": "ok", "key": key}


@app.get("/memory/list")
async def memory_list(token=Depends(require_token)):
    facts = sqlite_store.fact_list()
    return {"facts": facts}


@app.delete("/memory/forget/{key}")
async def memory_forget(key: str, token=Depends(require_token)):
    deleted = sqlite_store.fact_delete(key)
    if not deleted:
        return JSONResponse({"error": "Fact not found"}, status_code=404)
    logger.info("Memory fact deleted: %s", key)
    return {"status": "deleted", "key": key}


@app.get("/memory/search")
async def memory_search(request: Request, token=Depends(require_token)):
    query = request.query_params.get("q", "").strip()
    if not query:
        return JSONResponse({"error": "Missing 'q' query parameter"}, status_code=400)
    facts = sqlite_store.fact_search(query)
    return {"query": query, "facts": facts}


# ═══════════════════════════════════════════════════════════════════════════════
# SESSIONS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/sessions/list")
async def sessions_list(token=Depends(require_token)):
    sessions = session_manager.session_list(n=50)
    return {"sessions": sessions}


@app.get("/sessions/{session_id}")
async def session_get(session_id: str, token=Depends(require_token)):
    session = session_manager.session_get(session_id)
    if session is None:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    return {"session": session}


# ═══════════════════════════════════════════════════════════════════════════════
# FILE UPLOAD / DOWNLOAD
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/upload/file")
async def upload_file(file: UploadFile = File(...), token=Depends(require_token)):
    content = await file.read()
    result = await handle_file_upload(file.filename or "upload", content, file.content_type)
    return result


@app.get("/files/download")
async def download_file(request: Request, token=Depends(require_token)):
    filepath = request.query_params.get("path", "").strip()
    if not filepath:
        return JSONResponse({"error": "Missing 'path' query parameter"}, status_code=400)
    path = Path(filepath)
    if not path.exists() or not path.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)
    try:
        content = path.read_bytes()
        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
        )
    except OSError as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ═══════════════════════════════════════════════════════════════════════════════
# BACKUP
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/backup")
async def backup(token=Depends(require_token)):
    result = await run_backup()
    if result.startswith("Error"):
        return JSONResponse({"error": result}, status_code=500)
    return {"status": "ok", "path": result}


# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFY
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/notify")
async def notify(request: Request, token=Depends(require_token)):
    body = await request.json()
    title = body.get("title", "Holmium Notification")
    message = body.get("message", "").strip()
    if not message:
        return JSONResponse({"error": "Missing 'message'"}, status_code=400)
    await send_alert(title, message)
    await ntfy_send(title=title, message=message)
    await mac_send(title=title, message=message)
    return {"status": "sent", "title": title}


@app.post("/notify/android/clipboard")
async def notify_android_clipboard(request: Request, token=Depends(require_token)):
    body = await request.json()
    text = body.get("text", "").strip()
    if not text:
        return JSONResponse({"error": "Missing 'text'"}, status_code=400)
    sent = ntfy_send(
        title="Holmium Clipboard",
        message=f"Tap to copy: {text[:100]}",
        click_action="copy",
        copy_text=text,
    )
    return {"status": "sent" if sent else "failed"}


# ═══════════════════════════════════════════════════════════════════════════════
# API KEYS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/keys/create")
async def keys_create(request: Request, token=Depends(require_token)):
    body = await request.json()
    label = body.get("label", "").strip()
    if not label:
        return JSONResponse({"error": "Missing 'label'"}, status_code=400)
    raw_key = api_key_create(label)
    if raw_key is None:
        return JSONResponse({"error": "Failed to create API key"}, status_code=500)
    return {"status": "created", "label": label, "key": raw_key}


@app.get("/keys/list")
async def keys_list(token=Depends(require_token)):
    keys = api_key_list()
    return {"keys": keys}


@app.delete("/keys/{label}")
async def keys_revoke(label: str, token=Depends(require_token)):
    success = api_key_revoke(label)
    if not success:
        return JSONResponse({"error": "Key not found or could not be revoked"}, status_code=404)
    return {"status": "revoked", "label": label}


# ═══════════════════════════════════════════════════════════════════════════════
# BENCHMARK
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/benchmark")
async def benchmark(request: Request, token=Depends(require_token)):
    body = await request.json()
    quick = body.get("quick", False)
    results = await run_benchmark(quick=bool(quick))
    return results


@app.get("/benchmark/history")
async def benchmark_history(token=Depends(require_token)):
    history = await get_benchmark_history()
    return {"history": history}


# ═══════════════════════════════════════════════════════════════════════════════
# STATS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/stats")
async def stats(token=Depends(require_token)):
    report = usage_stats.weekly_report()
    perf_report = perf_monitor.get_report()
    return {
        "usage": report,
        "performance": perf_report,
        "tools_available": len(registry),
        "sessions_active": len(session_manager._sessions) if hasattr(session_manager, "_sessions") else 0,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/tools/list")
async def tools_list(token=Depends(require_token)):
    return {"tools": registry.list_tools()}


@app.post("/tools/execute")
async def tools_execute(request: Request, token=Depends(require_token)):
    body = await request.json()
    name = body.get("name", "").strip()
    params = body.get("params", {})
    session_id = body.get("session_id", "")
    if not name:
        return JSONResponse({"error": "Missing 'name'"}, status_code=400)
    result = execute_with_logging(name, params, session_id) if session_id else execute_tool(name, params)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# ALERTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/alerts/history")
async def alerts_history(token=Depends(require_token)):
    history = get_alert_history(n=100)
    return {"alerts": history}


# ═══════════════════════════════════════════════════════════════════════════════
# VISION DOCS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/vision_docs/{slug}")
async def vision_docs_get(slug: str, token=Depends(require_token)):
    content = export_vision_doc(slug)
    if content is None:
        return JSONResponse({"error": "Vision doc not found"}, status_code=404)
    return {"slug": slug, "content": content}


@app.get("/vision_docs")
async def vision_docs_list(token=Depends(require_token)):
    docs = vision_doc_store.list_vision_docs()
    return {"docs": docs}


@app.post("/vision_docs")
async def vision_docs_create(request: Request, token=Depends(require_token)):
    body = await request.json()
    title = body.get("title", "").strip()
    content = body.get("content", "").strip()
    if not title or not content:
        return JSONResponse({"error": "Missing 'title' or 'content'"}, status_code=400)
    slug = vision_doc_store.create_vision_doc(title, content)
    return {"status": "created", "slug": slug}


@app.delete("/vision_docs/{slug}")
async def vision_docs_delete(slug: str, token=Depends(require_token)):
    deleted = vision_doc_store.delete_vision_doc(slug)
    if not deleted:
        return JSONResponse({"error": "Vision doc not found"}, status_code=404)
    return {"status": "deleted", "slug": slug}


@app.get("/vision_docs/export/all")
async def vision_docs_export_all(token=Depends(require_token)):
    zip_bytes = export_all_vision_docs()
    if zip_bytes is None:
        return JSONResponse({"error": "No vision docs to export"}, status_code=404)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="vision_docs.zip"'},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DEVICE REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/register_device")
async def register_device(request: Request, token=Depends(require_token)):
    body = await request.json()
    device_name = body.get("device_name", "").strip()
    device_type = body.get("device_type", "").strip()
    public_key = body.get("public_key", "").strip()
    if not device_name or not device_type:
        return JSONResponse({"error": "Missing 'device_name' or 'device_type'"}, status_code=400)
    device_id = f"dev_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{os.urandom(4).hex()}"
    registration = {
        "device_id": device_id,
        "device_name": device_name,
        "device_type": device_type,
        "public_key": public_key,
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }
    sqlite_store.fact_set(f"device_{device_id}", json.dumps(registration))
    logger.info("Device registered: %s (%s)", device_name, device_type)
    return {"status": "registered", "device_id": device_id}


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULER ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/scheduler/list")
async def scheduler_list(token=Depends(require_token)):
    tasks = scheduler.list_tasks()
    return {"tasks": tasks}


@app.post("/scheduler/add")
async def scheduler_add(request: Request, token=Depends(require_token)):
    body = await request.json()
    description = body.get("description", "").strip()
    tool_calls = body.get("tool_calls", [])
    schedule = body.get("schedule", "").strip()
    repeat = body.get("repeat", False)
    if not description or not schedule:
        return JSONResponse({"error": "Missing 'description' or 'schedule'"}, status_code=400)
    task_id = scheduler.add_task(description, tool_calls, schedule, repeat=bool(repeat))
    return {"status": "created", "task_id": task_id}


@app.delete("/scheduler/cancel/{task_id}")
async def scheduler_cancel(task_id: str, token=Depends(require_token)):
    cancelled = scheduler.cancel_task(task_id)
    if not cancelled:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    return {"status": "cancelled", "task_id": task_id}


# ═══════════════════════════════════════════════════════════════════════════════
# UPDATE
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/update/check")
async def update_check(token=Depends(require_token)):
    result = await check_for_updates()
    return result


@app.post("/update")
async def update(token=Depends(require_token)):
    result = await perform_update()
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# BRIEFING
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/briefing")
async def briefing(token=Depends(require_token)):
    text = await generate_briefing()
    return {"briefing": text}


# ═══════════════════════════════════════════════════════════════════════════════
# MODE
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/mode")
async def mode_get(token=Depends(require_token)):
    current = mode_manager.get_current_mode()
    return {
        "mode": current.name,
        "temperature": current.temperature,
        "top_p": current.top_p,
        "enable_thinking": current.enable_thinking,
    }


@app.post("/mode")
async def mode_set(request: Request, token=Depends(require_token)):
    body = await request.json()
    mode_name = body.get("mode", "").strip().lower()
    if mode_name not in ("think", "work", "image"):
        return JSONResponse(
            {"error": f"Invalid mode '{mode_name}'. Choose from: think, work, image"},
            status_code=400,
        )
    mc = mode_manager.set_mode(mode_name)
    return {
        "status": "ok",
        "mode": mc.name,
        "temperature": mc.temperature,
        "top_p": mc.top_p,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS WEBSOCKET (for Mac daemon)
# ═══════════════════════════════════════════════════════════════════════════════

@app.websocket("/notifications/ws")
async def notification_ws(websocket: WebSocket):
    await websocket.accept()
    _notification_websockets.add(websocket)
    logger.debug("Notification WebSocket connected")
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            action = payload.get("action", "")
            if action == "ping":
                await websocket.send_text(json.dumps({"action": "pong"}))
            elif action == "notify":
                title = payload.get("title", "Holmium")
                message = payload.get("message", "")
                await send_alert(title, message)
                await websocket.send_text(json.dumps({"action": "notified", "title": title}))
    except WebSocketDisconnect:
        logger.debug("Notification WebSocket disconnected")
    except Exception as exc:
        logger.error("Notification WS error: %s", exc)
    finally:
        _notification_websockets.discard(websocket)


# ═══════════════════════════════════════════════════════════════════════════════
# ACTIONS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/actions/recent")
async def actions_recent(token=Depends(require_token)):
    actions = action_history.get_recent_actions(n=100)
    return {"actions": actions}


@app.get("/actions/search")
async def actions_search(request: Request, token=Depends(require_token)):
    query = request.query_params.get("q", "").strip()
    if not query:
        return JSONResponse({"error": "Missing 'q' query parameter"}, status_code=400)
    actions = action_history.search_actions(query)
    return {"query": query, "actions": actions}


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH / PING
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/ping")
async def ping():
    return {"status": "pong", "version": "1.0.0", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/health")
async def health():
    try:
        sqlite_store.fact_list()
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "ok" if db_ok else "unreachable",
        "tools": len(registry),
        "sessions": len(session_manager._sessions) if hasattr(session_manager, "_sessions") else 0,
    }


async def _run_finetune_background() -> None:
    """Run the full fine-tuning pipeline in background (finetune.sh → merge.sh)."""
    logger.info("=== First-boot fine-tuning started ===")
    training_dir = "/opt/holmium/training"

    # Step 1: finetune.sh
    logger.info("Running finetune.sh (this will take hours)...")
    proc = await asyncio.create_subprocess_exec(
        "bash", f"{training_dir}/finetune.sh",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    log_output = stdout.decode(errors="replace") if stdout else ""

    if proc.returncode != 0:
        logger.error("Fine-tuning failed with code %d", proc.returncode)
        await send_alert("Fine-Tuning Failed", f"Return code: {proc.returncode}\n{log_output[-500:]}")
        return

    # Step 2: merge.sh
    logger.info("Finetune.sh complete. Running merge.sh...")
    proc = await asyncio.create_subprocess_exec(
        "bash", f"{training_dir}/merge.sh",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    log_output = stdout.decode(errors="replace") if stdout else ""

    if proc.returncode != 0:
        logger.error("Model merge failed with code %d", proc.returncode)
        await send_alert("Model Merge Failed", f"Return code: {proc.returncode}\n{log_output[-500:]}")
        return

    sqlite_store.fact_set("last_finetune_date", datetime.now(timezone.utc).isoformat())
    logger.info("=== First-boot fine-tuning complete ===")
    await send_alert("Fine-Tuning Complete", "Holmium has been fine-tuned and the model merged successfully.")


def _run_finetune_handler(**kwargs) -> dict:
    """Synchronous handler that launches fine-tuning as a background asyncio task."""
    loop = asyncio.get_running_loop()
    loop.create_task(_run_finetune_background())
    return {"message": "Fine-tuning pipeline launched in background — this will take hours"}


async def _check_fine_tuning() -> dict:
    """Check if fine-tuning is due and notify the user."""
    vd = VisionDocStore(sqlite_store)
    docs = vd.list_vision_docs()
    session_docs = [d for d in docs if d.get("title", "").startswith("Session ")]
    last_finetune = sqlite_store.fact_get("last_finetune_date")
    msg_lines = []
    if session_docs:
        msg_lines.append(f"Found {len(session_docs)} session documents since last shutdown.")
    else:
        msg_lines.append("No new session data found since last check.")
    if last_finetune:
        msg_lines.append(f"Last fine-tune: {last_finetune}")
    else:
        msg_lines.append("No previous fine-tune recorded.")
    msg_lines.append("Reply 'run fine-tuning' to start if you'd like.")
    await send_alert("Weekly Fine-Tuning Check", " | ".join(msg_lines))
    return {"success": True, "result": {"message": " | ".join(msg_lines), "session_docs": len(session_docs)}, "error": None}


# ═══════════════════════════════════════════════════════════════════════════════
# BUILT-IN TOOL REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════════

def _register_builtin_tools():
    registry.register(
        name="get_time",
        description="Get the current date and time in the configured timezone.",
        params_schema={"type": "object", "properties": {}, "required": []},
        handler=lambda: datetime.now(timezone.utc).isoformat(),
    )

    registry.register(
        name="get_system_status",
        description="Get current system status including CPU, memory, GPU, and vLLM health.",
        params_schema={"type": "object", "properties": {}, "required": []},
        handler=lambda _config=config: asyncio.run(get_system_status()),
    )

    registry.register(
        name="search_memory",
        description="Search stored facts in the SQLite knowledge base.",
        params_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
        handler=lambda query: sqlite_store.fact_search(query),
    )

    registry.register(
        name="set_fact",
        description="Store a fact in the knowledge base.",
        params_schema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Fact key"},
                "value": {"type": "string", "description": "Fact value"},
            },
            "required": ["key", "value"],
        },
        handler=lambda key, value: sqlite_store.fact_set(key, value) or {"status": "stored", "key": key},
    )

    registry.register(
        name="list_facts",
        description="List all stored facts.",
        params_schema={"type": "object", "properties": {}, "required": []},
        handler=lambda: sqlite_store.fact_list(),
    )

    registry.register(
        name="get_mode",
        description="Get the current conversation mode (think/work/image).",
        params_schema={"type": "object", "properties": {}, "required": []},
        handler=lambda: mode_manager.get_current_mode().name,
    )

    registry.register(
        name="set_mode",
        description="Set the conversation mode.",
        params_schema={
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["think", "work", "image"],
                    "description": "Mode name",
                },
            },
            "required": ["mode"],
        },
        handler=lambda mode: mode_manager.set_mode(mode).name,
    )

    registry.register(
        name="generate_briefing",
        description="Generate a daily briefing with weather, todos, portfolio, and notes.",
        params_schema={"type": "object", "properties": {}, "required": []},
        handler=lambda: asyncio.run(generate_briefing()),
    )

    registry.register(
        name="send_notification",
        description="Send a notification to all connected clients (ntfy, macOS).",
        params_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Notification title"},
                "message": {"type": "string", "description": "Notification body"},
            },
            "required": ["title", "message"],
        },
        handler=lambda title, message: asyncio.run(send_alert(title, message)),
    )

    registry.register(
        "check_fine_tuning",
        "Check if fine-tuning is due and prompt the user.",
        {"type": "object", "properties": {}, "required": []},
        handler=lambda: asyncio.run(_check_fine_tuning()),
    )

    registry.register(
        "run_finetune",
        "Run the full fine-tuning pipeline (finetune.sh + merge.sh, takes hours).",
        {"type": "object", "properties": {}, "required": []},
        handler=_run_finetune_handler,
    )

    logger.debug("Built-in tools registered")


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8765,
        ssl_keyfile="/etc/holmium/tls/holmium.key",
        ssl_certfile="/etc/holmium/tls/holmium.crt",
        uds="/run/holmium/backend.sock",
        log_level="info",
        reload=False,
    )
