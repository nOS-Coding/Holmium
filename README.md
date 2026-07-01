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

The core model is **Qwen3.6-35B-A3B-AWQ** — a 35-billion-parameter Mixture-of-Experts LLM
with activation-aware weight quantization (AWQ), delivering GPT-4-class reasoning on consumer
GPUs. At inference time only 3.6B parameters are active per token, meaning it fits in 6 GB VRAM
while maintaining near-full-precision quality.

No data leaves your home. No subscriptions to cloud APIs. No telemetry. Just your hardware,
your model, your assistant.

---

## Features

Holmium ships with **146 tools** across **30 capability modules**:

- **Local AI inference** — Qwen3.6-35B-A3B-AWQ via vLLM on your own GPU. 3.6B active params per token. AWQ group-size 128/64 quantization.
- **Code generation** — Generate, review, debug, and refactor code in any language with full project context.
- **Web research** — Search the web, fetch pages, scrape Wikipedia, Reddit, YouTube transcripts, news.
- **File & NAS system** — Read, write, move, search files. Expose via Samba/NFS/WebDAV. Full filesystem access with safety checks.
- **Shell & system control** — Run commands, manage processes, schedule tasks, set up monitors. SSH into connected devices.
- **GitHub & Git integration** — Manage repos, issues, PRs, commits, CI/CD workflows. Local + remote.
- **Email** — Read, search, send, reply, manage your inbox. Full IMAP/SMTP with AI composition.
- **Finance & stock analysis** — Real-time prices, portfolio tracking, history, trends, suggestions.
- **Data analysis** — Parse and analyze CSV, JSON, SQL with Pandas-backed engine. Charts, stats, reports.
- **Multi-modal vision** — Upload any image and ask questions. Extract text, describe scenes, analyze diagrams.
- **Image generation** — Text-to-image via FLUX.1-schnell. Style prompts, multiple resolutions.
- **Video generation** — Text-to-video via HunyuanVideo FramePack pipeline.
- **Voice** — Speech-to-text via Whisper large-v3. Text-to-speech via Kokoro (am_michael voice).
- **Containers** — Pull, run, exec, compose with Docker/Podman integration.
- **Browser automation** — Headless Chromium. Navigate, click, fill forms, scrape JS-rendered pages.
- **Clipboard sync** — Seamless copy-paste between all your devices.
- **Calendar & scheduling** — Events, reminders, iCal, Google Calendar sync.
- **Contacts** — Manage, auto-learn from conversations, suggest new entries.
- **Notes & documents** — Markdown notes with full-text search. Parse PDF, DOCX, XLSX.
- **Encrypted vault** — Store secrets (API keys, passwords) encrypted at rest, accessible only by Holmium.
- **LAN scanning & VPN** — Discover devices, secure WireGuard tunnel to your home network.
- **Remote device control** — SSH, file transfer, app control on connected LAN devices.
- **Raspberry Pi control** — GPIO, I2C, sensors, automation.
- **System monitoring** — CPU/GPU/RAM/disk health, proactive alerts, scheduled checks.
- **DeepThink mode** — Extended chain-of-thought reasoning for complex multi-step problems.
- **Cowork** — Collaborative multi-user file editing session.
- **Custom plugins** — Extend Holmium with your own tools via the plugin system.

---

## Quick Start

### 1. Download an ISO

Choose the variant that matches your GPU:

| Variant | GPU | Backend |
|---------|-----|---------|
| **NVIDIA** | RTX 5060 — RTX 5090 | vLLM CUDA + AWQ |
| **AMD** | RX 9060 XT — RX 9070 XT | vLLM ROCm + AWQ |

All variants require **16 GB RAM** minimum and **512 GB storage**.

### 2. Write to USB

Use any tool: Rufus, Balena-Etcher, `dd`.

### 3. ⚠ Read before booting

Installing Holmium **will wipe the target drive completely**. The installer repartitions and
formats the entire disk. There is no "keep files" option. **Back up everything you care about**
before proceeding. Have a recovery USB ready for your current OS.

Additional risks:
- **Bootloader conflicts** — dual-boot setups may require manual GRUB repair
- **GPU driver issues** — only RTX 5060–5090 (NVIDIA) and RX 9060 XT–9070 XT (AMD) are supported
- **Network problems** — unusual network hardware may need manual configuration
- **Beta software** — Holmium is in beta; expect rough edges and breaking changes

