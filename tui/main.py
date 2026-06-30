from __future__ import annotations

import asyncio
import json
import os
import platform
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator

from rich.text import Text
from rich.style import Style

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Static, Input, RichLog
from textual.widget import Widget
from textual.worker import Worker
from textual.css.query import NoMatches

from tui.logo import LOGO, LOGO_SMALL

BACKEND_SOCKET = "/run/holmium/backend.sock"
CONFIG_PATH = Path("/etc/holmium/config.json")
MODE_PATH = Path("/var/holmium/mode.json")

COLOR_BG = "#000000"
COLOR_SURFACE = "#0a0a0a"
COLOR_BORDER = "#1a1a2e"
COLOR_CYAN = "#00BCD4"
COLOR_PINK = "#FF69B4"
COLOR_TEXT = "#E0E0E0"
COLOR_DIM = "#666666"
COLOR_SUBTLE = "#444444"
COLOR_ERROR = "#FF4444"
COLOR_GREEN = "#4CAF50"

MODE_COLORS = {
    "think": COLOR_CYAN,
    "work": COLOR_PINK,
    "image": COLOR_PINK,
    "help": COLOR_GREEN,
}

MODE_LABELS = {
    "think": "THINK",
    "work": "WORK",
    "image": "IMAGE",
    "help": "HELP",
}

MODES = ["work", "think", "image", "help"]


def load_config() -> dict[str, Any]:
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"user_name": "user", "timezone": "UTC"}


def load_mode() -> str:
    try:
        data = json.loads(MODE_PATH.read_text())
        return data.get("mode", "work")
    except (FileNotFoundError, json.JSONDecodeError):
        return "work"


def save_mode(mode: str) -> None:
    MODE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODE_PATH.write_text(json.dumps({"mode": mode}))


async def http_unix(method: str, path: str, body: bytes | None = None) -> dict | None:
    try:
        reader, writer = await asyncio.open_unix_connection(BACKEND_SOCKET)
    except (FileNotFoundError, OSError):
        return None
    try:
        req = f"{method} {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n"
        if body is not None:
            req += f"Content-Length: {len(body)}\r\nContent-Type: application/json\r\n"
        req += "\r\n"
        payload = req.encode()
        if body is not None:
            payload += body
        writer.write(payload)
        await writer.drain()
        raw = b""
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            raw += chunk
    finally:
        writer.close()
        await writer.wait_closed()
    if not raw:
        return None
    idx = raw.find(b"\r\n\r\n")
    if idx == -1:
        return None
    body_bytes = raw[idx + 4:]
    if not body_bytes:
        return None
    try:
        return json.loads(body_bytes.decode("utf-8"))
    except json.JSONDecodeError:
        return {"raw": body_bytes.decode("utf-8", errors="replace")}


