<div align="center">
  <img width="120" height="120" alt="Holmium" src="https://github.com/user-attachments/assets/0ba6f6c4-43b7-4099-81b9-4294c1a13076" />
  <h1 align="center">Holmium</h1>
  <p align="center">Your local AI. Anywhere, anytime.</p>
  <p align="center">
    <a href="#features">Features</a> •
    <a href="#quick-start">Quick Start</a> •
    <a href="#variants">Variants</a> •
    <a href="#dual-boot">Dual-Boot</a> •
    <a href="#apps">Apps</a> •
    <a href="#install-manager">Install Manager</a> •
    <a href="#pricing">Pricing</a>
  </p>
</div>

---

Holmium is a **privacy-first, dedicated AI operating system** that turns a PC into your own
personal AI assistant — accessible from every device you own. Install the ISO on a machine
with a capable GPU, and you get a fully autonomous AI that runs locally, has zero cloud
dependencies, and is reachable from Windows, macOS, Linux, and Android.

No data leaves your home. No subscriptions to cloud APIs. No telemetry. Just your hardware,
your model, your assistant.

---

## Features

- **Local AI inference** — Run LLMs on your own GPU via vLLM. No internet required after setup.
- **File & NAS system** — Holmium exposes its entire disk as a network drive. Send and receive
  files from any device, like your own private Google Drive.
- **Code generation** — Generate, review, debug, and refactor code in any language.
- **Web research** — Search the web, fetch pages, scrape Wikipedia, Reddit, YouTube transcripts, news.
- **Email** — Fetch, read, search, send, reply, and manage your inbox.
- **Image & video generation** — Generate images via FLUX.1. Analyze images with vision models.
- **Stock analysis** — Real-time prices, portfolio tracking, history, suggestions.
- **System automation** — Run shell commands, manage processes, schedule tasks, set up monitors.
- **GitHub & Git integration** — Manage repos, issues, PRs, commits, CI/CD workflows.
- **Contacts, notes, todos** — Built-in personal management.
- **Encrypted vault** — Store secrets securely, accessible only by Holmium.
- **Clipboard sync** — Share clipboard across all your devices.
- **Remote device control** — SSH, file transfer, process management on connected devices.
- **Deep-think mode** — Extended reasoning for complex problems.
- **Voice** — Text-to-speech and speech-to-text (Whisper).
- **Image examination** — Upload images and ask questions about them.
- **Proactive monitoring** — Holmium watches your system and alerts you to issues.

---

## Quick Start

### 1. Download an ISO

Choose the variant that matches your GPU:

| Variant | GPU | Kernel | Backend |
|---------|-----|--------|---------|
| **NVIDIA Standard** | RTX 5060 — RTX 5070 | NVIDIA-optimized | vLLM CUDA |
| **NVIDIA Pro** | RTX 5080 — RTX 5090 | NVIDIA-optimized, max perf | vLLM CUDA |
| **AMD** | RX 9060 XT — RX 9070 XT | AMD-optimized | vLLM ROCm |

All variants require **16 GB RAM** minimum and **512 GB storage**.

### 2. Write to USB
 You can use any tool: Rufus, Balena-Etcher, etc.

### 3. Boot & Install

Boot from the USB. The **Holmium Install Manager** launches automatically — a full TUI that
guides you through:

1. **Hardware detection** — GPU, disk, RAM, CPU detected automatically
2. **Variant selection** — Picks the right GPU profile or lets you choose
3. **Disk setup** — Select target disk (with clear warnings)
4. **Dual-boot** — Detects existing OS installations, pick which to keep
5. **License activation** — Enter your license key or start a trial
6. **User profile** — Tell Holmium about yourself so it adapts to you
7. **Install** — Partitions, formats, installs, configures GRUB, sets up GPU drivers

### 4. First Boot

After installation, Holmium boots into the **First-Boot Wizard** where you:

- Verify your license
- Set your name, goals, and preferences
- Connect to WiFi / Ethernet
- Configure dual-boot GRUB entries
- Start services

Then Holmium's TUI appears on the display. You can start talking immediately.

---

## Dual-Boot

Holmium can coexist with another Linux distribution. During installation, the Install Manager
scans all partitions and detects existing OSes. Check the ones you want to keep, and Holmium
configures GRUB to chain-load them.

**Supported secondary OSes:**

| OS | Detection | Boot Method |
|----|-----------|-------------|
| Debian | Automatic | GRUB chain-load |
| KDE Neon | Automatic | GRUB chain-load |
| Ubuntu | Automatic | GRUB chain-load |
| Fedora | Automatic | GRUB chain-load |
| Nobara | Automatic | GRUB chain-load |
| CachyOS | Automatic | GRUB chain-load |

It also detects any other Linux installation with ext4/btrfs on a separate partition.

---

## Apps

