from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from rich.text import Text
from rich.style import Style

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container, Grid
from textual.screen import Screen
from textual.widgets import Static, Input, Button, Header, Footer, ListView, ListItem, Checkbox, RadioSet, RadioButton, Label, ProgressBar, TextArea
from textual.widget import Widget

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

CONFIG_PATH = Path("/etc/holmium/config.json")
LICENSE_PATH = Path("/etc/holmium/license.json")
FIRST_RUN_FLAG = Path("/etc/holmium/first_run")

HOLMIUM_LOGO = r"""
██████████   ██████   ███  ███ ███ ███ ██   ██
██          ██    ██  ██ ███ ██  ██  ██ ██   ██
██          ██    ██  ██  █   ██  ██  ██ ██   ██
██  ███████ ████████  ██      ██  ██  ██ ███████
██  ██  ██  ██    ██  ██      ██  ██  ██ ██   ██
██  ██  ██  ██    ██  ██      ██  ██  ██ ██   ██
██████  ██ ██    ██ ████    ██████ ████ ██   ██
"""

SHARED_CSS = f"""
Screen {{
    background: {COLOR_BG};
}}

Static {{
    color: {COLOR_TEXT};
}}

Button {{
    background: {COLOR_CYAN};
    color: {COLOR_BG};
    border: none;
    padding: 0 2;
    min-width: 16;
    height: 3;
}}

Button:hover {{
    background: {COLOR_PINK};
}}

Button:focus {{
    background: {COLOR_PINK};
}}

Button.accent {{
    background: {COLOR_PINK};
    color: {COLOR_BG};
}}

Button.warning {{
    background: {COLOR_ERROR};
    color: {COLOR_BG};
}}

Button.success {{
    background: {COLOR_GREEN};
    color: {COLOR_BG};
}}

Input {{
    background: {COLOR_SURFACE};
    color: {COLOR_TEXT};
    border: solid {COLOR_BORDER};
    padding: 0 1;
    min-height: 3;
}}

Input:focus {{
    border: solid {COLOR_CYAN};
}}

Label {{
    color: {COLOR_TEXT};
    padding-bottom: 0;
}}

RadioSet {{
    background: {COLOR_SURFACE};
    border: solid {COLOR_BORDER};
    padding: 1;
}}

RadioButton {{
    color: {COLOR_TEXT};
    padding: 0 1;
}}

RadioButton:hover {{
    color: {COLOR_CYAN};
}}

RadioButton.radio--selected {{
    color: {COLOR_CYAN};
}}

ListView {{
    background: {COLOR_SURFACE};
    border: solid {COLOR_BORDER};
}}

ListItem {{
    color: {COLOR_TEXT};
    padding: 0 1;
}}

ListItem:hover {{
    background: {COLOR_BORDER};
    color: {COLOR_CYAN};
}}

Checkbox {{
    color: {COLOR_TEXT};
    padding: 0 1;
}}

Checkbox:hover {{
    color: {COLOR_CYAN};
}}

Checkbox.checked {{
    color: {COLOR_GREEN};
}}

ProgressBar {{
    background: {COLOR_SURFACE};
    border: solid {COLOR_BORDER};
    color: {COLOR_CYAN};
}}

ProgressBar > .bar--bar {{
    background: {COLOR_CYAN};
}}

ProgressBar > .bar--complete {{
    background: {COLOR_GREEN};
}}

#title {{
    text-style: bold;
    color: {COLOR_CYAN};
    padding: 1 0;
}}

#subtitle {{
    color: {COLOR_DIM};
    padding-bottom: 1;
}}

#error-text {{
    color: {COLOR_ERROR};
}}

#success-text {{
    color: {COLOR_GREEN};
}}

#dim-text {{
    color: {COLOR_DIM};
}}

#warning-text {{
    color: {COLOR_PINK};
}}

.nav-bar {{
    align: center bottom;
    padding: 1 0;
    height: 5;
}}

.nav-bar Button {{
    margin: 0 1;
}}
"""


def run_cmd(cmd, **kwargs):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30, **kwargs)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def detect_gpu() -> str:
    result = run_cmd(["lspci"], check=False)
    if result and result.returncode == 0:
        for line in result.stdout.splitlines():
            if re.search(r'vga|3d|display', line, re.I):
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    return parts[2].strip()
                return parts[-1].strip()
    result = run_cmd(["sh", "-c", "lspci | grep -i 'vga\\|3d\\|display'"], check=False)
    if result and result.returncode == 0 and result.stdout.strip():
        parts = result.stdout.strip().split(":", 2)
        if len(parts) >= 3:
            return parts[2].strip()
        return parts[-1].strip()
    return "Unknown GPU"


def detect_disks() -> list[dict]:
    disks = []
    result = run_cmd(["lsblk", "-dno", "NAME,SIZE,TYPE,MODEL"], check=False)
    if result and result.returncode == 0:
        for line in result.stdout.strip().splitlines():
            parts = line.split(None, 3)
            if len(parts) >= 2 and parts[2] == "disk":
                name = parts[0]
                size = parts[1]
                model = parts[3] if len(parts) >= 4 else ""
                disks.append({"name": name, "size": size, "model": model, "type": "disk"})
    if not disks:
        result = run_cmd(["lsblk", "-dno", "NAME,SIZE"], check=False)
        if result and result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                parts = line.split(None, 1)
                if len(parts) >= 2:
                    disks.append({"name": parts[0], "size": parts[1], "model": "", "type": "disk"})
    return disks


def detect_ram() -> str:
    result = run_cmd(["grep", "MemTotal", "/proc/meminfo"], check=False)
    if result and result.returncode == 0:
        return result.stdout.strip()
    return "Unknown"


def detect_cpu() -> str:
    result = run_cmd(["grep", "model name", "/proc/cpuinfo"], check=False)
    if result and result.returncode == 0:
        lines = result.stdout.strip().splitlines()
        if lines:
            parts = lines[0].split(":", 1)
            return parts[1].strip() if len(parts) >= 2 else lines[0]
    return "Unknown CPU"


def detect_os_installations() -> list[dict]:
    oses = []
    result = run_cmd(["lsblk", "-o", "FSTYPE,LABEL,PARTLABEL,MOUNTPOINT"], check=False)
    if not result or result.returncode != 0:
        return oses
    lines = result.stdout.strip().splitlines()
    header = None
    for line in lines:
        if not line.strip():
            continue
        if header is None:
            header = re.split(r"\s+", line.strip())
            continue
        parts = re.split(r"\s+", line.strip(), maxsplit=len(header) - 1) if header else [line.strip()]
        if len(parts) < 2:
            continue
        fstype = parts[0] if len(parts) > 0 else ""
        label = parts[1] if len(parts) > 1 else ""
        partlabel = parts[2] if len(parts) > 2 else ""
        mount = parts[3] if len(parts) > 3 else ""
        if fstype in ("ext4", "btrfs", "xfs", "ntfs") and mount != "/":
            os_name = label or partlabel or fstype
            known = {
                "debian": "Debian", "ubuntu": "Ubuntu", "kde": "KDE Neon",
                "neon": "KDE Neon", "fedora": "Fedora", "nobara": "Nobara",
                "cachyos": "CachyOS", "cachy": "CachyOS", "root": "Linux",
            }
            label_lower = os_name.lower()
            display_name = "Linux"
            for key, val in known.items():
                if key in label_lower:
                    display_name = val
                    break
            oses.append({
                "fstype": fstype,
                "label": label or partlabel or display_name,
                "display_name": display_name,
                "mount": mount,
            })
    return oses