async def chat_stream_tokens(message: str, mode: str) -> AsyncGenerator[str, None]:
    body = json.dumps({"message": message, "mode": mode}).encode()
    try:
        reader, writer = await asyncio.open_unix_connection(BACKEND_SOCKET)
    except (FileNotFoundError, OSError):
        yield "__BACKEND_UNAVAILABLE__"
        return
    try:
        req = (
            f"POST /chat HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Content-Type: application/json\r\n"
            f"Accept: text/event-stream\r\n"
            f"Connection: close\r\n\r\n"
        )
        writer.write(req.encode() + body)
        await writer.drain()
        header = b""
        while True:
            c = await reader.read(1)
            if not c:
                break
            header += c
            if header.endswith(b"\r\n\r\n"):
                break
        buf = b""
        while True:
            chunk = await reader.read(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line_bytes, buf = buf.split(b"\n", 1)
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        return
                    try:
                        ev = json.loads(data)
                        if "content" in ev:
                            yield ev["content"]
                        elif "error" in ev:
                            yield f"[ERROR] {ev['error']}"
                    except json.JSONDecodeError:
                        if data:
                            yield data
    finally:
        writer.close()
        await writer.wait_closed()


# ── Widgets ──────────────────────────────────────────────────────────

class HelpPopup(Screen):
    CSS = """
    Screen {
        background: rgba(0, 0, 0, 0.75);
    }
    #help-box {
        background: #0a0a0a;
        border: solid #1a1a2e;
        margin: 4 10;
        padding: 1 2;
        height: auto;
    }
    #help-title {
        text-style: bold;
        color: #00BCD4;
        padding-bottom: 1;
    }
    #help-content {
        color: #E0E0E0;
    }
    #help-close {
        color: #666666;
        padding-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Static("Holmium OS Help", id="help-title")
            yield Static("", id="help-content")
            yield Static("[dim]Press any key to close[/]", id="help-close")

    def on_mount(self) -> None:
        cmds = (
            "[bold cyan]Commands[/]\n"
            f"  [#00BCD4]:help[/]      Show this help\n"
            f"  [#00BCD4]:clear[/]     Clear conversation\n"
            f"  [#00BCD4]:memory[/]    Show memory facts\n"
            f"  [#00BCD4]:notes[/]     Show notes list\n"
            f"  [#00BCD4]:todo[/]      Show todo list\n"
            f"  [#00BCD4]:mode[/]      Switch mode (think/work/image/help)\n"
            f"  [#00BCD4]:web on/off[/] Toggle web search\n"
            f"\n"
            f"[bold]Key Bindings[/]\n"
            f"  [#666666]Tab[/]         Cycle mode\n"
            f"  [#666666]Ctrl+C[/]      Cancel current response\n"
            f"  [#666666]Ctrl+S[/]      Toggle sidebar\n"
            f"  [#666666]Ctrl+L[/]      Clear conversation\n"
        )
        self.query_one("#help-content", Static).update(cmds)

    def on_key(self, event) -> None:
        self.app.pop_screen()


class HeaderBar(Widget):
    current_mode = reactive("work")
    conn_status = reactive("connecting")
    user_name = "user"

    def compose(self) -> ComposeResult:
        yield Static(LOGO, id="header-logo")
        with Vertical(id="header-meta"):
            with Horizontal(id="header-top-row"):
                yield Static("", id="mode-badge")
                yield Static("", id="conn-dot")
            yield Static("", id="user-host")
            yield Static("", id="conn-detail")

    def watch_current_mode(self, mode: str) -> None:
        color = MODE_COLORS.get(mode, COLOR_TEXT)
        label = MODE_LABELS.get(mode, mode.upper())
        try:
            self.query_one("#mode-badge", Static).update(f"[{color} bold][{label}][/]")
        except NoMatches:
            pass

    def watch_conn_status(self, status: str) -> None:
        dot_map = {"connected": ("●", COLOR_GREEN), "error": ("●", COLOR_ERROR),
                    "connecting": ("○", "yellow")}
        dot, color = dot_map.get(status, ("○", COLOR_DIM))
        try:
            self.query_one("#conn-dot", Static).update(f"[{color}]{dot} {status.upper()}[/]")
        except NoMatches:
            pass

    def set_user(self, name: str) -> None:
        try:
            self.query_one("#user-host", Static).update(
                f"[{COLOR_DIM}]{name}[/][#666666]@[/][{COLOR_CYAN}]holmium[/]"
            )
        except NoMatches:
            pass

    def set_conn_detail(self, text: str) -> None:
        try:
            self.query_one("#conn-detail", Static).update(f"[{COLOR_DIM}]{text}[/]")
        except NoMatches:
            pass


class StatsSidebar(Widget):
    stats = reactive({})

    def compose(self) -> ComposeResult:
        with Vertical(id="stats-inner"):
            yield Static("[#666666]┌─ SYS ─────────────┐[/]", id="stats-title")
            yield Static("", id="stats-content")

    def watch_stats(self, s: dict[str, Any]) -> None:
        cpu = s.get("cpu_percent", "?")
        ram = s.get("ram_percent", "?")
        gpu = f"{s.get('gpu_util', '?')}% / {s.get('gpu_temp', '?')}°C"
        vram_used = s.get("vram_used_gb", "?")
        vram_total = s.get("vram_total_gb", 16)
        vram = f"{vram_used}G / {vram_total}G"
        vllm = s.get("vllm_status", "?")
        wg = s.get("wg_handshake", "?")
        uptime = s.get("uptime", "?")
        disk = s.get("disk_percent", "?")

        cpu_bar = self._bar(cpu)
        ram_bar = self._bar(ram)
        disk_bar = self._bar(disk)
        vllm_color = COLOR_GREEN if vllm == "ok" else (COLOR_ERROR if vllm == "down" else "yellow")
        wg_color = COLOR_GREEN if wg not in ("down", "?", "") else COLOR_DIM

        text = (
            f"[{COLOR_DIM}] CPU  [/]{cpu_bar} [white]{cpu}%[/]\n"
            f"[{COLOR_DIM}] RAM  [/]{ram_bar} [white]{ram}%[/]\n"
            f"[{COLOR_DIM}] GPU  [/][white]{gpu}[/]\n"
            f"[{COLOR_DIM}] VRAM [/][white]{vram}[/]\n"
            f"[{COLOR_DIM}] DISK [/]{disk_bar} [white]{disk}%[/]\n"
            f"[{COLOR_DIM}] vLLM [/][{vllm_color}]{vllm}[/]\n"
            f"[{COLOR_DIM}] WG   [/][{wg_color}]{wg}[/]\n"
            f"[{COLOR_DIM}] UP   [/][white]{uptime}[/]"
        )
        try:
            self.query_one("#stats-content", Static).update(text)
        except NoMatches:
            pass

    def _bar(self, pct: Any, width: int = 8) -> str:
        try:
            p = float(pct)
        except (ValueError, TypeError):
            return f"[{COLOR_DIM}]░░░░░░░░[/]"
        filled = max(0, min(width, int(p / 100 * width)))
        bar = "█" * filled + "░" * (width - filled)
        color = COLOR_CYAN if p < 70 else (COLOR_PINK if p < 90 else COLOR_ERROR)
        return f"[{color}]{bar}[/]"


class ChatPanel(RichLog):
    def add_user(self, text: str) -> None:
        ts = datetime.now().strftime("%H:%M")
        styled = Text()
        styled.append(f" [{COLOR_SUBTLE}]{ts}[/]", style=Style(color=COLOR_SUBTLE))
        styled.append(f" [#00BCD4]you >[/]", style=Style(color=COLOR_CYAN))
        styled.append(f" {text}", style=Style(color=COLOR_CYAN))
        self.write(styled)

    def add_holmium(self, text: str) -> None:
        ts = datetime.now().strftime("%H:%M")
        styled = Text()
        styled.append(f" [{COLOR_SUBTLE}]{ts}[/]", style=Style(color=COLOR_SUBTLE))
        styled.append(f" [white]holmium >[/]", style=Style(color="white"))
        styled.append(f" {text}", style=Style(color="white"))
        self.write(styled)

    def add_system(self, text: str) -> None:
        self.write(Text(text, style=Style(color=COLOR_DIM, italic=True)))

    def add_error(self, text: str) -> None:
        self.write(Text(text, style=Style(color=COLOR_ERROR, bold=True)))


class HolmiumInput(Widget):
    def compose(self) -> ComposeResult:
        with Horizontal(id="input-row"):
            yield Static(">>> ", id="input-prefix")
            yield Input(placeholder="Ask Holmium anything...", id="chat-input")


class StatusBar(Widget):
    current_mode = reactive("work")
    token_count = reactive(0)

    def compose(self) -> ComposeResult:
        yield Static("", id="status-mode")
        yield Static(
            "[#666666]Tab:mode  Ctrl+C:stop  Ctrl+S:sidebar  Ctrl+L:clear[/]",
            id="status-hints"
        )
        yield Static("", id="status-tokens")

    def watch_current_mode(self, mode: str) -> None:
        color = MODE_COLORS.get(mode, COLOR_TEXT)
        label = MODE_LABELS.get(mode, mode.upper())
        try:
            self.query_one("#status-mode", Static).update(
                f"[{color} bold][{label}][/]"
            )
        except NoMatches:
            pass

    def watch_token_count(self, count: int) -> None:
        try:
            self.query_one("#status-tokens", Static).update(
                f"[{COLOR_DIM}]tk: {count}[/]"
            )
        except NoMatches:
            pass


# ── CSS ──────────────────────────────────────────────────────────────

HOLMIUM_CSS = """
$bg: #000000;
$surface: #0a0a0a;
$border: #1a1a2e;
$cyan: #00BCD4;
$pink: #FF69B4;
$text: #E0E0E0;
$dim: #666666;
$subtle: #444444;

Screen {
    background: $bg;
}

#header-bar {
    background: $surface;
    height: auto;
    layout: horizontal;
    border-bottom: solid $border;
}