### 4. Boot & Install

Boot from the USB. The **Holmium Install Manager** launches automatically — a full TUI that
guides you through:

1. **Hardware detection** — GPU, disk, RAM, CPU detected automatically
2. **Variant selection** — Picks the right GPU profile or lets you choose
3. **Disk setup** — Select target disk (with clear warnings)
4. **Dual-boot** — Detects existing OS installations, pick which to keep
5. **License activation** — Enter your HOLM-XXXX-XXXX-XXXX key, verify via Lemon Squeezy
6. **User profile** — Tell Holmium about yourself so it adapts to you
7. **Install** — Partitions, formats, installs, configures GRUB, sets up GPU drivers

### 4. First Boot

After installation, Holmium boots into the **First-Boot Wizard** where you:

- Verify your license via Lemon Squeezy
- Set your name, goals, and preferences
- Connect to WiFi / Ethernet
- Configure dual-boot GRUB entries
- Start services

Then Holmium's TUI appears on the display. You can start talking immediately.

---

## Dual-Boot

Holmium wipes the target disk completely, then you set partition sizes for Holmium and
optionally a secondary OS. The Install Manager walks through it — pick a disk, set the space
for each OS, and Holmium partitions accordingly.

**Supported secondary OSes:**

| OS | Boot Method |
|----|-------------|
| Debian | GRUB chain-load |
| KDE Neon | GRUB chain-load |
| Ubuntu | GRUB chain-load |
| Fedora | GRUB chain-load |
| Nobara | GRUB chain-load |
| CachyOS | GRUB chain-load |

You install the second OS yourself later. Holmium saves the partition layout and always knows
where to find it for GRUB configuration.

---

## Apps

Holmium is accessible from every major platform:

### macOS (GUI App)

A native macOS windowed application:
- **Chat tab** — Message history, text input, send, file attachments, typing indicator
- **Dashboard tab** — Live system status: GPU temp, RAM, disk, uptime, quick actions
- **Settings tab** — Server address, port, auth token, auto-connect, clipboard sync, notifications
- Connection status indicator (green/yellow/red) in the status bar
- Auto-reconnect with backoff

### Windows (GUI App)

A native WPF windowed application:
- **Chat tab** — Message list with bubble styling, text input, send button, connection status bar
- **Dashboard tab** — Status cards (GPU, RAM, Disk, Uptime), quick action buttons
- **Settings tab** — Server address, port, auth token, auto-connect, clipboard sync, notifications
- Connection state: Connected / Disconnected / Connecting / Error with colored indicator
- Auto-reconnect with exponential backoff

### Android (GUI App)

A Material Design 3 native Android application:
- **Chat tab** — Real-time messaging with Holmium
- **Devices tab** — Connected device management
- **Settings tab** — Server configuration, theme (Light/Dark/System), clipboard sync, notifications
- Bottom navigation with three tabs

### Linux (TUI + CLI)

- Full TUI (Textual) runs on the Holmium PC display (tty1) — the primary interface
- CLI commands available via `holmium` tool for scripting and automation
- WebSocket connection to the backend for real-time interaction

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
6. **License** — Enter HOLM-XXXX-XXXX-XXXX key, verify via Lemon Squeezy
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
│  │  Qwen3.6-35B-A3B-AWQ (CUDA / ROCm)          │   │
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

- License key delivered instantly via Lemon Squeezy after purchase
- Ed25519-signed, machine-bound, one license per machine
- Free updates for life while your subscription is active

[Subscribe monthly](https://holmiumai.lemonsqueezy.com/checkout/buy/0fa7543e-6348-4667-ba0c-81470657c268) •
[Subscribe yearly](https://holmiumai.lemonsqueezy.com/checkout/buy/ee76b0f1-a789-4117-94b6-14afa50e08f3)

---

<div align="center">
  <sub>Built with Arch Linux • OpenRC • Qwen3.6-35B-A3B-AWQ • FastAPI • Textual • vLLM • WireGuard • FLUX.1 • Whisper • Kokoro</sub>
  <br>
  <sub> nOS_Coding. All rights reserved.</sub>
</div>
