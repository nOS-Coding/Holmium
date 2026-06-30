"""Holmium TUI — Remote Textual interface for Holmium AI.
Connects to Holmium over HTTPS/WebSocket. Launched by `holmium` (no args)."""

from __future__ import annotations

import asyncio
import json
import os
import platform
import re
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator

import httpx
import websockets

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

COLOR_BG = "#0d0d0d"
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

DEFAULT_SERVER = "127.0.0.1"
DEFAULT_PORT = 443
CONFIG_PATH = Path.home() / ".config" / "holmium" / "config.json"


def load_config() -> dict[str, Any]:
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"server": DEFAULT_SERVER, "port": DEFAULT_PORT, "token": "", "user_name": "user"}


def http_client() -> httpx.Client:
    cfg = load_config()
    server = cfg.get("server", DEFAULT_SERVER)
    port = cfg.get("port", DEFAULT_PORT)
    token = cfg.get("token", "")
    base = f"https://{server}:{port}"
    headers = {"X-Holmium-Token": token} if token else {}
    return httpx.Client(base_url=base, headers=headers, verify=False, timeout=10.0)


async def http_get(path: str) -> dict | None:
    try:
        cfg = load_config()
        server = cfg.get("server", DEFAULT_SERVER)
        port = cfg.get("port", DEFAULT_PORT)
        token = cfg.get("token", "")
        base = f"https://{server}:{port}"
        headers = {"X-Holmium-Token": token} if token else {}
        async with httpx.AsyncClient(base_url=base, headers=headers, verify=False, timeout=5.0) as c:
            resp = await c.get(path)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


async def chat_stream(message: str, mode: str) -> AsyncGenerator[str, None]:
    cfg = load_config()
    server = cfg.get("server", DEFAULT_SERVER)
    port = cfg.get("port", DEFAULT_PORT)
    token = cfg.get("token", "")
    uri = f"wss://{server}:{port}/ws/chat"

    try:
        async with websockets.connect(
            uri, ping_interval=20, ping_timeout=10,
            extra_headers={"X-Holmium-Token": token} if token else {},
        ) as ws:
            await ws.send(json.dumps({"message": message, "mode": mode}))
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=120.0)
                except asyncio.TimeoutError:
                    yield "__TIMEOUT__"
                    return
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if msg.get("type") == "token":
                    yield msg.get("content", "")
                elif msg.get("type") == "done":
                    return
                elif msg.get("type") == "error":
                    yield f"__ERROR__: {msg.get('content', 'unknown')}"
                    return
                elif msg.get("type") == "tool_call":
                    yield f"\n[dim]⚡ {msg.get('name', 'tool')}[/dim]\n"
                elif msg.get("type") == "tool_result":
                    pass
    except websockets.WebSocketException as e:
        yield f"__CONNECTION_ERROR__: {e}"
    except Exception as e:
        yield f"__ERROR__: {e}"


async def upload_image(filepath: str) -> dict | None:
    path = Path(filepath)
    if not path.exists():
        return None
    try:
        async with httpx.AsyncClient(verify=False, timeout=120.0) as c:
            cfg = load_config()
            server = cfg.get("server", DEFAULT_SERVER)
            port = cfg.get("port", DEFAULT_PORT)
            token = cfg.get("token", "")
            base = f"https://{server}:{port}"
            headers = {"X-Holmium-Token": token} if token else {}
            with open(path, "rb") as f:
                resp = await c.put(
                    f"{base}/upload/{path.name}",
                    content=f.read(),
                    headers={**headers, "Content-Type": "image/*"},
                )
            if resp.is_success:
                return {"status": "ok", "filename": path.name}
            return {"status": "error", "message": resp.text}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── Widgets ──────────────────────────────────────────────────────────