def detect_timezone() -> str:
    try:
        result = subprocess.run(["readlink", "-f", "/etc/localtime"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            path = result.stdout.strip()
            parts = path.split("zoneinfo/")
            if len(parts) > 1:
                return parts[1]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    result = run_cmd(["timedatectl", "show", "--value", "-p", "Timezone"], check=False)
    if result and result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return "UTC"


def recommend_gpu_variant(gpu_model: str) -> str:
    gpu_lower = gpu_model.lower()
    if "nvidia" in gpu_lower or "geforce" in gpu_lower or "rtx" in gpu_lower:
        for model in ["rtx 5090", "rtx 5080"]:
            if model in gpu_lower:
                return "nvidia-pro"
        for model in ["rtx 5070", "rtx 5060"]:
            if model in gpu_lower:
                return "nvidia-std"
        if "rtx" in gpu_lower:
            return "nvidia-pro"
        return "nvidia-std"
    if "amd" in gpu_lower or "radeon" in gpu_lower or "rx" in gpu_lower:
        return "amd"
    return "nvidia-std"


def detect_first_boot_mode() -> bool:
    if not FIRST_RUN_FLAG.exists():
        return False
    try:
        config = json.loads(CONFIG_PATH.read_text())
        return not config.get("user_name")
    except (FileNotFoundError, json.JSONDecodeError):
        return False


# ── Screens ──────────────────────────────────────────────────────────

class WelcomeScreen(Screen):
    CSS = SHARED_CSS + """
    #welcome-container {
        align: center middle;
        height: 100%;
    }
    #logo-text {
        text-style: bold;
        color: #00BCD4;
        padding: 0 0;
    }
    #version-text {
        color: #FF69B4;
        text-style: bold;
        padding: 0 0 1 0;
    }
    #desc-text {
        color: #E0E0E0;
        padding: 0 0 1 0;
    }
    #prompt-text {
        color: #666666;
        padding: 2 0 0 0;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="welcome-container"):
            yield Static(Text(HOLMIUM_LOGO, style=Style(color=COLOR_CYAN, bold=True)), id="logo-text")
            yield Static("Super Install Manager v1.0", id="version-text")
            yield Static("Holmium OS — Single-Purpose AI Appliance", id="desc-text")
            yield Static("This wizard will install Holmium OS or configure it for first use.", id="desc-text")
            yield Static("Press Enter to continue...", id="prompt-text")

    def on_key(self, event) -> None:
        if event.key == "enter":
            if detect_first_boot_mode():
                self.app.push_screen(FirstBootWelcomeScreen())
            else:
                self.app.push_screen(HardwareDetectionScreen())


class HardwareDetectionScreen(Screen):
    CSS = SHARED_CSS + """
    #detect-container {
        padding: 1 2;
        height: 100%;
    }
    #detect-results {
        padding: 1 0;
    }
    .detect-row {
        padding: 0 1;
        height: 3;
    }
    .detect-label {
        color: #00BCD4;
        width: 10;
    }
    .detect-value {
        color: #E0E0E0;
    }
    #disk-table {
        margin: 1 0;
    }
    .disk-header {
        color: #666666;
        text-style: bold;
        padding: 0 1;
    }
    .disk-row {
        color: #E0E0E0;
        padding: 0 1;
    }
    """

    def __init__(self):
        super().__init__()
        self.gpu = ""
        self.disks = []
        self.ram = ""
        self.cpu = ""
        self.oses = []

    def compose(self) -> ComposeResult:
        with Vertical(id="detect-container"):
            yield Static("Hardware Detection", id="title")
            yield Static("Scanning system hardware...", id="subtitle")
            yield Static("", id="detect-results")
            with Horizontal(classes="nav-bar"):
                yield Button("Re-detect", id="redetect-btn")
                yield Button("Continue", variant="success", id="continue-btn")

    def on_mount(self) -> None:
        self.detect_hardware()

    @work
    async def detect_hardware(self) -> None:
        results = self.query_one("#detect-results", Static)
        results.update("[#666666]Running detection...[/]")

        self.gpu = await asyncio.to_thread(detect_gpu)
        self.disks = await asyncio.to_thread(detect_disks)
        self.ram = await asyncio.to_thread(detect_ram)
        self.cpu = await asyncio.to_thread(detect_cpu)
        self.oses = await asyncio.to_thread(detect_os_installations)

        self._render_results()

    def _render_results(self) -> None:
        lines = []
        lines.append("[bold #00BCD4]System:[/]")
        lines.append(f"  [#666666]CPU:[/]  [#E0E0E0]{self.cpu}[/]")
        lines.append(f"  [#666666]RAM:[/]  [#E0E0E0]{self.ram}[/]")
        lines.append(f"  [#666666]GPU:[/]  [#E0E0E0]{self.gpu}[/]")
        lines.append("")
        lines.append("[bold #00BCD4]Detected Disks:[/]")
        lines.append(f"  [#666666]{'NAME':<8}{'SIZE':<10}{'MODEL':<20}[/]")
        for d in self.disks:
            lines.append(f"  [#E0E0E0]{d['name']:<8}{d['size']:<10}{d['model']:<20}[/]")
        if self.oses:
            lines.append("")
            lines.append("[bold #00BCD4]Existing OS Installations:[/]")
            for os_info in self.oses:
                lines.append(f"  [#E0E0E0]{os_info['display_name']:12} on {os_info['label']} ({os_info['fstype']})[/]")
        self.query_one("#detect-results", Static).update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "redetect-btn":
            self.detect_hardware()
        elif event.button.id == "continue-btn":
            self.app.push_screen(GpuVariantScreen(self.gpu))


class GpuVariantScreen(Screen):
    CSS = SHARED_CSS + """
    #gpu-container {
        padding: 1 2;
        height: 100%;
    }
    #variant-info {
        padding: 1 0;
    }
    .variant-card {
        background: #0a0a0a;
        border: solid #1a1a2e;
        padding: 1;
        margin: 0 0 1 0;
    }
    .variant-card:hover {
        border: solid #00BCD4;
    }
    .variant-name {
        text-style: bold;
        color: #FF69B4;
    }
    .variant-desc {
        color: #E0E0E0;
    }
    """

    def __init__(self, gpu_model: str):
        super().__init__()
        self.gpu_model = gpu_model
        self.recommended = recommend_gpu_variant(gpu_model)

    def compose(self) -> ComposeResult:
        variants = [
            ("nvidia-std", "NVIDIA Standard (nvidia-std)", "Optimized for RTX 5060-5070. Balanced performance and power. Q4_K_M quantization."),
            ("nvidia-pro", "NVIDIA Pro (nvidia-pro)", "Maximum performance for RTX 5080-5090. Full precision, fast inference."),
            ("amd", "AMD ROCm (amd)", "ROCm backend for AMD GPUs. Good performance with vLLM."),
        ]
        with Vertical(id="gpu-container"):
            yield Static("GPU Variant Selection", id="title")
            yield Static(f"Detected GPU: [#00BCD4]{self.gpu_model}[/]", id="subtitle")
            yield Static(f"Recommended: [#FF69B4]{self.recommended}[/]", id="dim-text")
            yield Static("", id="variant-info")
            with Vertical(id="variant-list"):
                for val, name, desc in variants:
                    with Vertical(classes="variant-card"):
                        yield Static(f"[bold #FF69B4]{name}[/]", id=f"vname-{val}")
                        yield Static(desc, id=f"vdesc-{val}")
                        yield Button(f"Select {name}", id=f"select-{val}")
            yield Static("", id="variant-info")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        for val in ["nvidia-std", "nvidia-pro", "amd"]:
            if event.button.id == f"select-{val}":
                self.app.data["gpu_variant"] = val
                self.app.push_screen(DiskSelectionScreen())


class DiskSelectionScreen(Screen):
    CSS = SHARED_CSS + """
    #disk-container {
        padding: 1 2;
        height: 100%;
    }
    #disk-list {
        margin: 1 0;
        min-height: 10;
    }
    #warning-box {
        background: #0a0a0a;
        border: solid #FF4444;
        padding: 1;
        margin: 1 0;
    }
    #confirm-box {
        padding: 1 0;
    }
    """

    def __init__(self):
        super().__init__()
        self.disks = detect_disks()
        self.selected_disk = None

    def compose(self) -> ComposeResult:
        with Vertical(id="disk-container"):
            yield Static("Disk Selection", id="title")
            yield Static("Select the target disk for installation:", id="subtitle")
            with ListView(id="disk-list"):
                for d in self.disks:
                    label = f"{d['name']:8} {d['size']:10} {d['model']}"
                    yield ListItem(Static(label, id=f"disk-item-{d['name']}"))
            with Vertical(id="warning-box"):
                yield Static("[bold #FF4444]⚠ WARNING: ALL DATA ON THE SELECTED DISK WILL BE DESTROYED[/]", id="warning-text")
                yield Static("", id="selected-disk-label")
            with Horizontal(classes="nav-bar"):
                yield Button("Back", id="back-btn")
                yield Button("Confirm & Continue", id="confirm-btn", variant="warning")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if item and item.children:
            label = item.children[0].renderable
            disk_name = label.strip().split()[0]
            self.selected_disk = disk_name
            disk = next((d for d in self.disks if d["name"] == disk_name), None)
            if disk:
                warning = f"[bold #FF4444]ALL DATA ON {disk['name']} ({disk['size']}) WILL BE DESTROYED[/]"
            else:
                warning = f"[bold #FF4444]ALL DATA ON {disk_name} WILL BE DESTROYED[/]"
            self.query_one("#warning-text", Static).update(warning)
            self.query_one("#selected-disk-label", Static).update(f"Selected: [#00BCD4]{label.strip()}[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back-btn":
            self.app.pop_screen()
        elif event.button.id == "confirm-btn":
            if not self.selected_disk:
                self.query_one("#warning-text", Static).update("[bold #FF4444]Please select a disk first![/]")
                return
            self.app.data["target_disk"] = self.selected_disk
            disk = next((d for d in self.disks if d["name"] == self.selected_disk), None)
            if disk:
                self.app.data["target_disk_size"] = disk["size"]
            self.app.push_screen(DualBootScreen())


class DualBootScreen(Screen):
    CSS = SHARED_CSS + """
    #dual-container {
        padding: 1 2;
        height: 100%;
    }
    #os-list {
        margin: 1 0;
    }
    #size-form {
        margin: 1 0;
        display: none;
    }
    #size-form.visible {
        display: block;
    }
    #status-text {
        padding: 1 0;
    }
    """

    def __init__(self):
        super().__init__()
        self.detected_oses = detect_os_installations()
        self.checkboxes = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="dual-container"):
            yield Static("Dual-Boot Configuration", id="title")
            yield Static("Select OS installations to keep for dual-boot:", id="subtitle")
            with Vertical(id="os-list"):
                if not self.detected_oses:
                    yield Static("[#666666]No additional OS installations detected.[/]")
                else:
                    for i, os_info in enumerate(self.detected_oses):
                        cb = Checkbox(f"{os_info['display_name']:12} ({os_info['label']})", id=f"os-cb-{i}", value=False)
                        self.checkboxes[i] = cb
                        yield cb
            with Vertical(id="size-form"):
                yield Static("Set partition sizes:", id="size-label")
                yield Input(placeholder="Holmium root size in GB (e.g. 100)", id="holmium-size")
                yield Static("[#666666]Secondary OS gets the remaining space[/]", id="remaining-hint")
            yield Static("", id="status-text")
            with Horizontal(classes="nav-bar"):
                yield Button("Back", id="back-btn")
                yield Button("Continue", variant="success", id="continue-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back-btn":
            self.app.pop_screen()
        elif event.button.id == "continue-btn":
            selected = []
            for i, os_info in enumerate(self.detected_oses):
                cb = self.checkboxes.get(i)
                if cb and cb.value:
                    selected.append(os_info["display_name"])
            self.app.data["dual_boot_oses"] = selected
            if not selected:
                self.query_one("#status-text", Static).update("[#4CAF50]Single-boot: Holmium OS will be the only OS[/]")
                self.query_one("#size-form", Vertical).remove_class("visible")
                self.app.data["secondary_partition_size"] = 0
            else:
                size_input = self.query_one("#holmium-size", Input)
                size_str = size_input.value.strip()
                try:
                    holmium_size_gb = int(size_str)
                    if holmium_size_gb < 20:
                        self.query_one("#status-text", Static).update("[#FF4444]Holmium root must be at least 20 GB[/]")
                        return
                    self.app.data["holmium_root_size"] = holmium_size_gb
                except ValueError:
                    self.query_one("#status-text", Static).update("[#FF4444]Enter a valid size in GB[/]")
                    return
                self.query_one("#status-text", Static).update(f"[#00BCD4]Keeping: {', '.join(selected)} — Holmium: {holmium_size_gb} GB[/]")
            self.app.push_screen(LicenseScreen())


class LicenseScreen(Screen):
    CSS = SHARED_CSS + """
    #license-container {
        padding: 1 2;
        height: 100%;
    }
    #license-form {
        margin: 1 0;
    }
    #status-box {
        padding: 1 0;
    }
    """

    def __init__(self):
        super().__init__()
        self.license_key = ""
        self.email = ""
        self.status = "pending"

    def compose(self) -> ComposeResult:
        with Vertical(id="license-container"):
            yield Static("Activate Holmium", id="title")
            yield Static("Enter your license key or start a 7-day trial.", id="subtitle")
            with Vertical(id="license-form"):
                yield Label("License Key (HOLM-XXXX-XXXX-XXXX):")
                yield Input(placeholder="HOLM-XXXX-XXXX-XXXX", id="license-input")
                yield Label("Email:")
                yield Input(placeholder="your@email.com", id="email-input")
            yield Static("", id="status-box")
            with Horizontal(classes="nav-bar"):
                yield Button("Verify Online", id="verify-btn")
                yield Button("Activate Later (7-day trial)", id="trial-btn")
                yield Button("Back", id="back-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back-btn":
            self.app.pop_screen()
            return

        license_input = self.query_one("#license-input", Input)
        email_input = self.query_one("#email-input", Input)
        status_box = self.query_one("#status-box", Static)

        if event.button.id == "trial-btn":
            self._activate_trial(status_box)
        elif event.button.id == "verify-btn":
            self.license_key = license_input.value.strip()
            self.email = email_input.value.strip()
            if not self.license_key or not self.email:
                status_box.update("[bold #FF4444]Please enter both license key and email.[/]")
                return
            if not re.match(r'^HOLM-(?:[A-Z0-9]{4}-){3,}[A-Z0-9]{4}$|^HOLM-DEV-[A-Z0-9-]+$', self.license_key):
                status_box.update("[bold #FF4444]Invalid license key format. Expected: HOLM-XXXX-XXXX-XXXX[/]")
                return
            self._verify_online(status_box)

    def _activate_trial(self, status_box: Static) -> None:
        expiry = datetime.now(timezone.utc) + timedelta(days=7)
        trial_data = {
            "license_key": "TRIAL",
            "email": "trial@holmium.local",
            "expiry": expiry.isoformat(),
            "signature": "trial",
            "machine_id": "trial",
            "activated_at": datetime.now(timezone.utc).isoformat(),
            "trial": True,
        }
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        LICENSE_PATH.write_text(json.dumps(trial_data, indent=2))
        LICENSE_PATH.chmod(0o600)
        self.app.data["license"] = trial_data
        self.app.data["license_status"] = "trial"
        status_box.update("[bold #4CAF50]✓ 7-day trial activated! Expires: " + expiry.strftime("%Y-%m-%d") + "[/]")
        self.app.push_screen(UserProfileScreen())

    def _verify_online(self, status_box: Static) -> None:
        status_box.update("[#666666]Verifying license online...[/]")
        self._do_verify()

    @work
    async def _do_verify(self) -> None:
        status_box = self.query_one("#status-box", Static)
        try:
            import urllib.request
            data = json.dumps({"license_key": self.license_key, "email": self.email}).encode()
            req = urllib.request.Request(
                "https://api.holmium.ai/api/license/activate",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=15))
            result = json.loads(resp.read().decode())
            if result.get("valid"):
                expiry = result.get("expiry", (datetime.now(timezone.utc) + timedelta(days=365)).isoformat())
                lic_data = {
                    "license_key": self.license_key,
                    "email": self.email,
                    "expiry": expiry,
                    "signature": result.get("signature", ""),
                    "machine_id": result.get("machine_id", ""),
                    "activated_at": datetime.now(timezone.utc).isoformat(),
                }
                CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
                LICENSE_PATH.write_text(json.dumps(lic_data, indent=2))
                LICENSE_PATH.chmod(0o600)
                self.app.data["license"] = lic_data
                self.app.data["license_status"] = "valid"
                status_box.update(f"[bold #4CAF50]✓ License valid! Expires: {expiry}[/]")
                self.app.push_screen(UserProfileScreen())
            else:
                msg = result.get("message", "License key invalid.")
                status_box.update(f"[bold #FF4444]✗ {msg}[/]")
        except Exception as e:
            status_box.update(f"[bold #FF4444]Verification failed: {e}. Check internet connection.[/]")


class UserProfileScreen(Screen):
    CSS = SHARED_CSS + """
    #profile-container {
        padding: 1 2;
        height: 100%;
    }
    #profile-form {
        margin: 1 0;
    }
    .question-label {
        color: #00BCD4;
        padding: 1 0 0 0;
    }
    .multi-select-container {
        background: #0a0a0a;
        border: solid #1a1a2e;
        padding: 1;
        margin: 0 0 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="profile-container"):
            yield Static("User Profile", id="title")
            yield Static("Tell us about yourself to personalize Holmium.", id="subtitle")
            with Vertical(id="profile-form", overflow="auto"):
                yield Label("What should I call you?", classes="question-label")
                yield Input(placeholder="Your name", id="name-input")

                yield Label("What do you mainly want to use me for?", classes="question-label")
                with Vertical(classes="multi-select-container", id="use-cases"):
                    yield Checkbox("Coding", id="uc-coding", value=True)
                    yield Checkbox("Research", id="uc-research")
                    yield Checkbox("AI Chat", id="uc-ai-chat")
                    yield Checkbox("Automation", id="uc-automation")
                    yield Checkbox("Media", id="uc-media")
                    yield Checkbox("Other", id="uc-other")

                yield Label("How technical are you?", classes="question-label")
                with RadioSet(id="tech-level"):
                    yield RadioButton("Beginner", id="tech-beginner")
                    yield RadioButton("Intermediate", id="tech-intermediate", value=True)
                    yield RadioButton("Advanced", id="tech-advanced")
                    yield RadioButton("Expert", id="tech-expert")

                yield Label("What's your primary goal?", classes="question-label")
                yield Input(placeholder="e.g. Build an AI assistant for my business", id="goal-input")

                yield Label("Preferred model style?", classes="question-label")
                with RadioSet(id="model-style"):
                    yield RadioButton("Concise & Fast", id="style-concise")
                    yield RadioButton("Balanced", id="style-balanced", value=True)
                    yield RadioButton("Detailed & Creative", id="style-creative")

                yield Label("Any topics to avoid?", classes="question-label")
                yield Input(placeholder="e.g. politics, religion (comma separated)", id="avoid-input")

                yield Label("Default timezone?", classes="question-label")
                yield Input(placeholder="Auto-detected, or type override", id="tz-input")

            with Horizontal(classes="nav-bar"):
                yield Button("Back", id="back-btn")
                yield Button("Continue", variant="success", id="continue-btn")

    def on_mount(self) -> None:
        tz = detect_timezone()
        self.query_one("#tz-input", Input).value = tz

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back-btn":
            self.app.pop_screen()
        elif event.button.id == "continue-btn":
            name = self.query_one("#name-input", Input).value.strip()
            if not name:
                name = "user"

            use_cases = []
            for uid in ["coding", "research", "ai-chat", "automation", "media", "other"]:
                cb = self.query_one(f"#uc-{uid}", Checkbox)
                if cb.value:
                    use_cases.append(uid.replace("-", " ").title())

            tech_level_widget = self.query_one("#tech-level", RadioSet)
            tech_map = {"tech-beginner": "Beginner", "tech-intermediate": "Intermediate", "tech-advanced": "Advanced", "tech-expert": "Expert"}
            tech_level = "Intermediate"
            for btn_id, label in tech_map.items():
                try:
                    rb = tech_level_widget.query_one(f"#{btn_id}", RadioButton)
                    if rb.value:
                        tech_level = label
                except Exception:
                    pass

            style_widget = self.query_one("#model-style", RadioSet)
            style_map = {"style-concise": "concise", "style-balanced": "balanced", "style-creative": "creative"}
            model_style = "balanced"
            for btn_id, label in style_map.items():
                try:
                    rb = style_widget.query_one(f"#{btn_id}", RadioButton)
                    if rb.value:
                        model_style = label
                except Exception:
                    pass

            goal = self.query_one("#goal-input", Input).value.strip() or "General AI use"
            avoid = self.query_one("#avoid-input", Input).value.strip()
            tz = self.query_one("#tz-input", Input).value.strip() or "UTC"

            self.app.data["user_name"] = name
            self.app.data["use_cases"] = use_cases
            self.app.data["tech_level"] = tech_level
            self.app.data["primary_goal"] = goal
            self.app.data["model_style"] = model_style
            self.app.data["topics_avoid"] = avoid
            self.app.data["timezone"] = tz

            self.app.push_screen(SummaryScreen())


