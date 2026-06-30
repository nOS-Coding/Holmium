#!/usr/bin/env python3
"""Holmium CLI — Linux client for Holmium Personal AI OS.
Run without arguments to launch the TUI. Use subcommands for scripting."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TransferSpeedColumn
from rich.table import Table
from rich import box

console = Console()

CONFIG_PATH = Path.home() / ".config" / "holmium" / "config.json"
DEFAULT_SERVER = "127.0.0.1"
DEFAULT_PORT = 443


def _load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        if CONFIG_PATH.exists():
            console.print("[red]Invalid config file. Reconfigure with 'holmium config'.[/red]")
            sys.exit(1)
        return {"server": DEFAULT_SERVER, "port": DEFAULT_PORT, "token": ""}


def _client() -> httpx.Client:
    cfg = _load_config()
    server = cfg.get("server", DEFAULT_SERVER)
    port = cfg.get("port", DEFAULT_PORT)
    token = cfg.get("token", "")
    base = f"https://{server}:{port}"
    headers = {"X-Holmium-Token": token} if token else {}
    return httpx.Client(base_url=base, headers=headers, verify=False, timeout=30.0)


def _get(path: str, **kwargs) -> dict:
    with _client() as c:
        resp = c.get(path, **kwargs)
        resp.raise_for_status()
        return resp.json()


def _post(path: str, data: dict = None, **kwargs) -> dict:
    with _client() as c:
        resp = c.post(path, json=data, **kwargs)
        resp.raise_for_status()
        return resp.json()


def _put(path: str, data: dict = None) -> dict:
    with _client() as c:
        resp = c.put(path, json=data)
        resp.raise_for_status()
        return resp.json()


def _delete(path: str) -> dict:
    with _client() as c:
        resp = c.delete(path)
        resp.raise_for_status()
        return resp.json()


# ---- Config ----

def cmd_config(args: argparse.Namespace) -> None:
    if args.set:
        parts = args.set.split("=", 1)
        if len(parts) != 2:
            console.print("[red]Usage: holmium config --set key=value[/red]")
            return
        key, value = parts[0].strip(), parts[1].strip()
        cfg = _load_config()
        if key in ("server", "port", "token"):
            if key == "port":
                cfg[key] = int(value)
            else:
                cfg[key] = value
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
        console.print(f"[green]✓ Set {key} = {value}[/green]")
        return

    cfg = _load_config()
    console.print(f"[cyan]Server:[/] {cfg.get('server', DEFAULT_SERVER)}")
    console.print(f"[cyan]Port:[/] {cfg.get('port', DEFAULT_PORT)}")
    console.print(f"[cyan]Token:[/] {'<set>' if cfg.get('token') else '<empty>'}")


# ---- Status ----

def cmd_status(args: argparse.Namespace) -> None:
    if args.ping:
        try:
            data = _get("/status")
            server = data.get("server", "unknown")
            latency = data.get("latency_ms", 0)
            console.print(f"[green]✓ Server {server} — {latency}ms[/green]")
        except Exception as e:
            console.print(f"[red]✗ Ping failed: {e}[/red]")
        return

    if args.logs:
        try:
            with _client() as c:
                with c.stream("GET", "/logs") as resp:
                    for line in resp.iter_lines():
                        if line:
                            ts = datetime.now().strftime("%H:%M:%S")
                            console.print(f"[dim]{ts}[/dim] {line}")
        except KeyboardInterrupt:
            pass
        return

    try:
        data = _post("/status")
    except Exception:
        data = _get("/status")

    table = Table(title="System Status", box=box.ROUNDED)
    table.add_column("Component", style="cyan")
    table.add_column("Value", style="white")

    cpu = data.get("cpu", {})
    table.add_row("CPU", f"{cpu.get('percent', '?')}% ({cpu.get('count', '?')} cores)")
    mem = data.get("memory", {})
    table.add_row("RAM", f"{mem.get('available_gb', '?')}GB / {mem.get('total_gb', '?')}GB ({mem.get('percent', '?')}%)")
    gpu = data.get("gpu", {})
    if gpus := gpu.get("gpus"):
        for g in gpus:
            table.add_row("GPU", f"{g.get('name', '?')} — {g.get('temperature', '?')}°C")
    uptime = data.get("uptime", {})
    table.add_row("Uptime", uptime.get("human", "?"))
    vllm = data.get("vllm", {})
    vllm_status = vllm.get("status", "unknown")
    vllm_color = "green" if vllm_status == "healthy" else "red"
    table.add_row("vLLM", f"[{vllm_color}]{vllm_status}[/{vllm_color}]")
    wg = data.get("wireguard", {})
    peers = len(wg.get("peers", []))
    table.add_row("WireGuard", f"{peers} peer(s)")
    console.print(table)

    if args.system:
        return

    sys_data = {
        "cpu_percent": cpu.get("percent"),
        "ram_percent": mem.get("percent"),
        "gpu_temp": gpus[0].get("temperature") if gpus else None,
    }
    console.print(f"\nCPU: {sys_data['cpu_percent']}%  RAM: {sys_data['ram_percent']}%", style="bold")


# ---- Send (upload/download) ----

def cmd_send(args: argparse.Namespace) -> None:
    local = args.local
    remote = args.remote
    is_image = args.image

    if Path(local).exists():
        path = Path(local)
        filename = path.name
        size = path.stat().st_size

        upload_path = f"/upload/{remote}"
        content_type = "image/*" if is_image else "application/octet-stream"

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TransferSpeedColumn(),
        ) as progress:
            task = progress.add_task(f"Uploading {'image' if is_image else 'file'} {filename}...", total=size)
            with _client() as c:
                with open(path, "rb") as f:
                    resp = c.put(
                        upload_path,
                        content=f,
                        headers={"Content-Type": content_type},
                    )
            progress.update(task, completed=size)

        if resp.is_success:
            console.print(f"[green]✓ Uploaded {filename} to {remote}[/green]")
            if is_image:
                console.print(f"[cyan]Image sent — Holmium can see it at /files/{remote}[/cyan]")
        else:
            console.print(f"[red]✗ Upload failed: {resp.status_code}[/red]")
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TransferSpeedColumn(),
        ) as progress:
            task = progress.add_task(f"Downloading {remote}...", total=100)
            with _client() as c:
                with c.stream("GET", f"/download/{remote}") as resp:
                    if resp.is_success:
                        dest = Path(local)
                        with open(dest, "wb") as f:
                            for chunk in resp.iter_bytes():
                                f.write(chunk)
                                progress.update(task, advance=50)
                        progress.update(task, completed=100)
                        console.print(f"[green]✓ Downloaded to {local}[/green]")
                    else:
                        console.print(f"[red]✗ Download failed: {resp.status_code}[/red]")


# ---- Chat (one-shot) ----

def cmd_chat(args: argparse.Namespace) -> None:
    "Send a single message and print the response."
    import websockets
    cfg = _load_config()
    server = cfg.get("server", DEFAULT_SERVER)
    port = cfg.get("port", DEFAULT_PORT)
    token = cfg.get("token", "")
    uri = f"wss://{server}:{port}/ws/chat"

    async def _chat():
        async with websockets.connect(
            uri, ping_interval=20, ping_timeout=10,
            extra_headers={"X-Holmium-Token": token} if token else {},
        ) as ws:
            await ws.send(json.dumps({"message": args.message}))
            buffer = ""
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=120.0)
                except asyncio.TimeoutError:
                    console.print("\n[red]Stream timed out[/red]")
                    break
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if msg.get("type") == "token":
                    token_text = msg.get("content", "")
                    buffer += token_text
                    console.print(token_text, end="")
                    sys.stdout.flush()
                elif msg.get("type") == "done":
                    console.print()
                    break
                elif msg.get("type") == "error":
                    console.print(f"\n[red]Error: {msg.get('content', 'unknown')}[/red]")
                    break
                elif msg.get("type") == "tool_call":
                    console.print(f"\n[dim]⚡ tool: {msg.get('name', '')}[/dim]")
                elif msg.get("type") == "tool_result":
                    console.print(f"\n[dim]✓ tool result received[/dim]")

    try:
        asyncio.run(_chat())
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")


# ---- Memory ----

def cmd_memory(args: argparse.Namespace) -> None:
    if args.action == "list":
        data = _get("/facts")
        table = Table(title="Facts", box=box.SIMPLE)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        for k, v in data.items():
            table.add_row(str(k), str(v)[:80])
        console.print(table)

    elif args.action == "edit":
        data = _get("/facts")
        fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="holmium_facts_")
        os.write(fd, json.dumps(data, indent=2).encode())
        os.close(fd)

        editor = os.environ.get("EDITOR", "vim")
        subprocess.run([editor, tmp_path])

        try:
            new_data = json.loads(Path(tmp_path).read_text())
        except json.JSONDecodeError:
            console.print("[red]Invalid JSON — no changes saved[/red]")
            Path(tmp_path).unlink(missing_ok=True)
            return

        diff_added = {k: v for k, v in new_data.items() if k not in data}
        diff_removed = {k: v for k, v in data.items() if k not in new_data}
        diff_changed = {k: v for k, v in new_data.items() if k in data and data[k] != v}

        if diff_added:
            console.print("[green]Added:[/green]")
            for k, v in diff_added.items():
                console.print(f"  + {k}: {v}")
        if diff_removed:
            console.print("[red]Removed:[/red]")
            for k in diff_removed:
                console.print(f"  - {k}")
        if diff_changed:
            console.print("[yellow]Changed:[/yellow]")
            for k, v in diff_changed.items():
                console.print(f"  ~ {k}: {data[k]} → {v}")

        if diff_added or diff_removed or diff_changed:
            _post("/facts", data=new_data)
            console.print("[green]✓ Facts saved[/green]")
        else:
            console.print("[dim]No changes[/dim]")

        Path(tmp_path).unlink(missing_ok=True)

    elif args.action == "forget":
        data = _get("/facts")
        key = args.key
        if key in data:
            _delete(f"/facts/{key}")
            console.print(f"[green]Forgot '{key}'[/green]")
        else:
            console.print(f"[red]Key '{key}' not found[/red]")

    elif args.action == "search":
        data = _get("/facts")
        query = args.query.lower()
        results = {k: v for k, v in data.items() if query in k.lower() or query in str(v).lower()}
        if results:
            table = Table(title=f"Facts matching '{args.query}'", box=box.SIMPLE)
            table.add_column("Key", style="cyan")
            table.add_column("Value", style="white")
            for k, v in results.items():
                table.add_row(str(k), str(v)[:80])
            console.print(table)
        else:
            console.print("[dim]No matching facts[/dim]")


# ---- Notes ----

def cmd_notes(args: argparse.Namespace) -> None:
    if args.action == "list":
        data = _get("/notes")
        table = Table(title="Notes", box=box.SIMPLE)
        table.add_column("ID", style="dim")
        table.add_column("Title", style="cyan")
        table.add_column("Created", style="dim")
        for item in data:
            table.add_row(str(item.get("id", "")), str(item.get("title", "")), str(item.get("created_at", ""))[:10])
        console.print(table)

    elif args.action == "add":
        data = _post("/notes", {"title": args.title})
        console.print(f"[green]✓ Note added (id={data.get('id', '?')})[/green]")


# ---- Todos ----

def cmd_todos(args: argparse.Namespace) -> None:
    if args.action == "list":
        data = _get("/todos")
        table = Table(title="Todos", box=box.SIMPLE)
        table.add_column("ID", style="dim")
        table.add_column("Title", style="cyan")
        table.add_column("Done", style="green")
        for item in data:
            done = "✓" if item.get("done") else " "
            table.add_row(str(item.get("id", "")), str(item.get("title", "")), done)
        console.print(table)

    elif args.action == "done":
        data = _get("/todos")
        found = [t for t in data if args.title.lower() in t.get("title", "").lower()]
        if found:
            _post(f"/todos/{found[0]['id']}/done")
            console.print(f"[green]✓ Marked '{found[0]['title']}' as done[/green]")
        else:
            console.print("[red]Todo not found[/red]")


# ---- Contacts ----

def cmd_contacts(args: argparse.Namespace) -> None:
    if args.action == "list":
        data = _get("/contacts")
        table = Table(title="Contacts", box=box.SIMPLE)
        table.add_column("ID", style="dim")
        table.add_column("Name", style="cyan")
        table.add_column("Email", style="white")
        for item in data:
            table.add_row(str(item.get("id", "")), str(item.get("name", "")), str(item.get("email", "")))
        console.print(table)

    elif args.action == "add":
        parts = args.contact.strip().rsplit(" ", 1)
        name = parts[0]
        email = parts[1] if len(parts) > 1 else ""
        data = _post("/contacts", {"name": name, "email": email})
        console.print(f"[green]✓ Contact added (id={data.get('id', '?')})[/green]")

    elif args.action == "search":
        data = _get("/contacts")
        query = args.query.lower()
        results = [c for c in data if query in c.get("name", "").lower() or query in c.get("email", "").lower()]
        table = Table(title=f"Contacts matching '{args.query}'", box=box.SIMPLE)
        table.add_column("ID", style="dim")
        table.add_column("Name", style="cyan")
        table.add_column("Email", style="white")
        for item in results:
            table.add_row(str(item.get("id", "")), str(item.get("name", "")), str(item.get("email", "")))
        console.print(table)


# ---- Vault ----

def cmd_vault(args: argparse.Namespace) -> None:
    if args.action == "list":
        data = _get("/vault")
        table = Table(title="Vault Keys", box=box.SIMPLE)
        table.add_column("Key", style="cyan")
        for k in data:
            table.add_row(k)
        console.print(table)

    elif args.action == "show":
        data = _get(f"/vault/{args.slug}")
        console.print(f"[bold cyan]{args.slug}:[/bold cyan] {json.dumps(data, indent=2)}")

    elif args.action == "delete":
        data = _delete(f"/vault/{args.slug}")
        console.print(f"[green]Deleted '{args.slug}'[/green]")


# ---- API Keys ----

def cmd_apikeys(args: argparse.Namespace) -> None:
    if args.action == "list":
        data = _get("/api-keys")
        table = Table(title="API Keys", box=box.SIMPLE)
        table.add_column("Label", style="cyan")
        table.add_column("Enabled", style="green")
        for item in data:
            enabled = "✓" if item.get("enabled") else "✗"
            table.add_row(str(item.get("label", "")), enabled)
        console.print(table)

    elif args.action == "search":
        data = _get("/api-keys")
        query = args.query.lower()
        results = [k for k in data if query in k.get("label", "").lower()]
        for item in results:
            console.print(f"{item.get('label', '')}")


# ---- Sessions ----

def cmd_sessions(args: argparse.Namespace) -> None:
    if args.action == "list":
        data = _get("/sessions")
        table = Table(title="Sessions", box=box.SIMPLE)
        table.add_column("ID", style="dim")
        table.add_column("Type", style="cyan")
        table.add_column("Messages", style="white")
        table.add_column("Last Activity", style="dim")
        for item in data:
            table.add_row(
                str(item.get("session_id", ""))[:8],
                str(item.get("client_type", "")),
                str(item.get("message_count", 0)),
                str(item.get("last_activity", ""))[:16],
            )
        console.print(table)

    elif args.action == "show":
        data = _get(f"/sessions/{args.id}")
        console.print(json.dumps(data, indent=2))


# ---- Finance ----

def cmd_finance(args: argparse.Namespace) -> None:
    if args.action == "report":
        data = _get("/finance/portfolio")
        table = Table(title="Portfolio", box=box.ROUNDED)
        table.add_column("Ticker", style="cyan")
        table.add_column("Price", style="white")
        table.add_column("Change", style="green")
        table.add_column("Value", style="yellow")
        for h in data.get("holdings", []):
            table.add_row(
                h.get("ticker", ""),
                f"${h.get('current_price', 0):.2f}",
                f"{h.get('gain_loss_pct', 0):.1f}%",
                f"${h.get('current_value', 0):.2f}",
            )
        console.print(table)
        console.print(f"Total: ${data.get('total_value', 0):.2f}  "
                      f"P&L: ${data.get('total_gain_loss', 0):.2f} "
                      f"({data.get('total_gain_loss_pct', 0):.1f}%)")

    elif args.action == "history":
        data = _get(f"/finance/history/{args.ticker}")
        table = Table(title=f"{args.ticker.upper()} History", box=box.SIMPLE)
        table.add_column("Date", style="dim")
        table.add_column("Close", style="white")
        table.add_column("Volume", style="dim")
        for row in data[-30:]:
            table.add_row(
                row.get("date", ""),
                f"${row.get('close', 0):.2f}",
                str(row.get("volume", 0)),
            )
        console.print(table)


# ---- Info ----

def cmd_info(args: argparse.Namespace) -> None:
    data = _get("/info")
    table = Table(title="System Info", box=box.SIMPLE)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")
    for k, v in data.items():
        table.add_row(k, str(v)[:100])
    console.print(table)


# ---- Mode ----

def cmd_mode(args: argparse.Namespace) -> None:
    if args.mode in ("think", "work", "image", "help"):
        data = _post("/mode", {"mode": args.mode})
        mode = data.get("mode", args.mode)
        color = {"think": "cyan", "work": "orange1", "image": "magenta", "help": "green"}.get(mode, "white")
        console.print(f"[bold {color}]Mode set to {mode}[/bold {color}]")
    else:
        current = _get("/mode")
        console.print(f"Current mode: {current.get('mode', 'unknown')}")


# ---- Briefing ----

def cmd_briefing(args: argparse.Namespace) -> None:
    console.print("[dim]Generating briefing...[/dim]")
    try:
        data = _post("/briefing")
        console.print(Markdown(data.get("briefing", "No briefing available.")))
    except Exception as e:
        console.print(f"[red]Briefing failed: {e}[/red]")


# ---- Benchmark ----

def cmd_benchmark(args: argparse.Namespace) -> None:
    if args.history:
        data = _get("/benchmark/history")
        if not data:
            console.print("[dim]No benchmark history[/dim]")
            return
        latest = data[-1]
        table = Table(title="Latest Benchmark", box=box.SIMPLE)
        table.add_column("Test", style="cyan")
        table.add_column("Result", style="white")
        for k, v in latest.items():
            if k == "timestamp":
                continue
            if isinstance(v, dict):
                for sk, sv in v.items():
                    table.add_row(f"{k}.{sk}", str(sv))
            else:
                table.add_row(k, str(v))
        console.print(table)
        return

    quick = args.quick
    label = "Quick Benchmark" if quick else "Full Benchmark"
    console.print(f"[dim]Running {label}...[/dim]")
    try:
        data = _post("/benchmark", {"quick": quick})
        table = Table(title=label, box=box.SIMPLE)
        table.add_column("Test", style="cyan")
        table.add_column("Result", style="white")
        for k, v in data.items():
            if k in ("timestamp", "quick"):
                continue
            if isinstance(v, dict):
                for sk, sv in v.items():
                    table.add_row(f"{k}.{sk}", str(sv))
            else:
                table.add_row(k, str(v))
        console.print(table)
    except Exception as e:
        console.print(f"[red]Benchmark failed: {e}[/red]")


# ---- Stats ----

def cmd_stats(args: argparse.Namespace) -> None:
    if args.history:
        data = _get("/stats/history")
        if not data:
            console.print("[dim]No stats history[/dim]")
            return
        table = Table(title="Stats History", box=box.SIMPLE)
        table.add_column("Date", style="dim")
        table.add_column("Messages", style="white")
        table.add_column("Sessions", style="white")
        for row in data[-14:]:
            table.add_row(
                row.get("date", ""),
                str(row.get("messages_sent", 0)),
                str(row.get("sessions_count", 0)),
            )
        console.print(table)
        return

    params = {}
    if args.week:
        params["range"] = "week"
    data = _post("/stats", params)
    console.print(data.get("report", "No stats available."))


# ---- Backup ----

def cmd_backup(args: argparse.Namespace) -> None:
    console.print("[dim]Running backup...[/dim]")
    try:
        data = _post("/backup")
        console.print(f"[green]✓ Backup saved: {data.get('path', '?')}[/green]")
    except Exception as e:
        console.print(f"[red]Backup failed: {e}[/red]")


# ---- Update ----

def cmd_update(args: argparse.Namespace) -> None:
    console.print("[dim]Checking for updates...[/dim]")
    try:
        data = _post("/update")
        if data.get("success"):
            console.print(f"[green]✓ Updated to {data.get('new_version', '?')}[/green]")
        else:
            console.print(f"[red]Update failed: {data.get('error', 'unknown')}[/red]")
    except Exception as e:
        console.print(f"[red]Update failed: {e}[/red]")


# ---- Version ----

def cmd_version(args: argparse.Namespace) -> None:
    try:
        data = _get("/version")
        console.print(f"Holmium v{data.get('version', 'unknown')}  ({data.get('commit', '?')})")
    except Exception:
        console.print(f"Holmium CLI v1.0 (Linux) — server unreachable", style="dim")


# ---- Help ----

def cmd_help(args: argparse.Namespace) -> None:
    table = Table(title="Holmium CLI Commands", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Category", style="bold yellow")
    table.add_column("Command", style="cyan")
    table.add_column("Description", style="white")

    table.add_row("TUI", "holmium", "Launch Textual TUI (default)")
    table.add_row("Shell", "holmium chat <message>", "Send one-shot message")
    table.add_row("Shell", "holmium --help", "This help screen")
    table.add_row("Shell", "holmium --tools", "Live tool registry")
    table.add_row("Config", "holmium config", "Show config")
    table.add_row("Config", "holmium config --set key=val", "Set config value")
    table.add_row("System", "holmium status [-p|-l|-s]", "System dashboard / ping / logs / system-only")
    table.add_row("System", "holmium stats [--week|--history]", "Usage statistics")
    table.add_row("System", "holmium version", "Show version")
    table.add_row("System", "holmium update", "Self-update")
    table.add_row("System", "holmium backup", "Create backup")
    table.add_row("System", "holmium benchmark [--quick|--history]", "Run benchmarks")
    table.add_row("System", "holmium briefing", "Daily briefing")
    table.add_row("System", "holmium mode <think|work|image|help>", "Set conversation mode")
    table.add_row("Files", "holmium send <local> <remote> [--image]", "Upload/download file (--image for pics)")
    table.add_row("Data", "holmium -m list", "List memory facts")
    table.add_row("Data", "holmium -m edit", "Edit facts in $EDITOR")
    table.add_row("Data", "holmium -m forget <key>", "Delete a fact")
    table.add_row("Data", "holmium -m search <q>", "Search facts")
    table.add_row("Data", "holmium -n list", "List notes")
    table.add_row("Data", 'holmium -n add "<title>"', "Add note")
    table.add_row("Data", "holmium -t list", "List todos")
    table.add_row("Data", 'holmium -t done "<title>"', "Complete todo")
    table.add_row("Data", "holmium -c list", "List contacts")
    table.add_row("Data", 'holmium -c add "<name> <email>"', "Add contact")
    table.add_row("Data", "holmium -c search <q>", "Search contacts")
    table.add_row("Data", "holmium -v list", "List vault keys")
    table.add_row("Data", "holmium -v show <slug>", "Show vault entry")
    table.add_row("Data", "holmium -v delete <slug>", "Delete vault entry")
    table.add_row("Data", "holmium -a list", "List API keys")
    table.add_row("Data", "holmium -a search <q>", "Search API keys")
    table.add_row("Data", "holmium -s list", "List sessions")
    table.add_row("Data", "holmium -s show <id>", "Show session")
    table.add_row("Finance", "holmium -f report", "Portfolio report")
    table.add_row("Finance", "holmium -f history <ticker>", "Stock history")
    table.add_row("Info", "holmium -i list", "System info")
    table.add_row("Vault", "holmium --vault add/get/list/delete", "Encrypted vault ops")
    table.add_row("Keys", "holmium --key create/list/revoke", "API key management")

    console.print(table)


# ---- Tools ----

def cmd_tools(args: argparse.Namespace) -> None:
    try:
        data = _get("/tools")
        table = Table(title="Tool Registry", box=box.SIMPLE)
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="white")
        for tool in data:
            table.add_row(tool.get("name", ""), tool.get("description", ""))
        console.print(table)
    except Exception as e:
        console.print(f"[red]Failed to fetch tools: {e}[/red]")


# ---- Vault ops (--vault) ----

def cmd_vault_ops(args: argparse.Namespace) -> None:
    if len(args.args) < 1:
        console.print("Usage: holmium --vault add/get/list/delete [args]")
        return
    op = args.args[0]

    if op == "list":
        data = _get("/vault")
        for k in data:
            console.print(k)
    elif op == "get":
        if len(args.args) < 2:
            console.print("Usage: holmium --vault get <key>")
            return
        data = _get(f"/vault/{args.args[1]}")
        console.print(data.get("value", "not found"))
    elif op == "add":
        if len(args.args) < 3:
            console.print("Usage: holmium --vault add <key> <value>")
            return
        _post("/vault", {"key": args.args[1], "value": args.args[2]})
        console.print("[green]✓ Stored[/green]")
    elif op == "delete":
        if len(args.args) < 2:
            console.print("Usage: holmium --vault delete <key>")
            return
        _delete(f"/vault/{args.args[1]}")
        console.print("[green]✓ Deleted[/green]")
    else:
        console.print(f"[red]Unknown vault op: {op}[/red]")


# ---- Key ops (--key) ----

def cmd_key_ops(args: argparse.Namespace) -> None:
    if len(args.args) < 1:
        console.print("Usage: holmium --key create/list/revoke [args]")
        return
    op = args.args[0]

    if op == "list":
        data = _get("/api-keys")
        for k in data:
            console.print(f"{k.get('label', '')}  {'[green]enabled[/green]' if k.get('enabled') else '[dim]disabled[/dim]'}")
    elif op == "create":
        if len(args.args) < 2:
            console.print("Usage: holmium --key create <label>")
            return
        data = _post("/api-keys", {"label": args.args[1]})
        console.print(f"[green]✓ Key created: {data.get('key', '?')}[/green]")
        console.print("[yellow]Save this — it won't be shown again.[/yellow]")
    elif op == "revoke":
        if len(args.args) < 2:
            console.print("Usage: holmium --key revoke <label>")
            return
        _delete(f"/api-keys/{args.args[1]}")
        console.print("[green]✓ Key revoked[/green]")
    else:
        console.print(f"[red]Unknown key op: {op}[/red]")


# ---- TUI Launcher ----

def launch_tui() -> None:
    try:
        from tui_client import HolmiumTUI
        app = HolmiumTUI()
        app.run()
    except ImportError as e:
        console.print(f"[red]TUI not available: {e}[/red]")
        console.print("[yellow]Install Textual: pip install textual[/yellow]")


# ---- Main ----

def main() -> None:
    # Block on macOS — this is a Linux-only client
    if platform.system() == "Darwin":
        console = Console()
        console.print("[bold pink]Holmium CLI[/] — Linux only.")
        console.print("[dim]Use the native Holmium app on macOS instead.[/dim]")
        sys.exit(1)

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--help", action="store_true")
    parser.add_argument("--tools", action="store_true")
    parser.add_argument("--tui", action="store_true", help="Launch TUI (default when no subcommand)")
    parser.add_argument("--vault", nargs="*", default=None)
    parser.add_argument("--key", nargs="*", default=None)

    parser.add_argument("-m", nargs="*", default=None, metavar="MEMORY_ARGS")
    parser.add_argument("-n", nargs="*", default=None, metavar="NOTES_ARGS")
    parser.add_argument("-t", nargs="*", default=None, metavar="TODOS_ARGS")
    parser.add_argument("-c", nargs="*", default=None, metavar="CONTACTS_ARGS")
    parser.add_argument("-v", nargs="*", default=None, metavar="VAULT_ARGS")
    parser.add_argument("-a", nargs="*", default=None, metavar="APIKEY_ARGS")
    parser.add_argument("-s", nargs="*", default=None, metavar="SESSION_ARGS")
    parser.add_argument("-f", nargs="*", default=None, metavar="FINANCE_ARGS")
    parser.add_argument("-i", nargs="*", default=None, metavar="INFO_ARGS")

    sub = parser.add_subparsers(dest="command")

    p_config = sub.add_parser("config")
    p_config.add_argument("--set", type=str, default="", help="key=value")

    p_status = sub.add_parser("status")
    p_status.add_argument("-p", "--ping", action="store_true")
    p_status.add_argument("-l", "--logs", action="store_true")
    p_status.add_argument("-s", "--system", action="store_true")

    p_send = sub.add_parser("send")
    p_send.add_argument("local")
    p_send.add_argument("remote")
    p_send.add_argument("--image", "-i", action="store_true", help="Mark as image/picture")

    p_chat = sub.add_parser("chat")
    p_chat.add_argument("message", nargs="+")
    p_chat.add_argument("--image", "-i", type=str, default="", help="Attach image file path")

    p_mode = sub.add_parser("mode")
    p_mode.add_argument("mode", nargs="?", default="")

    p_briefing = sub.add_parser("briefing")
    p_bench = sub.add_parser("benchmark")
    p_bench.add_argument("--quick", action="store_true")
    p_bench.add_argument("--history", action="store_true")

    p_stats = sub.add_parser("stats")
    p_stats.add_argument("--week", action="store_true")
    p_stats.add_argument("--history", action="store_true")

    p_backup = sub.add_parser("backup")
    p_update = sub.add_parser("update")
    p_version = sub.add_parser("version")

    args, unknown = parser.parse_known_args()

    # If no subcommand or flags, launch TUI (unless --help is used)
    has_flags = any([
        args.tools, args.tui,
        args.vault is not None, args.key is not None,
        args.m is not None, args.n is not None,
        args.t is not None, args.c is not None,
        args.v is not None, args.a is not None,
        args.s is not None, args.f is not None,
        args.i is not None,
    ])

    if args.help or (args.command is None and not has_flags):
        cmd_help(args)
        return

    if args.tools:
        cmd_tools(args)
        return

    if args.vault is not None:
        args.args = args.vault
        cmd_vault_ops(args)
        return

    if args.key is not None:
        args.args = args.key
        cmd_key_ops(args)
        return

    if args.m is not None:
        if not args.m:
            args.action = "list"
        else:
            args.action = args.m[0]
            if args.action == "edit":
                pass
            elif args.action == "forget":
                if len(args.m) < 2:
                    console.print("Usage: holmium -m forget <key>")
                    return
                args.key = args.m[1]
            elif args.action == "search":
                if len(args.m) < 2:
                    console.print("Usage: holmium -m search <query>")
                    return
                args.query = args.m[1]
        cmd_memory(args)
        return

    if args.n is not None:
        if not args.n:
            args.action = "list"
        else:
            args.action = args.n[0]
            if args.action == "add" and len(args.n) >= 2:
                args.title = " ".join(args.n[1:])
        cmd_notes(args)
        return

    if args.t is not None:
        if not args.t:
            args.action = "list"
        else:
            args.action = args.t[0]
            if args.action == "done" and len(args.t) >= 2:
                args.title = " ".join(args.t[1:])
        cmd_todos(args)
        return

    if args.c is not None:
        if not args.c:
            args.action = "list"
        else:
            args.action = args.c[0]
            if args.action == "add" and len(args.c) >= 2:
                args.contact = " ".join(args.c[1:])
            elif args.action == "search" and len(args.c) >= 2:
                args.query = " ".join(args.c[1:])
        cmd_contacts(args)
        return

    if args.v is not None:
        if not args.v:
            args.action = "list"
        else:
            args.action = args.v[0]
            if args.action in ("show", "delete") and len(args.v) >= 2:
                args.slug = args.v[1]
        cmd_vault(args)
        return

    if args.a is not None:
        if not args.a:
            args.action = "list"
        else:
            args.action = args.a[0]
            if args.action == "search" and len(args.a) >= 2:
                args.query = " ".join(args.a[1:])
        cmd_apikeys(args)
        return

    if args.s is not None:
        if not args.s:
            args.action = "list"
        else:
            args.action = args.s[0]
            if args.action == "show" and len(args.s) >= 2:
                args.id = args.s[1]
        cmd_sessions(args)
        return

    if args.f is not None:
        if not args.f:
            args.action = "report"
        else:
            args.action = args.f[0]
            if args.action == "history" and len(args.f) >= 2:
                args.ticker = args.f[1]
        cmd_finance(args)
        return

    if args.i is not None:
        cmd_info(args)
        return

    # Dispatch subcommands
    if args.command == "config":
        cmd_config(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "send":
        cmd_send(args)
    elif args.command == "chat":
        msg = " ".join(args.message)
        if args.image:
            cmd_send(argparse.Namespace(local=args.image, remote=os.path.basename(args.image), image=True))
            console.print()
        cmd_chat(argparse.Namespace(message=msg))
    elif args.command == "mode":
        cmd_mode(args)
    elif args.command == "briefing":
        cmd_briefing(args)
    elif args.command == "benchmark":
        cmd_benchmark(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "backup":
        cmd_backup(args)
    elif args.command == "update":
        cmd_update(args)
    elif args.command == "version":
        cmd_version(args)
    elif args.tui:
        launch_tui()
    else:
        launch_tui()


if __name__ == "__main__":
    main()