#header-logo {
    width: 42;
    padding: 0 1;
    min-height: 11;
}

#header-meta {
    width: 1fr;
    align: right middle;
    padding: 0 1;
}

#header-top-row {
    height: auto;
    layout: horizontal;
}

#mode-badge {
    text-style: bold;
    margin-right: 1;
}

#conn-dot {
    color: $dim;
    margin-left: 1;
}

#user-host {
    color: $dim;
    text-style: bold;
}

#conn-detail {
    color: $dim;
}

#body-row {
    height: 1fr;
    layout: horizontal;
}

#stats-sidebar {
    background: $surface;
    width: 24;
    padding: 0 1;
    border-right: solid $border;
    overflow-y: auto;
}

#stats-inner {
    height: auto;
}

#stats-title {
    color: $dim;
    padding-bottom: 1;
}

#stats-content {
    color: $dim;
}

#main-panel {
    background: $bg;
    height: 1fr;
}

#conversation {
    height: 1fr;
    padding: 0 1;
    overflow-y: auto;
}

#stream-buffer {
    background: $surface;
    color: white;
    padding: 0 2;
    height: auto;
    max-height: 4;
    border-top: solid $border;
    display: none;
}

#input-row {
    height: 3;
    background: $surface;
    border-top: solid $border;
    layout: horizontal;
}