class SummaryScreen(Screen):
    CSS = SHARED_CSS + """
    #summary-container {
        padding: 1 2;
        height: 100%;
    }
    #summary-table {
        margin: 1 0;
    }
    .summary-row {
        padding: 0 1;
        height: 3;
    }
    .summary-label {
        color: #00BCD4;
        width: 16;
    }
    .summary-value {
        color: #E0E0E0;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="summary-container"):
            yield Static("Installation Summary", id="title")
            yield Static("Review your selections before installing.", id="subtitle")
            with Vertical(id="summary-table"):
                yield self._row("GPU Variant", self.app.data.get("gpu_variant", "N/A"))
                yield self._row("Target Disk", f"{self.app.data.get('target_disk', 'N/A')} ({self.app.data.get('target_disk_size', '')})")
                dual = self.app.data.get("dual_boot_oses", [])
                dual_str = ", ".join(dual) if dual else "None (single-boot)"
                yield self._row("Dual-Boot", dual_str)
                lic_status = self.app.data.get("license_status", "none")
                yield self._row("License", lic_status)
                yield self._row("User Name", self.app.data.get("user_name", "N/A"))
                yield self._row("Primary Goal", self.app.data.get("primary_goal", "N/A"))
                yield self._row("Tech Level", self.app.data.get("tech_level", "N/A"))
                yield self._row("Model Style", self.app.data.get("model_style", "N/A"))
                yield self._row("Timezone", self.app.data.get("timezone", "UTC"))
            with Horizontal(classes="nav-bar"):
                yield Button("Back", id="back-btn")
                yield Button("INSTALL", variant="warning", id="install-btn")

    def _row(self, label: str, value: str) -> Static:
        return Static(f"[#00BCD4]{label:<16}[/] [#E0E0E0]{value}[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back-btn":
            self.app.pop_screen()
        elif event.button.id == "install-btn":
            self.app.push_screen(InstallScreen())


class InstallScreen(Screen):
    CSS = SHARED_CSS + """
    #install-container {
        padding: 1 2;
        height: 100%;
    }
    #progress-bar {
        margin: 1 0;
    }
    #step-list {
        margin: 1 0;
    }
    .step-item {
        padding: 0 1;
        height: 3;
    }
    .step-done {
        color: #4CAF50;
    }
    .step-active {
        color: #00BCD4;
    }
    .step-pending {
        color: #444444;
    }
    #complete-text {
        text-style: bold;
        color: #4CAF50;
        padding: 1 0;
    }
    """

    STEPS = [
        "Partitioning disk...",
        "Formatting filesystem...",
        "Installing base system...",
        "Configuring GRUB...",
        "Installing Holmium packages...",
        "Configuring dual-boot...",
        "Setting up GPU drivers...",
        "Writing license...",
        "Finalizing...",
    ]

    def __init__(self):
        super().__init__()
        self.current_step = 0
        self.step_widgets = []

    def compose(self) -> ComposeResult:
        with Vertical(id="install-container"):
            yield Static("Installing Holmium OS", id="title")
            yield ProgressBar(total=len(self.STEPS), id="progress-bar")
            with Vertical(id="step-list"):
                for i, step in enumerate(self.STEPS):
                    w = Static(f"  ○ {step}", id=f"step-{i}")
                    self.step_widgets.append(w)
                    yield w
            yield Static("", id="complete-text")
            with Horizontal(classes="nav-bar"):
                yield Button("Reboot", variant="success", id="reboot-btn", disabled=True)

    def on_mount(self) -> None:
        self._run_installation()

    @work
    async def _run_installation(self) -> None:
        progress = self.query_one("#progress-bar", ProgressBar)
        for i, step_name in enumerate(self.STEPS):
            self.current_step = i
            step_w = self.query_one(f"#step-{i}", Static)
            step_w.update(f"[#00BCD4]  ◇ {step_name}[/]")
            progress.update(progress=i)

            if i == 0:
                await self._step_partition()
            elif i == 1:
                await self._step_format()
            elif i == 2:
                await self._step_base_system()
            elif i == 3:
                await self._step_grub()
            elif i == 4:
                await self._step_holmium_packages()
            elif i == 5:
                await self._step_dual_boot()
            elif i == 6:
                await self._step_gpu_drivers()
            elif i == 7:
                await self._step_write_license()
            elif i == 8:
                await self._step_finalize()

            step_w.update(f"[#4CAF50]  ✓ {step_name}[/]")

        progress.update(progress=len(self.STEPS))
        self.query_one("#complete-text", Static).update("[bold #4CAF50]✓ Installation Complete![/]")
        self.query_one("#reboot-btn", Button).disabled = False

    async def _step_partition(self) -> None:
        disk = self.app.data.get("target_disk", "")
        if disk:
            run_cmd(["sgdisk", "-o", f"/dev/{disk}"], check=False)
            run_cmd(["sgdisk", "-n", "1:0:+512M", "-t", "1:ef00", f"/dev/{disk}"], check=False)
            holmium_size = self.app.data.get("holmium_root_size", 0)
            if holmium_size > 0:
                holmium_sectors = holmium_size * 1024 * 2  # approx sectors per GB
                run_cmd(["sgdisk", "-n", f"2:0:+{holmium_sectors}", "-t", "2:8300", f"/dev/{disk}"], check=False)
                run_cmd(["sgdisk", "-n", "3:0:0", "-t", "3:8300", f"/dev/{disk}"], check=False)
                self.app.data["has_secondary_partition"] = True
            else:
                run_cmd(["sgdisk", "-n", "2:0:0", "-t", "2:8300", f"/dev/{disk}"], check=False)
                self.app.data["has_secondary_partition"] = False
            run_cmd(["partprobe", f"/dev/{disk}"], check=False)
        await asyncio.sleep(2)

    async def _step_format(self) -> None:
        disk = self.app.data.get("target_disk", "")
        if disk:
            run_cmd(["mkfs.fat", "-F", "32", f"/dev/{disk}1"], check=False)
            run_cmd(["mkfs.btrfs", "-f", f"/dev/{disk}2"], check=False)
        await asyncio.sleep(1)

    async def _step_base_system(self) -> None:
        disk = self.app.data.get("target_disk", "")
        if disk:
            run_cmd(["mount", f"/dev/{disk}2", "/mnt"], check=False)
            run_cmd(["mount", f"/dev/{disk}1", "/mnt/boot"], check=False)
            run_cmd(["cp", "-a", "/run/archiso/bootmnt/", "/mnt/"], check=False)
        await asyncio.sleep(3)

    async def _step_grub(self) -> None:
        run_cmd(["arch-chroot", "/mnt", "grub-install", "--target=x86_64-efi", "--efi-directory=/boot", "--bootloader-id=Holmium"], check=False)
        dual_boot = self.app.data.get("dual_boot_oses", [])
        if dual_boot:
            run_cmd(["arch-chroot", "/mnt", "grub-mkconfig", "-o", "/boot/grub/grub.cfg"], check=False)
        await asyncio.sleep(2)

    async def _step_holmium_packages(self) -> None:
        run_cmd(["cp", "-a", "/holmium/", "/mnt/opt/holmium"], check=False)
        run_cmd(["cp", "-a", "/etc/holmium/", "/mnt/etc/holmium"], check=False)
        await asyncio.sleep(3)

    async def _step_dual_boot(self) -> None:
        dual_boot = self.app.data.get("dual_boot_oses", [])
        if dual_boot:
            run_cmd(["arch-chroot", "/mnt", "os-prober"], check=False)
            run_cmd(["arch-chroot", "/mnt", "grub-mkconfig", "-o", "/boot/grub/grub.cfg"], check=False)
        await asyncio.sleep(1)

    async def _step_gpu_drivers(self) -> None:
        variant = self.app.data.get("gpu_variant", "nvidia-std")
        if variant == "nvidia-std":
            run_cmd(["arch-chroot", "/mnt", "nvidia-installer", "--no-kernel-modules"], check=False)
        elif variant == "nvidia-pro":
            run_cmd(["arch-chroot", "/mnt", "nvidia-installer", "--no-kernel-modules", "--no-dkms"], check=False)
        elif variant == "amd":
            run_cmd(["arch-chroot", "/mnt", "rocminstall"], check=False)
        await asyncio.sleep(2)

    async def _step_write_license(self) -> None:
        lic = self.app.data.get("license", {})
        if lic:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            LICENSE_PATH.write_text(json.dumps(lic, indent=2))
            try:
                LICENSE_PATH.chmod(0o600)
            except Exception:
                pass
        await asyncio.sleep(0.5)

    async def _step_finalize(self) -> None:
        config = {
            "user_name": self.app.data.get("user_name", "user"),
            "gpu_variant": self.app.data.get("gpu_variant", "nvidia-std"),
            "target_disk": self.app.data.get("target_disk", ""),
            "dual_boot_oses": self.app.data.get("dual_boot_oses", []),
            "has_secondary_partition": self.app.data.get("has_secondary_partition", False),
            "secondary_partition": f"/dev/{self.app.data.get('target_disk', '')}3" if self.app.data.get("has_secondary_partition") else "",
            "timezone": self.app.data.get("timezone", "UTC"),
            "tech_level": self.app.data.get("tech_level", "Intermediate"),
            "model_style": self.app.data.get("model_style", "balanced"),
            "primary_goal": self.app.data.get("primary_goal", ""),
            "use_cases": self.app.data.get("use_cases", []),
            "topics_avoid": self.app.data.get("topics_avoid", ""),
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "vllm_socket": "/run/holmium/vllm.sock",
            "backend_socket": "/run/holmium/backend.sock",
            "mode_default": "work",
            "mode_temps": {
                "think": [0.1, 0.85],
                "work": [0.5, 0.9],
                "image": [0.8, 0.95],
            },
        }
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(config, indent=2))
        CONFIG_PATH.chmod(0o600)
        run_cmd(["umount", "-R", "/mnt"], check=False)
        await asyncio.sleep(1)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "reboot-btn":
            run_cmd(["reboot"], check=False)


# ── First Boot Screens ─────────────────────────────────────────────

class FirstBootWelcomeScreen(Screen):
    CSS = SHARED_CSS + """
    #welcome-container {
        align: center middle;
        height: 100%;
    }
    #logo-text {
        text-style: bold;
        color: #00BCD4;
    }
    #welcome-title {
        text-style: bold;
        color: #FF69B4;
        padding: 0 0 1 0;
    }
    #desc-text {
        color: #E0E0E0;
    }
    #prompt-text {
        color: #666666;
        padding: 2 0 0 0;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="welcome-container"):
            yield Static(Text(HOLMIUM_LOGO, style=Style(color=COLOR_CYAN, bold=True)), id="logo-text")
            yield Static("Welcome to Holmium OS!", id="welcome-title")
            yield Static("Your single-purpose AI appliance is ready to configure.", id="desc-text")
            yield Static("Let's get you set up.", id="desc-text")
            yield Static("Press Enter to continue...", id="prompt-text")

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.app.push_screen(FirstBootLicenseScreen())