class HelpPopup(Screen):
    CSS = """
    Screen { background: rgba(0, 0, 0, 0.75); }
    #help-box { background: #0a0a0a; border: solid #1a1a2e; margin: 4 10; padding: 1 2; height: auto; }
    #help-title { text-style: bold; color: #00BCD4; padding-bottom: 1; }
    #help-content { color: #E0E0E0; }
    #help-close { color: #666666; padding-top: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Static("Holmium TUI Help", id="help-title")
            yield Static("", id="help-content")
            yield Static("[dim]Press any key to close[/]", id="help-close")

    def on_mount(self) -> None:
        cmds = (
            "[bold cyan]Commands[/]\n"
            f"  [#00BCD4]:help[/]      Show this help\n"
            f"  [#00BCD4]:clear[/]     Clear conversation\n"
            f"  [#00BCD4]:mode[/]      Switch mode (think/work/image/help)\n"
            f"  [#00BCD4]:send <path>[/] Send an image/file\n"
            f"  [#00BCD4]:status[/]    Show connection status\n"
            f"\n"
            f"[bold]Key Bindings[/]\n"
            f"  [#666666]Tab[/]         Cycle mode\n"
            f"  [#666666]Ctrl+C[/]      Cancel current response\n"
            f"  [#666666]Ctrl+S[/]      Toggle sidebar\n"
            f"  [#666666]Ctrl+L[/]      Clear conversation\n"
            f"  [#666666]Ctrl+P[/]      Send picture (opens file picker)\n"
        )
        self.query_one("#help-content", Static).update(cmds)

    def on_key(self, event) -> None:
        self.app.pop_screen()


class HeaderBar(Widget):
    current_mode = reactive("work")
    conn_status = reactive("connecting")
    user_name = "user"

    def compose(self) -> ComposeResult:
        with Horizontal(id="header-top"):
            with Vertical(id="header-left"):
                yield Static("[#00BCD4 bold]HOLMIUM[/] [#FF69B4]●[/]", id="header-title")
            with Horizontal(id="header-right"):
                yield Static("", id="mode-badge")
                yield Static("", id="conn-dot")

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


class StatsSidebar(Widget):
    stats = reactive({})

    def compose(self) -> ComposeResult:
        with Vertical(id="stats-inner"):
            yield Static("[#666666]┌─ HOLMIUM ──────────┐[/]", id="stats-title")
            yield Static("", id="stats-content")

    def watch_stats(self, s: dict[str, Any]) -> None:
        cpu = s.get("cpu_percent", "?")
        ram = s.get("ram_percent", "?")
        gpu = f"{s.get('gpu_util', '?')}% / {s.get('gpu_temp', '?')}°C"
        vram = f"{s.get('vram_used_gb', '?')}G / {s.get('vram_total_gb', 16)}G"
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
            yield Input(placeholder="Ask Holmium anything... (:send /path/to/pic)", id="chat-input")


class StatusBar(Widget):
    current_mode = reactive("work")

    def compose(self) -> ComposeResult:
        yield Static("", id="status-mode")
        yield Static(
            "[#666666]Tab:mode  Ctrl+C:stop  Ctrl+S:sidebar  Ctrl+L:clear  Ctrl+P:pic[/]",
            id="status-hints",
        )

    def watch_current_mode(self, mode: str) -> None:
        color = MODE_COLORS.get(mode, COLOR_TEXT)
        label = MODE_LABELS.get(mode, mode.upper())
        try:
            self.query_one("#status-mode", Static).update(f"[{color} bold][{label}][/]")
        except NoMatches:
            pass


# ── CSS ──────────────────────────────────────────────────────────────

HOLMIUM_CSS = """
$bg: #0d0d0d;
$surface: #0a0a0a;
$border: #1a1a2e;
$cyan: #00BCD4;
$pink: #FF69B4;
$text: #E0E0E0;
$dim: #666666;
$subtle: #444444;

Screen { background: $bg; }

#header-top {
    background: $surface;
    height: 3;
    border-bottom: solid $border;
    padding: 0 1;
    layout: horizontal;
}

#header-left { width: auto; content-align: left middle; }
#header-right { width: 1fr; content-align: right middle; }

#mode-badge { text-style: bold; margin-right: 1; }
#conn-dot { color: $dim; }

#body-row { height: 1fr; layout: horizontal; }

#stats-sidebar {
    background: $surface;
    width: 24;
    padding: 0 1;
    border-right: solid $border;
    overflow-y: auto;
}

#stats-inner { height: auto; }
#stats-title { color: $dim; padding-bottom: 1; }
#stats-content { color: $dim; }

#main-panel { background: $bg; height: 1fr; }

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

#input-row { height: 3; background: $surface; border-top: solid $border; layout: horizontal; }

#input-prefix { color: #FF69B4; width: 5; content-align: center middle; text-style: bold; }

#chat-input { background: transparent; color: $text; border: none; padding: 0 1; height: 3; }
#chat-input:focus { background: #111111; }
#chat-input .input--placeholder { color: $subtle; }