#input-prefix {
    color: #FF69B4;
    width: 5;
    content-align: center middle;
    text-style: bold;
}

#chat-input {
    background: transparent;
    color: $text;
    border: none;
    padding: 0 1;
    height: 3;
}

#chat-input:focus {
    background: #111111;
}

#chat-input .input--placeholder {
    color: $subtle;
}

#status-bar {
    background: $surface;
    height: 1;
    layout: horizontal;
    border-top: solid $border;
}

#status-mode {
    width: auto;
    padding: 0 1;
}

#status-hints {
    width: 1fr;
    color: $dim;
    text-align: center;
}

#status-tokens {
    width: auto;
    padding: 0 1;
    color: $dim;
}
"""


# ── Application ──────────────────────────────────────────────────────

class Holmium(App):
    CSS = HOLMIUM_CSS

    BINDINGS = [
        Binding("ctrl+c", "interrupt", "Stop", priority=True),
        Binding("ctrl+s", "toggle_sidebar", "Sidebar"),
        Binding("ctrl+l", "clear", "Clear"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.current_mode = load_mode()
        self.user_name = self.config.get("user_name", "user")
        self._processing = False
        self._token_count = 0
        self._current_worker: Worker | None = None

    def compose(self) -> ComposeResult:
        yield HeaderBar(id="header-bar")
        with Container(id="body-row"):
            yield StatsSidebar(id="stats-sidebar")
            with Vertical(id="main-panel"):
                yield ChatPanel(id="conversation", highlight=True, markup=False)
                yield Static("", id="stream-buffer")
                yield HolmiumInput(id="input-area")
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        self.title = f"HOLMIUM — {self.user_name}"
        header = self.query_one(HeaderBar)
        header.current_mode = self.current_mode
        header.user_name = self.user_name
        header.set_user(self.user_name)
        self.set_interval(2.0, self._tick)
        self.call_after_refresh(self._on_startup)

    def _on_startup(self) -> None:
        conv = self.query_one("#conversation", ChatPanel)
        mode_label = MODE_LABELS.get(self.current_mode, self.current_mode.upper())
        conv.add_system(f"Holmium OS — Mode: [{MODE_COLORS[self.current_mode]}]{mode_label}[/]")
        conv.add_system(f"User: {self.user_name}  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        conv.add_system("Type :help for commands.")

    async def _tick(self) -> None:
        data = await http_unix("GET", "/status")
        header = self.query_one(HeaderBar)
        sidebar = self.query_one(StatsSidebar)

        if data is None:
            header.conn_status = "error"
            header.set_conn_detail("Backend unavailable — retrying...")
            sidebar.stats = {"cpu_percent": "?", "ram_percent": "?", "gpu_util": "?",
                             "gpu_temp": "?", "vram_used_gb": "?", "vram_total_gb": 16,
                             "vllm_status": "down", "wg_handshake": "down",
                             "uptime": "?", "disk_percent": "?"}
            return

        header.conn_status = "connected"
        vllm = data.get("vllm_status", "?")
        wg = data.get("wg_handshake", "?")
        header.set_conn_detail(f"vLLM: {vllm}  |  WG: {wg}")
        sidebar.stats = data

    # ── Actions ──────────────────────────────────────────────────────

    def action_interrupt(self) -> None:
        if self._processing and self._current_worker:
            self._current_worker.cancel()
            self._current_worker = None
            self._processing = False
            conv = self.query_one("#conversation", ChatPanel)
            conv.add_system("Interrupted.")
            stream = self.query_one("#stream-buffer", Static)
            stream.update("")
            stream.display = False

    def action_toggle_sidebar(self) -> None:
        sidebar = self.query_one("#stats-sidebar")
        sidebar.display = not sidebar.display

    def action_clear(self) -> None:
        conv = self.query_one("#conversation", ChatPanel)
        conv.clear()
        conv.add_system("Conversation cleared.")

    # ── Mode ─────────────────────────────────────────────────────────

    def _cycle_mode(self) -> None:
        idx = MODES.index(self.current_mode) if self.current_mode in MODES else 0
        nxt = MODES[(idx + 1) % len(MODES)]
        self._set_mode(nxt)

    def _set_mode(self, mode: str) -> None:
        self.current_mode = mode
        save_mode(mode)
        header = self.query_one(HeaderBar)
        header.current_mode = mode
        status = self.query_one(StatusBar)
        status.current_mode = mode
        conv = self.query_one("#conversation", ChatPanel)
        label = MODE_LABELS.get(mode, mode.upper())
        conv.add_system(f"Switched to [{MODE_COLORS[mode]}]{label}[/] mode")

    # ── Input Handling ───────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        if not raw:
            return

        inp = self.query_one("#chat-input", Input)
        inp.value = ""

        if raw.startswith("//"):
            return

        if raw.startswith(":"):
            self._execute_command(raw[1:])
            return

        conv = self.query_one("#conversation", ChatPanel)
        conv.add_user(raw)
        self._send_chat(raw)

    def on_key(self, event) -> None:
        if event.key == "tab":
            event.prevent_default()
            self._cycle_mode()
            return

    # ── Commands ─────────────────────────────────────────────────────

    def _execute_command(self, cmd: str) -> None:
        conv = self.query_one("#conversation", ChatPanel)
        parts = cmd.strip().split()
        if not parts:
            return
        base = parts[0].lower()

        if base == "help":
            self.push_screen(HelpPopup())
        elif base == "clear":
            conv.clear()
            conv.add_system("Conversation cleared.")
        elif base == "memory":
            self._backend_get("memory/list")
        elif base == "notes":
            self._backend_get("notes/list")
        elif base == "todo":
            self._backend_get("todo/list")
        elif base == "mode" and len(parts) >= 2:
            mode = parts[1].lower()
            if mode in MODES:
                self._set_mode(mode)
            else:
                conv.add_system(f"Unknown mode [{COLOR_ERROR}]{mode}[/]. Use: work, think, image, help")
        elif base == "web" and len(parts) >= 2:
            self._backend_post(f"web/{parts[1]}")
        else:
            conv.add_system(f"Unknown command [{COLOR_CYAN}]:{base}[/]. Try :help")

    # ── Chat ─────────────────────────────────────────────────────────

    def _send_chat(self, text: str) -> None:
        self._processing = True
        self._current_worker = self.run_worker(self._stream_worker(text), exclusive=True)

    async def _stream_worker(self, text: str) -> None:
        conv = self.query_one("#conversation", ChatPanel)
        stream = self.query_one("#stream-buffer", Static)
        buf = ""

        stream.display = True
        stream.update("")

        try:
            async for token in chat_stream_tokens(text, self.current_mode):
                if token == "__BACKEND_UNAVAILABLE__":
                    conv.add_error(
                        "Backend unavailable.\n"
                        f"  Socket: [{COLOR_DIM}]{BACKEND_SOCKET}[/]"
                    )
                    stream.display = False
                    return
                buf += token
                stream.update(buf)

            if buf:
                conv.add_holmium(buf)
                self._token_count += 1
                try:
                    self.query_one("#status-tokens", Static).update(
                        f"[{COLOR_DIM}]tk: {self._token_count}[/]"
                    )
                except NoMatches:
                    pass

        except asyncio.CancelledError:
            if buf:
                conv.add_holmium(buf)
                conv.add_system("Interrupted.")
        except Exception as e:
            conv.add_error(f"Error: {e}")
        finally:
            stream.display = False
            stream.update("")
            self._processing = False
            self._current_worker = None

    def _backend_get(self, endpoint: str) -> None:
        self.run_worker(self._backend_get_worker(endpoint))

    async def _backend_get_worker(self, endpoint: str) -> None:
        conv = self.query_one("#conversation", ChatPanel)
        result = await http_unix("GET", f"/{endpoint}")
        if result is None:
            conv.add_error(f"Backend unavailable for /{endpoint}")
        else:
            text = json.dumps(result, indent=2, ensure_ascii=False)
            if len(text) > 500:
                text = text[:500] + "\n... (truncated)"
            conv.add_system(text)

    def _backend_post(self, endpoint: str) -> None:
        self.run_worker(self._backend_post_worker(endpoint))

    async def _backend_post_worker(self, endpoint: str) -> None:
        conv = self.query_one("#conversation", ChatPanel)
        result = await http_unix("POST", f"/{endpoint}", body=b"{}")
        if result is None:
            conv.add_error(f"Backend unavailable for /{endpoint}")
        else:
            text = json.dumps(result, indent=2, ensure_ascii=False)
            if len(text) > 500:
                text = text[:500] + "\n... (truncated)"
            conv.add_system(text)


def main() -> None:
    app = Holmium()
    app.run()


if __name__ == "__main__":
    main()