class FirstBootLicenseScreen(Screen):
    CSS = SHARED_CSS + """
    #license-container {
        padding: 1 2;
        height: 100%;
    }
    #status-box {
        padding: 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="license-container"):
            yield Static("License Verification", id="title")
            yield Static("Checking your Holmium license...", id="subtitle")
            yield Static("", id="status-box")
            with Horizontal(classes="nav-bar"):
                yield Button("Re-check", id="recheck-btn")
                yield Button("Continue", variant="success", id="continue-btn")

    def on_mount(self) -> None:
        self._check_license()

    @work
    async def _check_license(self) -> None:
        status_box = self.query_one("#status-box", Static)
        status_box.update("[#666666]Verifying license...[/]")
        await asyncio.sleep(0.5)

        try:
            lic_data = json.loads(LICENSE_PATH.read_text()) if LICENSE_PATH.exists() else None
        except (json.JSONDecodeError, OSError):
            lic_data = None

        if lic_data and lic_data.get("signature") and lic_data.get("signature") != "trial":
            self.app.data["license_status"] = "valid"
            status_box.update("[bold #4CAF50]✓ License is valid![/]")
        elif lic_data and lic_data.get("trial"):
            self.app.data["license_status"] = "trial"
            expiry = lic_data.get("expiry", "unknown")
            status_box.update(f"[bold #FF69B4]⚠ Trial mode — expires: {expiry}[/]")
        else:
            self.app.data["license_status"] = "none"
            status_box.update("[bold #FF4444]✗ No valid license found. Please activate Holmium.[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "recheck-btn":
            self._check_license()
        elif event.button.id == "continue-btn":
            self.app.push_screen(FirstBootUserScreen())


class FirstBootUserScreen(Screen):
    CSS = SHARED_CSS + """
    #profile-container {
        padding: 1 2;
        height: 100%;
    }
    #profile-form {
        margin: 1 0;
    }
    .question-label {
        color: #00BCD4;
        padding: 1 0 0 0;
    }
    .multi-select-container {
        background: #0a0a0a;
        border: solid #1a1a2e;
        padding: 1;
        margin: 0 0 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="profile-container"):
            yield Static("Configure Holmium", id="title")
            yield Static("Tell us about yourself.", id="subtitle")
            with Vertical(id="profile-form", overflow="auto"):
                yield Label("What should I call you?", classes="question-label")
                yield Input(placeholder="Your name", id="name-input")

                yield Label("What do you mainly want to use me for?", classes="question-label")
                with Vertical(classes="multi-select-container", id="use-cases"):
                    yield Checkbox("Coding", id="uc-coding", value=True)
                    yield Checkbox("Research", id="uc-research")
                    yield Checkbox("AI Chat", id="uc-ai-chat")
                    yield Checkbox("Automation", id="uc-automation")
                    yield Checkbox("Media", id="uc-media")
                    yield Checkbox("Other", id="uc-other")

                yield Label("How technical are you?", classes="question-label")
                with RadioSet(id="tech-level"):
                    yield RadioButton("Beginner", id="tech-beginner")
                    yield RadioButton("Intermediate", id="tech-intermediate", value=True)
                    yield RadioButton("Advanced", id="tech-advanced")
                    yield RadioButton("Expert", id="tech-expert")

                yield Label("What's your primary goal?", classes="question-label")
                yield Input(placeholder="e.g. Build an AI assistant for my business", id="goal-input")

                yield Label("Preferred model style?", classes="question-label")
                with RadioSet(id="model-style"):
                    yield RadioButton("Concise & Fast", id="style-concise")
                    yield RadioButton("Balanced", id="style-balanced", value=True)
                    yield RadioButton("Detailed & Creative", id="style-creative")

                yield Label("Default timezone?", classes="question-label")
                yield Input(placeholder="Auto-detected, or type override", id="tz-input")

            with Horizontal(classes="nav-bar"):
                yield Button("Back", id="back-btn")
                yield Button("Continue", variant="success", id="continue-btn")

    def on_mount(self) -> None:
        tz = detect_timezone()
        self.query_one("#tz-input", Input).value = tz

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back-btn":
            self.app.pop_screen()
        elif event.button.id == "continue-btn":
            name = self.query_one("#name-input", Input).value.strip() or "user"

            use_cases = []
            for uid in ["coding", "research", "ai-chat", "automation", "media", "other"]:
                cb = self.query_one(f"#uc-{uid}", Checkbox)
                if cb.value:
                    use_cases.append(uid.replace("-", " ").title())

            tech_level_widget = self.query_one("#tech-level", RadioSet)
            tech_map = {"tech-beginner": "Beginner", "tech-intermediate": "Intermediate", "tech-advanced": "Advanced", "tech-expert": "Expert"}
            tech_level = "Intermediate"
            for btn_id, label in tech_map.items():
                try:
                    rb = tech_level_widget.query_one(f"#{btn_id}", RadioButton)
                    if rb.value:
                        tech_level = label
                except Exception:
                    pass

            style_widget = self.query_one("#model-style", RadioSet)
            style_map = {"style-concise": "concise", "style-balanced": "balanced", "style-creative": "creative"}
            model_style = "balanced"
            for btn_id, label in style_map.items():
                try:
                    rb = style_widget.query_one(f"#{btn_id}", RadioButton)
                    if rb.value:
                        model_style = label
                except Exception:
                    pass

            goal = self.query_one("#goal-input", Input).value.strip() or "General AI use"
            tz = self.query_one("#tz-input", Input).value.strip() or "UTC"

            self.app.data["user_name"] = name
            self.app.data["use_cases"] = use_cases
            self.app.data["tech_level"] = tech_level
            self.app.data["primary_goal"] = goal
            self.app.data["model_style"] = model_style
            self.app.data["timezone"] = tz
            self.app.push_screen(FirstBootGpuScreen())