#status-bar { background: $surface; height: 1; layout: horizontal; border-top: solid $border; }
#status-mode { width: auto; padding: 0 1; }
#status-hints { width: 1fr; color: $dim; text-align: center; }
"""


# ── Application ──────────────────────────────────────────────────────

class HolmiumTUI(App):
    CSS = HOLMIUM_CSS

    BINDINGS = [
        Binding("ctrl+c", "interrupt", "Stop", priority=True),
        Binding("ctrl+s", "toggle_sidebar", "Sidebar"),
        Binding("ctrl+l", "clear", "Clear"),
        Binding("ctrl+p", "send_picture", "Send Pic"),
    ]

    def __init__(self) -> None:
        super().__init__()
        cfg = load_config()
        self.current_mode = "work"
        self.user_name = cfg.get("user_name", "user")
        self._processing = False
        self._current_worker: Worker | None = None

    def compose(self) -> ComposeResult:
        yield HeaderBar(id="header-top")
        with Container(id="body-row"):
            yield StatsSidebar(id="stats-sidebar")
            with Vertical(id="main-panel"):
                yield ChatPanel(id="conversation", highlight=True, markup=False)
                yield Static("", id="stream-buffer")
                yield HolmiumInput(id="input-area")
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        self.title = f"Holmium — {self.user_name}"
        header = self.query_one(HeaderBar)
        header.current_mode = self.current_mode
        header.user_name = self.user_name
        self.set_interval(5.0, self._tick)
        self.call_after_refresh(self._on_startup)

    def _on_startup(self) -> None:
        conv = self.query_one("#conversation", ChatPanel)
        mode_label = MODE_LABELS.get(self.current_mode, self.current_mode.upper())
        conv.add_system(f"Connected to Holmium — Mode: [{MODE_COLORS[self.current_mode]}]{mode_label}[/]")
        conv.add_system(f"User: {self.user_name}  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        conv.add_system("Type :help for commands. Ctrl+P to send a picture.")

    async def _tick(self) -> None:
        data = await http_get("/status")
        header = self.query_one(HeaderBar)
        sidebar = self.query_one(StatsSidebar)

        if data is None:
            header.conn_status = "error"
            sidebar.stats = {
                "cpu_percent": "?", "ram_percent": "?", "gpu_util": "?",
                "gpu_temp": "?", "vram_used_gb": "?", "vram_total_gb": 16,
                "vllm_status": "down", "wg_handshake": "down",
                "uptime": "?", "disk_percent": "?",
            }
            return

        header.conn_status = "connected"
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

    def action_send_picture(self) -> None:
        inp = self.query_one("#chat-input", Input)
        inp.focus()
        conv = self.query_one("#conversation", ChatPanel)
        conv.add_system("Ctrl+P: Enter the path to your image and press Enter, or use :send /path/to/img.jpg")

    # ── Mode ─────────────────────────────────────────────────────────

    def _cycle_mode(self) -> None:
        idx = MODES.index(self.current_mode) if self.current_mode in MODES else 0
        nxt = MODES[(idx + 1) % len(MODES)]
        self._set_mode(nxt)

    def _set_mode(self, mode: str) -> None:
        self.current_mode = mode
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
        elif base == "mode" and len(parts) >= 2:
            mode = parts[1].lower()
            if mode in MODES:
                self._set_mode(mode)
            else:
                conv.add_system(f"Unknown mode [{COLOR_ERROR}]{mode}[/]. Use: work, think, image, help")
        elif base == "send" and len(parts) >= 2:
            filepath = " ".join(parts[1:])
            self._send_image(filepath)
        elif base == "status":
            self._fetch_status()
        else:
            conv.add_system(f"Unknown command [{COLOR_CYAN}]:{base}[/]. Try :help")

    # ── Image Sending ────────────────────────────────────────────────

    def _send_image(self, filepath: str) -> None:
        conv = self.query_one("#conversation", ChatPanel)
        path = Path(filepath)
        if not path.exists():
            conv.add_error(f"File not found: {filepath}")
            return

        ext = path.suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"):
            conv.add_system(f"Sending file: {path.name}")
        else:
            conv.add_system(f"Sending image: {path.name}")

        self.run_worker(self._send_image_worker(filepath))

    async def _send_image_worker(self, filepath: str) -> None:
        conv = self.query_one("#conversation", ChatPanel)
        result = await upload_image(filepath)
        if result and result.get("status") == "ok":
            conv.add_system(f"[green]✓[/] Sent {result['filename']}")
            self._send_chat(f"[Sent file: {result['filename']}]")
        else:
            msg = result.get("message", "unknown error") if result else "upload failed"
            conv.add_error(f"Upload failed: {msg}")

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
            async for token in chat_stream(text, self.current_mode):
                if token.startswith("__CONNECTION_ERROR__"):
                    conv.add_error(f"Connection failed: {token.split(':', 1)[-1].strip()}")
                    stream.display = False
                    return
                if token.startswith("__ERROR__"):
                    conv.add_error(token.split(":", 1)[-1].strip())
                    stream.display = False
                    return
                if token == "__TIMEOUT__":
                    conv.add_error("Response timed out.")
                    stream.display = False
                    return
                buf += token
                stream.update(buf)

            if buf:
                conv.add_holmium(buf)

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

    def _fetch_status(self) -> None:
        self.run_worker(self._fetch_status_worker())

    async def _fetch_status_worker(self) -> None:
        conv = self.query_one("#conversation", ChatPanel)
        data = await http_get("/status")
        if data is None:
            conv.add_error("Cannot reach Holmium server")
        else:
            uptime = data.get("uptime", {}).get("human", "?")
            vllm = data.get("vllm_status", "?")
            wg = data.get("wg_handshake", "?")
            peers = data.get("wireguard", {}).get("peers", [])
            text = (
                f"[cyan]Connected to Holmium[/]\n"
                f"  vLLM: {vllm}  |  WG: {wg}  |  Peers: {len(peers)}\n"
                f"  Uptime: {uptime}"
            )
            conv.add_system(text)


def main() -> None:
    app = HolmiumTUI()
    app.run()


if __name__ == "__main__":
    main()
