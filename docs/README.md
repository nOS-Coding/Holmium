# Holmium — Personal AI Operating System

Holmium is a private, personal AI OS and assistant for a single user. Named after Holmium (GTA Vice City). Runs on a dedicated PC with Arch Linux, ROCm, and Qwen3.6-35B-A3B-AWQ.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      WireGuard Tunnel                        │
│                    10.0.0.0/24 subnet                        │
│                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐ │
│  │  Android  │   │  macOS   │   │   Pi     │   │   TUI    │ │
│  │ 10.0.0.3  │   │ 10.0.0.2 │   │ 10.0.0.4 │   │ (local)  │ │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘ │
│       │              │              │              │        │
│       └──────────────┼──────────────┼──────────────┘        │
│                      │              │                       │
│              ┌───────▼──────────────▼──────────┐            │
│              │    FastAPI Backend :8765          │            │
│              │  (Unix socket + HTTPS)           │            │
│              └───────┬──────────────┬──────────┘            │
│                      │              │                       │
│              ┌───────▼────┐  ┌──────▼────────┐              │
│              │  vLLM      │  │  Kokoro TTS   │              │
│              │  /v1/chat  │  │  am_michael    │              │
│              └───────┬────┘  └───────┬────────┘              │
│                      │              │                       │
│              ┌───────▼──────────────▼──────────┐            │
│              │          Whisper STT              │            │
│              │          large-v3                 │            │
│              └──────────────────────────────────┘            │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    Memory System                        │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐  │  │
│  │  │  SQLite     │  │  LanceDB    │  │  Embeddings   │  │  │
│  │  │  facts.db   │  │  vectors    │  │  MiniLM-L6-v2  │  │  │
│  │  └─────────────┘  └─────────────┘  └───────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    Tools                                │  │
│  │  file_ops  shell  app_control  remote  monitor         │  │
│  │  web_search  scrapers  vision  image_gen  media(stub)  │  │
│  │  email  finance  github  browser  notes  vault  ...    │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  ntfy.sh Push ───► Android + macOS Notifications       │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Components

| Directory | Purpose |
|-----------|---------|
| `os/` | Arch Linux base config, OpenRC services, archiso profile |
| `backend/` | FastAPI Python backend — Unix socket + HTTPS hybrid |
| `model/` | vLLM config, ROCm setup, Qwen3.6-35B-A3B-AWQ |
| `memory/` | SQLite + LanceDB memory systems |
| `tools/` | Tool system (JSON TOOL_CALL format) |
| `tts/` | Kokoro TTS (am_michael) |
| `stt/` | Whisper STT (large-v3) |
| `search/` | DuckDuckGo + SearXNG |
| `wireguard/` | WG server config, keygen |
| `holmium-cmd/` | CLI for macOS/Linux |
| `tui/` | Local PC TUI (Textual) |
| `android/` | Kotlin Android app |
| `notifications/` | ntfy.sh push + Mac bridge |
| `installer/` | archiso profile + first-run wizard |
| `training/` | Fine-tuning pipeline |
| `docs/` | Documentation |

## Quick Start

See `docs/mac_setup.md` (macOS client) or `docs/android_setup.md` (Android).