class FirstBootGpuScreen(Screen):
    CSS = SHARED_CSS + """
    #gpu-container {
        padding: 1 2;
        height: 100%;
    }
    #gpu-info {
        padding: 1 0;
    }
    .variant-card {
        background: #0a0a0a;
        border: solid #1a1a2e;
        padding: 1;
        margin: 0 0 1 0;
    }
    """

    def __init__(self):
        super().__init__()
        self.gpu_model = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="gpu-container"):
            yield Static("GPU Configuration", id="title")
            yield Static("Detecting GPU for vLLM backend...", id="subtitle")
            yield Static("", id="gpu-info")
            with Vertical(id="variant-list"):
                for val, name in [("nvidia-std", "NVIDIA Standard"), ("nvidia-pro", "NVIDIA Pro"), ("amd", "AMD ROCm")]:
                    with Vertical(classes="variant-card"):
                        yield Static(f"[bold #FF69B4]{name}[/]", id=f"vname-{val}")
                        yield Button(f"Select {name}", id=f"select-{val}")
            with Horizontal(classes="nav-bar"):
                yield Button("Continue", variant="success", id="continue-btn")

    def on_mount(self) -> None:
        self._detect()

    @work
    async def _detect(self) -> None:
        self.gpu_model = await asyncio.to_thread(detect_gpu)
        variant = recommend_gpu_variant(self.gpu_model)
        self.app.data["gpu_variant"] = variant
        info = self.query_one("#gpu-info", Static)
        info.update(f"Detected GPU: [#00BCD4]{self.gpu_model}[/]\nRecommended: [#FF69B4]{variant}[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        for val in ["nvidia-std", "nvidia-pro", "amd"]:
            if event.button.id == f"select-{val}":
                self.app.data["gpu_variant"] = val
        if event.button.id == "continue-btn" or event.button.id.startswith("select-"):
            self.app.push_screen(FirstBootDualBootScreen())


class FirstBootDualBootScreen(Screen):
    CSS = SHARED_CSS + """
    #dual-container {
        padding: 1 2;
        height: 100%;
    }
    #os-list {
        margin: 1 0;
    }
    """

    def __init__(self):
        super().__init__()
        self.detected_oses = detect_os_installations()
        self.checkboxes = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="dual-container"):
            yield Static("Dual-Boot Setup", id="title")
            yield Static("Other OS partitions detected. Configure boot entries:", id="subtitle")
            with Vertical(id="os-list"):
                if not self.detected_oses:
                    yield Static("[#666666]No other OS installations detected.[/]")
                else:
                    for i, os_info in enumerate(self.detected_oses):
                        cb = Checkbox(f"{os_info['display_name']:12} ({os_info['label']})", id=f"fb-os-cb-{i}", value=True)
                        self.checkboxes[i] = cb
                        yield cb
            yield Static("", id="status-text")
            with Horizontal(classes="nav-bar"):
                yield Button("Continue", variant="success", id="continue-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue-btn":
            selected = []
            for i, os_info in enumerate(self.detected_oses):
                cb = self.checkboxes.get(i)
                if cb and cb.value:
                    selected.append(os_info["display_name"])
            self.app.data["dual_boot_oses"] = selected
            self.app.push_screen(FirstBootNetworkScreen())


class FirstBootNetworkScreen(Screen):
    CSS = SHARED_CSS + """
    #network-container {
        padding: 1 2;
        height: 100%;
    }
    #network-form {
        margin: 1 0;
    }
    #wifi-list {
        margin: 1 0;
        min-height: 8;
    }
    """

    def __init__(self):
        super().__init__()
        self.wifi_networks = []

    def compose(self) -> ComposeResult:
        with Vertical(id="network-container"):
            yield Static("Network Setup", id="title")
            yield Static("Configure network connectivity.", id="subtitle")
            with Vertical(id="network-form"):
                yield Label("WiFi SSID:")
                yield Input(placeholder="Enter SSID or leave blank for Ethernet", id="ssid-input")
                yield Label("WiFi Password:")
                yield Input(placeholder="Password", id="password-input", password=True)
            yield Static("[#666666]Scanning for WiFi networks...[/]", id="scan-text")
            with ListView(id="wifi-list"):
                pass
            with Horizontal(classes="nav-bar"):
                yield Button("Skip", id="skip-btn")
                yield Button("Continue", variant="success", id="continue-btn")

    def on_mount(self) -> None:
        self._scan_wifi()

    @work
    async def _scan_wifi(self) -> None:
        scan_text = self.query_one("#scan-text", Static)
        scan_text.update("[#666666]Scanning...[/]")
        result = await asyncio.to_thread(run_cmd, ["nmcli", "-t", "-f", "SSID,SIGNAL", "device", "wifi", "list"], check=False)
        if result and result.returncode == 0:
            networks = []
            for line in result.stdout.strip().splitlines():
                if ":" in line:
                    parts = line.split(":", 1)
                    ssid = parts[0].strip()
                    if ssid:
                        networks.append(ssid)
            self.wifi_networks = networks[:20]
            wifi_list = self.query_one("#wifi-list", ListView)
            wifi_list.clear()
            for ssid in self.wifi_networks:
                wifi_list.mount(ListItem(Static(ssid)))
            scan_text.update(f"[#4CAF50]Found {len(self.wifi_networks)} networks. Select one or type SSID manually.[/]")
        else:
            scan_text.update("[#666666]WiFi scan unavailable. Using Ethernet or manual entry.[/]")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item and event.item.children:
            ssid = str(event.item.children[0].renderable).strip()
            self.query_one("#ssid-input", Input).value = ssid

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue-btn" or event.button.id == "skip-btn":
            ssid = self.query_one("#ssid-input", Input).value.strip()
            password = self.query_one("#password-input", Input).value.strip()
            self.app.data["wifi_ssid"] = ssid
            self.app.data["wifi_password"] = password
            self.app.push_screen(FirstBootSummaryScreen())


class FirstBootSummaryScreen(Screen):
    CSS = SHARED_CSS + """
    #summary-container {
        padding: 1 2;
        height: 100%;
    }
    #summary-table {
        margin: 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="summary-container"):
            yield Static("Summary & Finish", id="title")
            yield Static("Review your configuration:", id="subtitle")
            with Vertical(id="summary-table"):
                yield Static(f"[#00BCD4]User Name:      [/][#E0E0E0]{self.app.data.get('user_name', 'N/A')}[/]")
                yield Static(f"[#00BCD4]GPU Variant:    [/][#E0E0E0]{self.app.data.get('gpu_variant', 'N/A')}[/]")
                yield Static(f"[#00BCD4]Primary Goal:   [/][#E0E0E0]{self.app.data.get('primary_goal', 'N/A')}[/]")
                yield Static(f"[#00BCD4]Tech Level:     [/][#E0E0E0]{self.app.data.get('tech_level', 'N/A')}[/]")
                yield Static(f"[#00BCD4]Model Style:    [/][#E0E0E0]{self.app.data.get('model_style', 'N/A')}[/]")
                yield Static(f"[#00BCD4]Timezone:       [/][#E0E0E0]{self.app.data.get('timezone', 'UTC')}[/]")
                dual = self.app.data.get("dual_boot_oses", [])
                dual_str = ", ".join(dual) if dual else "None"
                yield Static(f"[#00BCD4]Dual-Boot:      [/][#E0E0E0]{dual_str}[/]")
                wifi = self.app.data.get("wifi_ssid", "") or "Ethernet"
                yield Static(f"[#00BCD4]Network:        [/][#E0E0E0]{wifi}[/]")
            with Horizontal(classes="nav-bar"):
                yield Button("Back", id="back-btn")
                yield Button("Finish", variant="success", id="finish-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back-btn":
            self.app.pop_screen()
        elif event.button.id == "finish-btn":
            self._apply_config(event)

    def _apply_config(self, event) -> None:
        try:
            config = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
        except (FileNotFoundError, json.JSONDecodeError):
            config = {}

        config.update({
            "user_name": self.app.data.get("user_name", "user"),
            "gpu_variant": self.app.data.get("gpu_variant", "nvidia-std"),
            "dual_boot_oses": self.app.data.get("dual_boot_oses", []),
            "timezone": self.app.data.get("timezone", "UTC"),
            "tech_level": self.app.data.get("tech_level", "Intermediate"),
            "model_style": self.app.data.get("model_style", "balanced"),
            "primary_goal": self.app.data.get("primary_goal", ""),
            "use_cases": self.app.data.get("use_cases", []),
            "topics_avoid": self.app.data.get("topics_avoid", ""),
            "wifi_ssid": self.app.data.get("wifi_ssid", ""),
            "wifi_password": self.app.data.get("wifi_password", ""),
        })

        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(config, indent=2))
        CONFIG_PATH.chmod(0o600)

        if FIRST_RUN_FLAG.exists():
            try:
                FIRST_RUN_FLAG.unlink()
            except OSError:
                pass

        ssid = self.app.data.get("wifi_ssid", "")
        password = self.app.data.get("wifi_password", "")
        if ssid and password:
            run_cmd(["nmcli", "device", "wifi", "connect", ssid, "password", password], check=False)

        self.app.push_screen(FirstBootCompleteScreen())


class FirstBootCompleteScreen(Screen):
    CSS = SHARED_CSS + """
    #complete-container {
        align: center middle;
        height: 100%;
    }
    #complete-title {
        text-style: bold;
        color: #4CAF50;
        padding: 1 0;
    }
    #complete-msg {
        color: #E0E0E0;
    }
    #prompt-text {
        color: #666666;
        padding: 2 0 0 0;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="complete-container"):
            yield Static(Text(HOLMIUM_LOGO, style=Style(color=COLOR_CYAN, bold=True)), id="logo-text")
            yield Static("✓ Setup Complete!", id="complete-title")
            yield Static(f"Welcome, {self.app.data.get('user_name', 'user')}!", id="complete-msg")
            yield Static("Holmium OS is ready. The TUI is your interface to the system.", id="complete-msg")
            yield Static("Press Enter to launch Holmium.", id="prompt-text")

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.app.exit()


# ── App ────────────────────────────────────────────────────────────

class HolmiumInstaller(App):
    CSS = SHARED_CSS

    SCREENS = {
        "welcome": WelcomeScreen(),
        "hardware": HardwareDetectionScreen,
        "gpu_variant": GpuVariantScreen,
        "disk_selection": DiskSelectionScreen,
        "dual_boot": DualBootScreen,
        "license": LicenseScreen,
        "user_profile": UserProfileScreen,
        "summary": SummaryScreen,
        "install": InstallScreen,
        "first_boot_welcome": FirstBootWelcomeScreen,
        "first_boot_license": FirstBootLicenseScreen,
        "first_boot_user": FirstBootUserScreen,
        "first_boot_gpu": FirstBootGpuScreen,
        "first_boot_dual": FirstBootDualBootScreen,
        "first_boot_network": FirstBootNetworkScreen,
        "first_boot_summary": FirstBootSummaryScreen,
        "first_boot_complete": FirstBootCompleteScreen,
    }

    def __init__(self):
        super().__init__()
        self.data: dict = {}

    def on_mount(self) -> None:
        self.push_screen("welcome")


def main():
    app = HolmiumInstaller()
    app.run()


if __name__ == "__main__":
    main()