Holmium is accessible from every major platform:

### macOS (GUI App)

A native macOS windowed application:
- **Chat tab** — Message history, text input, send, file attachments, typing indicator
- **Dashboard tab** — Live system status: GPU temp, RAM, disk, uptime, quick actions (Screenshot, Clipboard Sync, Open TUI)
- **Settings tab** — Server address, port, auth token, auto-connect, clipboard sync, notifications, test connection
- Connection status indicator (green/yellow/red) in the status bar
- Auto-reconnect with backoff

### Windows (GUI App)

A native WPF windowed application:
- **Chat tab** — Message list with bubble styling, text input, send button, connection status bar
- **Dashboard tab** — Status cards (GPU, RAM, Disk, Uptime), quick action buttons (Screenshot, Clipboard Sync, Open in Browser)
- **Settings tab** — Server address, port, auth token, auto-connect, clipboard sync, notifications, start on boot, test connection
- Connection state: Connected / Disconnected / Connecting / Error with colored indicator
- Auto-reconnect with exponential backoff

### Android (GUI App)

A Material Design 3 native Android application:
- **Chat tab** — Real-time messaging with Holmium
- **Devices tab** — Connected device management
- **Settings tab** — Server configuration, theme (Light/Dark/System), clipboard sync, notifications, TTS, test connection
- Connection status indicator with dynamic colors
- Bottom navigation with three tabs

### Linux (TUI + CLI)

- Full TUI (Textual) runs on the Holmium PC display (tty1) — the primary interface
- CLI commands available via `holmium` tool for scripting and automation
- WebSocket connection to the backend for real-time interaction
- Multiple modes: Work, Think, Image, Help

---

## Install Manager

The Holmium Install Manager is a full TUI application that replaces traditional installer scripts.
It runs on the live ISO environment and handles the entire installation process.

After booting from USB, a TUI install manager will open.

The manager walks through:

1. **Welcome** — Logo, version, intro
2. **Hardware Detection** — Scans GPU, disks, RAM, CPU, existing OSes via `lspci`, `lsblk`, `/proc`
3. **GPU Variant** — Auto-recommends variant based on detected GPU
4. **Disk Selection** — Lists all disks with size, model, type; destructive warning
5. **Dual-Boot** — Checkboxes for each detected OS
6. **License** — Enter HOLM-XXXX-XXXX-XXXX key, verify online, or 7-day trial
7. **User Profile** — 7 questions: name, use case, technical level, goal, style, topics, timezone
8. **Summary** — Full config review with Install / Back
9. **Install** — 9-step progress: partition, format, base, GRUB, packages, dual-boot, GPU, license, finalize
10. **Complete** — Reboot prompt

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Holmium OS                         │
│  ┌──────────────────────────────────────────────┐   │
│  │  TUI (Textual) — Primary interface on tty1   │   │
│  └──────────────────┬───────────────────────────┘   │
│                     │ WebSocket                     │
│  ┌──────────────────▼───────────────────────────┐   │
│  │  FastAPI Backend                             │   │
│  │  ┌──────┬──────┬──────┬──────┬──────────┐   │   │
│  │  │Tools │Memory│Modes │Config│ License  │   │   │
│  │  ├──────┼──────┼──────┼──────┼──────────┤   │   │
│  │  │Auth  │Search│STT   │TTS   │Scheduler │   │   │
│  │  └──────┴──────┴──────┴──────┴──────────┘   │   │
│  └──────────────────┬───────────────────────────┘   │
│                     │ HTTP                           │
│  ┌──────────────────▼───────────────────────────┐   │
│  │  vLLM Inference Server                       │   │
│  │  (CUDA / ROCm)                               │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐    │
│  │ WireGuard │ │ NAS      │ │ Monitors          │    │
│  │ VPN       │ │ WebDAV   │ │ Scheduler         │    │
│  └──────────┘ └──────────┘ └──────────────────┘    │
└─────────────────────────────────────────────────────┘
         │              │              │
         ▼              ▼              ▼
    ┌────────┐   ┌──────────┐   ┌──────────┐
    │ macOS  │   │ Windows  │   │ Android  │
    │ App    │   │ App      │   │ App      │
    └────────┘   └──────────┘   └──────────┘
         │              │              │
         └──────────────┼──────────────┘
                        ▼
                 WireGuard VPN
                 (10.0.0.0/24)
```

---

## Pricing

Holmium is **$8/month** or **$85/year** (cancel anytime).

- Free updates for life while your subscription is active

Payment is handled through **Stripe**. After payment, your license key is delivered
automatically. Enter it in the Install Manager or First-Boot Wizard.

---

<div align="center">
  <sub>Built with Arch Linux • OpenRC • FastAPI • Textual • vLLM • WireGuard</sub>
  <br>
  <sub> nOS_Coding. All rights reserved.</sub>
</div>
