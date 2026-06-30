# HOLMIUM — Personal AI Operating System

You are building **Holmium**, a private, personal AI OS and assistant for a single user.
Holmium runs on a dedicated x86_64 PC with an AMD GPU (>=16GB VRAM) and >=32GB RAM.
The OS is a stripped **Arch Linux** minimal base with **OpenRC** as init. No systemd.
Holmium is fully autonomous — no permission gates, executes silently and immediately.
Named after Holmium (GTA Vice City). Casual, American male, direct, confident.

This is a complete, private, single-user system. No multi-tenancy, no SaaS, no cloud.
WireGuard is the only ingress. DuckDuckGo + SearXNG (Pi) for search. ntfy.sh for push.
Everything else runs locally on the dedicated PC.

---

## PARAGRAPH 1 — Project Structure

```
holmium/
├── os/                  # Arch Linux base config, OpenRC services, archiso profile
├── backend/             # FastAPI Python backend — Unix socket + HTTPS hybrid
├── model/               # vLLM config, ROCm setup, Qwen3.6-35B-A3B-AWQ loading
├── memory/              # SQLite schema + LanceDB vector store logic
├── tools/               # Tool system (JSON TOOL_CALL format, file ops, shell, etc.)
├── tts/                 # Kokoro TTS (am_michael)
├── stt/                 # Whisper STT
├── search/              # DuckDuckGo primary + SearXNG (Pi) fallback
├── wireguard/           # WG server config, keygen, netsh wrapper
├── holmium-cmd/           # CLI for macOS/Linux (Textual TUI + daemon)
├── tui/                 # Local PC TUI (Textual, linux driver, Unix socket)
├── android/             # Kotlin Android app (API 29+)
├── notifications/       # ntfy.sh push + Mac notification bridge
├── installer/           # archiso custom profile + first-run wizard (in-TUI)
├── training/            # Fine-tuning pipeline (QLoRA, rank 16/32, self-distillation)
└── docs/                # Architecture docs, diagrams, README
```

Every subdirectory must have its own `README.md`. Create all directories + README stubs before any functional code.

---

## PARAGRAPH 2 — OS Base

Holmium OS is built on **Arch Linux** minimal (no DE, no display server, no bloat).
Include: Python 3.13+, pip, git, vim, curl, wget, htop, NetworkManager, OpenRC, ROCm, WireGuard tools, base-devel.
**No systemd.** OpenRC is the init. eudev replaces systemd-udev.
Write `os/packages.txt` (Arch packages) and `os/setup.sh` that installs everything on a fresh Arch minimal system.

---

## PARAGRAPH 3 — Init System (OpenRC)

Every Holmium component that runs on boot is an OpenRC service in `os/services/`:
- `holmium-backend` (FastAPI on Unix socket `/run/holmium/backend.sock`)
- `holmium-vllm` (vLLM on Unix socket `/run/holmium/vllm.sock`)
- `holmium-wireguard` (WireGuard interface via netsh)
- `holmium-tui` (Textual TUI on tty1)
- `holmium-scheduler` (background scheduler loop)
- `netsh-monitor` (background network monitor)

Each service has `start`, `stop`, `restart`, depends on network. `holmium-backend` waits for `holmium-vllm` to be healthy.
Format: standard OpenRC `/etc/init.d/` scripts.

---

## PARAGRAPH 4 — NetworkManager + WiFi

Arch Linux NetworkManager handles WiFi. WiFi credentials baked into the OS image at install time.
Write `os/network/configure_wifi.sh` that accepts SSID + password and writes the NM connection profile to
`/etc/NetworkManager/system-connections/holmium-wifi.nmconnection` (600, root-owned).
Called during the archiso install process. Auto-connect on boot, reconnect on drop.

---

## PARAGRAPH 5 — WireGuard Server

Holmium PC is WireGuard server. All remote clients (Mac, Android) connect through it.
Write `wireguard/setup_server.sh`: generates server keys, writes `/etc/wireguard/wg0.conf`
(listen port 51820, subnet 10.0.0.0/24, server = 10.0.0.1), enables IP forwarding, iptables NAT.
Write `wireguard/register_peers.sh`: generates two client keypairs — Mac = 10.0.0.2, Android = 10.0.0.3.
Outputs `wireguard/clients/mac.conf` and `wireguard/clients/android.conf`.
Android config: `AllowedIPs = 0.0.0.0/0` (full tunnel). Mac config: `AllowedIPs = 10.0.0.0/24` (Holmium only).
Display Android config as QR code via `qrencode -t ansiutf8` during first-run.
Pi optional: `wireguard/add_pi_peer.sh` adds 10.0.0.4 manually when needed.
WireGuard starts on boot via OpenRC service. Also wrapped by `netsh`.

---

## PARAGRAPH 6 — vLLM Model Server (Unix Socket)

Holmium's brain is **Qwen3.6-35B-A3B-AWQ** (QuantTrio/Qwen3.6-35B-A3B-AWQ, AWQ 4-bit, group size 128).
vLLM with ROCm backend listens on **Unix socket** at `/run/holmium/vllm.sock` (not TCP port).
Write `model/setup.sh`: installs vLLM with ROCm via pip, downloads model via wget from HF raw URL.
Write `model/start_vllm.sh`: launches vLLM with:
- `HIP_VISIBLE_DEVICES=0`, `ROCR_VISIBLE_DEVICES=0`
- `--max-model-len 131072`, `--gpu-memory-utilization 0.90`, `--swap-space 16`
- `--num-scheduler-steps 8`, `--dtype float16`
- `--api-key none` (backend handles auth)
- Unix socket at `/run/holmium/vllm.sock`

Model weights NOT in ISO. Downloaded on first boot via wget from HuggingFace raw URLs.
No `huggingface_hub` library.
Write `model/health_check.py` that polls the Unix socket until vLLM responds.

---

## PARAGRAPH 7 — Fine-Tuning Pipeline (QLoRA, rank 16/32)

Holmium's personality baked into the model via QLoRA fine-tuning.
Write `training/generate_data.py`: generates synthetic training data via **self-distillation**
(Qwen3.6 generates high-quality conversations from its own sessions, user-approved per pair).
Target: ~100 manual pairs + ~400 self-distillation pairs (total ≥500).
Format: ShareGPT JSONL (`{"conversations": [{"from": "human"/"gpt", "value": "..."}]}`).
System prompt for generation: Holmium is casual, American male, direct, confident, never asks permission,
never hedges, calls user by name, never says "I'm just an AI".

Write `training/finetune.sh`: QLoRA with Unsloth, rank 16, alpha 32, targeting all 7 LoRA modules
(q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj).
Batch size 1, gradient accumulation 8 (effective batch 8), 3 epochs, cosine LR, warmup 100 steps,
peak LR 2e-4. Save checkpoints to `training/checkpoints/`.
Write `training/merge.sh`: merges LoRA adapter into base model, saves to `model/holmium-merged/` in safetensors.

---

## PARAGRAPH 8 — FastAPI Backend (Unix Socket + HTTPS)

The FastAPI backend at `backend/main.py` is Holmium's central orchestrator.
Listens on two interfaces:
- **Unix socket** at `/run/holmium/backend.sock` for local TUI
- **HTTPS** on `0.0.0.0:8765` for remote clients (macOS CLI, Android) over WireGuard

Internal endpoints (both sockets):
- `POST /chat` — receive message, retrieve memory context, call vLLM, execute tools if needed, stream SSE response
- `POST /stt` — receive audio, run Whisper, return transcript
- `POST /tts` — receive text, run Kokoro, return audio WAV
- `GET /status` — CPU%, GPU%, RAM%, VRAM%, uptime, vLLM status, WireGuard status
- `GET /logs` — stream live log
- `POST /memory/add`, `GET /memory/list`, `DELETE /memory/forget/<key>`, `GET /memory/search?q=<query>`
- `POST /backup` — trigger USB backup (zip to `/mnt/backup/`)
- `POST /notify` — send ntfy.sh push + Mac notification
- `POST /upload/file` — file upload (images + documents)
- `GET /files/download?path=` — file download
- `GET /sessions/list`, `GET /sessions/<id>`
- `POST /keys/create`, `GET /keys/list`, `DELETE /keys/<label>`
- `POST /benchmark`
- `GET /stats`
- `GET /tools/list` — list all registered tools
- `GET /alerts/history` — last 50 alerts
- `GET /vision_docs/<slug>`
- `POST /register_device` — FCM token registration (ntfy.sh topic)
- `WebSocket /ws/chat` — for CLI interactive shell streaming
- `WebSocket /notifications/ws` — for Mac daemon notification connection

All endpoints require `X-Holmium-Token` header (HMAC-comparison via `require_token` dependency).
Token generated on first run, stored at `/etc/holmium/token`.
Log every request/response to `/var/log/holmium/holmium.log`.

---

## PARAGRAPH 9 — Memory System (SQLite)

Structured facts in SQLite at `/var/holmium/memory/facts.db`.
Schema tables:
- `facts` (key TEXT PK, value TEXT, created_at DATETIME, updated_at DATETIME)
- `action_history` (action_id TEXT PK, timestamp ISO, tool_name TEXT, parameters TEXT, result_summary TEXT, session_id TEXT, success BOOL)
- `notes` (id INTEGER PK, title TEXT, content TEXT, created_at DATETIME, updated_at DATETIME, tags TEXT)
- `todos` (id INTEGER PK, title TEXT, done INT DEFAULT 0, due_date TEXT, priority TEXT, created_at DATETIME, completed_at DATETIME)
- `contacts` (id INTEGER PK, name TEXT, email TEXT, phone TEXT, notes TEXT, created_at DATETIME)
- `portfolio_snapshots` (id INTEGER PK, snapshot_date TEXT, ticker TEXT, shares REAL, price REAL, value REAL, gain_loss REAL, gain_loss_pct REAL)
- `api_keys` (key_hash TEXT PK, label TEXT, created_at DATETIME, last_used DATETIME, enabled INT)
- `usage_stats` (date TEXT, hours_active REAL, messages_sent INT, tools_used TEXT, top_topics TEXT, sessions_count INT)

Write `memory/sqlite_store.py` with typed functions for each table.
Write `memory/fact_extractor.py`: takes a conversation turn, uses lightweight vLLM call to extract
new facts (name mentions, preferences, dates, todos), upserts into SQLite. Runs async after every user message.

---

## PARAGRAPH 10 — Memory System (LanceDB)

Semantic conversation memory via **LanceDB** at `/var/holmium/memory/lancedb/` (not ChromaDB).
Write `memory/vector_store.py`: initializes LanceDB, creates collection `conversations`.
Embedding model: **all-MiniLM-L6-v2** ONNX (~80MB, 384d, CPU-only via onnxruntime-cpu).
Bundled in ISO at `/usr/lib/holmium/embeddings/model.onnx`.
Functions: `add_turn(role, content, timestamp)`, `search_similar(query, n=5)`, `get_recent(n=20)`.
Every conversation turn stored. Before each LLM call, retrieve top-5 similar past turns + last 20 turns.

---

## PARAGRAPH 11 — Context Assembly

Write `backend/context.py` — assembles the full context for each vLLM call:
1. Load Holmium's system prompt from `/etc/holmium/system_prompt.txt`
2. Inject user's configured name (user)
3. Retrieve top-5 semantically similar turns from LanceDB
4. Retrieve last 20 turns from LanceDB
5. Retrieve all SQLite facts as formatted block
6. Append current conversation history from active session
7. Append current user message
8. Append response rules from `/etc/holmium/response_rules.txt`

Total context must not exceed **48000 tokens** (our assembly limit).
vLLM context window: 131072 tokens (remaining tokens for model's internal reasoning + generation).
Write token counter using `tiktoken`, truncate oldest turns first if over limit.

---

## PARAGRAPH 12 — System Prompt

Write `/etc/holmium/system_prompt.txt` — Holmium's core personality:
- Private AI assistant running on his own dedicated PC
- Named Holmium
- Casual, American, direct, confident
- Never asks for permission
- Never says "I'm just an AI" or hedges
- Addresses user by their configured name (user)
- Aware he has tools and uses them without announcing
- Keeps responses concise unless detail is asked
- Never refuses a task
- Proactive about alerts
- Knows the user's preferences
- Speaks like a guy you'd trust with your computer

---

## PARAGRAPH 13 — Tool System Architecture

Tool format: **JSON TOOL_CALL** (not XML).
When the model outputs `TOOL_CALL: {"tool": "tool_name", "params": {...}}`, the backend intercepts,
executes the tool, and injects `TOOL_RESULT: {...}` into the conversation.
Write `tools/registry.py`: central registry with name, description, param schema (JSON Schema), handler function.
Write `tools/executor.py`: looks up handler by name, calls it with params, returns result.
Write `tools/parser.py`: scans LLM response for `TOOL_CALL:` blocks, parses JSON, passes to executor.
Tool calls invisible to user — only the final result appears in Holmium's response.
Max 5 sequential tool calls per response.

---

## PARAGRAPH 14 — File Operations Tool

Write `tools/file_ops.py`:
- `file_read(path)` — returns file content
- `file_write(path, content)` — writes content (creates parent dirs)
- `file_delete(path)` — deletes file/directory
- `file_move(src, dst)` — moves file/directory
- `file_list(path)` — directory listing with sizes + modification times
- `file_exists(path)` — boolean

All paths absolute. No confirmation. No permission check. Execute immediately.

---

## PARAGRAPH 15 — Shell Execution Tool

Write `tools/shell.py`:
- `shell_run(command, timeout=30)` — `subprocess.run` with `shell=True`, returns stdout+stderr+exit code
- `shell_run_background(command)` — `subprocess.Popen`, returns PID immediately

No sandboxing, no filtering, no whitelist. Holmium runs whatever command is generated.

---

## PARAGRAPH 16 — App Control Tool

Write `tools/app_control.py` (uses `psutil`):
- `process_list()` — running processes with PID, name, CPU%, RAM%
- `process_kill(pid_or_name)` — kill by PID or name
- `process_start(command)` — start background process, return PID
- `process_status(pid)` — check if PID is running

---

## PARAGRAPH 17 — Remote Device Control Tool

Write `tools/remote.py`:
- `remote_shell(device, command)` — run shell on remote device via WG
- `remote_file_read(device, path)` — read file from remote
- `remote_file_write(device, path, content)` — write file to remote
- `remote_file_send(device, local_path, remote_path)` — transfer file

Devices looked up in `/etc/holmium/devices.json` mapping name → WG IP + auth token.
Pre-registered: `mac` (10.0.0.2), `android` (10.0.0.3), `pi` (10.0.0.4, stub).

---

## PARAGRAPH 18 — Monitor Tool

Write `tools/monitor.py`:
- `monitor_start(name, condition, interval)` — background loop evaluating a Python expression
- `monitor_stop(name)` — stop named monitor
- `monitor_list()` — list active monitors

Monitors reset on boot (no persistence). State not saved. No automated periodic tasks otherwise.

---

## PARAGRAPH 19 — Plugin System

Write `tools/plugins.py`:
- Scans `/etc/holmium/plugins/` for Python files
- Imports each, registers functions decorated with `@holmium_tool(name, description, params_schema)`
- Write the `@holmium_tool` decorator
- Example plugin at `/etc/holmium/plugins/example_plugin.py` implementing `get_time(timezone)`
- Document plugin API in `tools/README.md`

---

## PARAGRAPH 20 — DuckDuckGo Web Search

Write `search/duckduckgo.py`: uses `duckduckgo_search` Python library (not Tavily, no API key needed).
`web_search(query, max_results=5)` returns title, URL, snippet.
Write `search/ddg_fallback.py`: fallback for rate-limiting — uses `httpx` + `html2text` on DuckDuckGo's HTML page.
Write `search/search_tool.py`: registers `web_search` in tool registry, formats results as numbered list.
Holmium calls this automatically when he needs current information.
**No Tavily API. No API key.** DuckDuckGo is the primary. SearXNG (Pi) is the secondary fallback.

---

## PARAGRAPH 21 — Custom Scrapers

Write `search/scrapers/` — each implements `scrape(query_or_url)` returning clean extracted text.
- `wikipedia.py` — Wikipedia API, returns summary + sections
- `weather.py` — Open-Meteo free API (no key), geocode city, return current + 3-day
- `github.py` — GitHub REST API (token optional), search repos, read READMEs, list issues
- `youtube.py` — `youtube-transcript-api` for video transcripts
- `trendyol.py` — requests + BeautifulSoup with realistic UA + delay

Register all as tools: `scrape_wikipedia`, `scrape_weather`, `scrape_github`, `scrape_youtube_transcript`, `scrape_trendyol`.

---

## PARAGRAPH 22 — Whisper STT

Write `stt/whisper_stt.py`: loads Whisper large-v3 with ROCm, exposes `transcribe(audio_path)` → transcript.
Model loaded once on startup.
Write `stt/stt_service.py`: FastAPI sub-app at `/stt` — accepts WAV/WebM upload, returns JSON with `transcript`.
Android app sends audio to this endpoint.

---

## PARAGRAPH 23 — Kokoro TTS (am_michael)

Write `tts/kokoro_tts.py`: Kokoro TTS with voice **am_michael** (American male).
Exposes `synthesize(text)` → raw WAV bytes.
Write `tts/tts_service.py`: FastAPI sub-app at `/tts` — accepts JSON with `text`, returns audio/wav.
Android app calls this after receiving Holmium's text response for voice playback.

---

## PARAGRAPH 24 — Streaming Response Pipeline

Write `backend/streaming.py`:
1. Assemble context via `context.py`
2. Call vLLM Unix socket `/v1/chat/completions` with `stream=True`
3. As tokens arrive, scan for `TOOL_CALL:` JSON blocks
4. When complete tool call detected, pause streaming, execute tool, inject result, resume
5. Yield each token chunk as SSE event to `/chat` endpoint
6. `StreamingResponse` with `text/event-stream`

`holmium` CLI and Android app consume this SSE stream and render tokens as they arrive.

---

## PARAGRAPH 25 — Boot Greeting

Write `backend/greeting.py`: on backend startup (after vLLM healthy), generate a short greeting
via vLLM — casual, acknowledges time of day, uses user's name.
Pass to Kokoro TTS, play via `aplay` on PC speakers.
Generated fresh each boot. Not hardcoded.

---

## PARAGRAPH 26 — Local TUI (Textual, Unix Socket, Tab Modes)

Write `tui/main.py` using `textual` with `TEXTUAL_DRIVER=linux`:
- **Header**: ASCII Holmium logo + palm tree (#FF6B35 / #00BCD4).
  Current mode badge: **[THINK]** / **[WORK]** / **[IMAGE]** in mode-colored text.
  Status bar: connection quality (WG handshake age), GPU temp, user name, mode.
- **Left sidebar**: Live system stats (CPU%, GPU temp/util%, RAM, VRAM, uptime, vLLM, WG status) — refreshed every 2s.
- **Main panel**: Scrollable conversation log — user in cyan, Holmium in white.
- **Input bar**: `>>>` in #FF6B35. Placeholder "Ask Holmium anything...".
  - Tab: cycle modes (Work → Think → Image → Work)
  - `:` prefix: command mode
  - `//` prefix: comment (not sent)
  - `@` mentions: file completion from `~/.holmium/notes/`
- **Status bar**: `Tab switch mode | Ctrl+C interrupt | Ctrl+D exit | Ctrl+S sidebar | Ctrl+L clear`. Right: token count.
- Connects to backend via **Unix socket** `/run/holmium/backend.sock`.
- Command mode: `/help`, `/clear`, `/forget`, `/reboot`, `/shutdown`, `/systemctl`, `/memory`,
  `/model`, `/theme`, `/toggle`, `/web on/off`, `/push`, `/screenshot`, `/finetune`,
  `/fact`, `/lora`, `/whoami`, `/su`, `/netsh`, `/notes list`, `/todo list`, `/actions list`, `/visiondoc export`

---

## PARAGRAPH 27 — `holmium` CLI Client (macOS + Linux)

Write `holmium-cmd/holmium.py` — a single Python script installed as the `holmium` command on macOS and Linux.
Connects to Holmium PC over WireGuard (10.0.0.1:8765) via HTTPS with self-signed cert.
Auth token from `~/.netsh/hosts.json`.

Running `holmium` with no args opens interactive REPL shell:
- Connects via WebSocket to `/ws/chat`
- Prompt: `> ` (right-angle bracket)
- Holmium's responses stream and print immediately (no buffering)
- Multi-line input, history via `readline`, Ctrl+C cancels stream, Ctrl+D exits
- Markdown rendering via `rich`

Subcommands:
- `holmium status` — formatted dashboard (calls `/status`)
- `holmium status -p` — ping check
- `holmium status -l` — stream `/logs`
- `holmium status -s` — system stats only
- `holmium send <local> <remote>` — file upload with progress bar (`rich.Progress`)
- `holmium send <remote> <local>` — file download
- `holmium -m edit` — fetch facts, open in `$EDITOR`, save changes back
- `holmium -m list`, `holmium -m forget <key>`, `holmium -m search <query>`
- `holmium -n list`, `holmium -n add "<title>"`
- `holmium -t list`, `holmium -t done "<title>"`
- `holmium -c list`, `holmium -c add "<name>" <email>`, `holmium -c search <query>`
- `holmium -v list`, `holmium -v show <slug>`, `holmium -v delete <slug>`
- `holmium -a list`, `holmium -a search <query>`
- `holmium -s list`, `holmium -s show <id>`
- `holmium -f report`, `holmium -f history <ticker>`
- `holmium -i list`
- `holmium mode <think|work|image>`
- `holmium briefing`
- `holmium benchmark`, `holmium benchmark --quick`, `holmium benchmark --history`
- `holmium stats`, `holmium stats --week`, `holmium stats --history`
- `holmium backup`
- `holmium update`
- `holmium version`
- `holmium --help` — formatted rich table by category
- `holmium --tools` — live tool registry listing
- `holmium --vault add/get/list/delete`
- `holmium --key create <label>`, `--key list`, `--key revoke <label>`
- `holmium send vd-<slug>` — export Vision Doc
- `holmium send vd-all` — export all Vision Docs as zip

---

## PARAGRAPH 28 — `holmium` CLI Transport

HTTPS (TLS) over WireGuard. Self-signed cert from `wireguard/gen_cert.sh` (10-year validity, stored at `/etc/holmium/tls/`).
FastAPI backend serves HTTPS on `0.0.0.0:8765` with `--ssl-keyfile` and `--ssl-certfile`.
CLI uses `httpx` with `verify=False` (WG tunnel is already encrypted).
Interactive shell uses WebSocket (`/ws/chat`) for real-time bidirectional streaming.

---

## PARAGRAPH 29 — `holmium` CLI Install Script

Write `holmium-cmd/install.sh`:
- Check for Python 3.10+
- Install pip packages: `httpx`, `websockets`, `rich`, `readline`
- Copy `holmium.py` to `/usr/local/bin/holmium`, make executable
- Create `~/.netsh/` directory
- Prompt for Holmium PC's WG IP + auth token → write `~/.netsh/hosts.json`
- macOS: add to PATH. Linux: same.
- Print success with usage.

---

## PARAGRAPH 30 — Notification System (ntfy.sh)

Write `notifications/ntfy_push.py`: uses `ntfy` Python client to send push notifications.
Self-hosted ntfy.sh topic (WG-only) or public topic.
Android app receives via WebSocket. No Firebase, no FCM.
Configurable topic in `/etc/holmium/config.json` (e.g., `holmium-<hostname>`).
`send_notification(title, body)` pushes to the topic.

---

## PARAGRAPH 31 — Notification System (Mac)

Write `notifications/mac_notify.py`:
- `send_mac_notification(title, body)` pushes over WebSocket to Mac daemon
- Mac daemon (`holmium-cmd/daemon.py`) maintains persistent WebSocket to `/notifications/ws`
- On receive: `osascript -e 'display notification ...'` for native macOS notification
- Daemon also handles clipboard commands and `/receive_file` for images from Holmium

Mac daemon is separate from the macOS TUI client. Both run simultaneously.
Daemon auto-starts via macOS LaunchAgents or Login Items.

---

## PARAGRAPH 32 — Proactive Alert System

Write `backend/alerts.py`:
- `send_alert(title, body)` simultaneously calls `ntfy_push.send_notification()` + `mac_notify.send_mac_notification()`
- Alerts logged to `/var/log/holmium/alerts.log` with timestamp
- `GET /alerts/history` returns last 50 alerts
- TUI shows alert indicator in status bar

---

## PARAGRAPH 33 — Android App Structure

Android app in `android/` — Kotlin, API 29+ (minSdk 29, targetSdk 34).
Communicates over WireGuard HTTPS to `https://10.0.0.1:8765` with self-signed cert (custom TrustManager).
Components:
- `MainActivity.kt` — chat UI
- `VoiceActivity.kt` — voice recording + playback
- `SettingsActivity.kt` — token, server IP, TTS toggle, STT language, theme, wake word toggle
- `HolmiumApiClient.kt` — OkHttp + WebSocket client (self-signed cert)
- `AudioRecorder.kt` — WAV 16kHz 16-bit mono
- `AudioPlayer.kt` — low-latency PCM queue playback
- `VoiceSession.kt` — full voice-in/voice-out pipeline
- `FcmService.kt` — ntfy WebSocket notification handling
- `MemoryFragment.kt` — fact browser (search, edit, delete)
- `WakeWordService.kt` — "Hey Holmium" via Porcupine (OFF by default, toggle in settings)
- `ShareReceiver.kt` — Android share sheet integration
- `ShareHandler.kt` — extract source app, format pre-filled message
- `ThemeManager.kt` — dark/light/system toggle (default dark)

---

## PARAGRAPH 34 — Android Chat UI

Write `MainActivity.kt`: RecyclerView with message bubbles (user right-aligned blue, Holmium left-aligned dark gray on near-black background).
Streaming — Holmium's message bubble grows token by token as WebSocket delivers chunks.
Animated typing indicator when waiting for first token.
Conversation persists in-memory during session. On app start, fetch last 20 messages from `/memory/recent`.

---

## PARAGRAPH 35 — Android Voice Input

Write `AudioRecorder.kt`: records WAV 16kHz mono 16-bit PCM via `AudioRecord`.
Hold mic button → record → release → upload to `/stt` → transcript appears in input field → user reviews → sends.
`AudioPlayer.kt`: playback via `AudioTrack`, queue chunks back-to-back with no gaps.
Target: under 3 seconds from finishing speaking to hearing Holmium's first sentence.

---

## PARAGRAPH 36 — Android ntfy Integration

Write `FcmService.kt`: connects to ntfy.sh WebSocket, handles push notifications.
Shows local Android notification with title + body. In-app banner if foreground.
Store ntfy topic in EncryptedSharedPreferences.

---

## PARAGRAPH 37 — Android Memory Browser

Write `MemoryFragment.kt`: searchable list of SQLite facts. Tap to edit inline. Delete button.
Search bar filters by key/value. Mirrors `holmium -m` CLI commands in mobile UI.

---

## PARAGRAPH 38 — First-Run Wizard (In-TUI)

Write `installer/first_run.py` — integrated into the TUI (not whiptail/dialog).
On first boot (`/etc/holmium/config.json` doesn't exist), Holmium detects this and launches the wizard inside the TUI:
1. Welcome screen with ASCII Holmium logo
2. Ask for user's name (user)
3. Confirm WiFi SSID + password
4. Generate WireGuard server keys, show server public key
5. Generate Mac + Android client configs, show Android QR code
6. Set Holmium auth token (auto-generated, shown to user)
7. Ask for DuckDuckGo (no key needed) — skip, already configured
8. Ask for optional GitHub token for code updates
9. Summary screen → write `/etc/holmium/config.json`
10. Start all OpenRC services
11. Disable first-run flag

---

## PARAGRAPH 39 — Config File

Write `backend/config.py` — loads `/etc/holmium/config.json` as typed dataclass.
Fields: `user_name`, `wifi_ssid`, `holmium_token`, `tts_voice`, `stt_model`, `vllm_model`,
`vllm_socket`, `backend_socket`, `wireguard_subnet`, `ntfy_topic`, `github_token`,
`timezone` (default UTC), `mode_default` (work),
`mode_temps` (think: 0.1/0.85, work: 0.5/0.9, image: 0.8/0.95).
Write `config_validator.py` — checks all required fields present on startup.
Config never committed to git — add to `.gitignore`.

---

## PARAGRAPH 40 — USB Backup (not git)

Write `backend/backup.py` — implements `run_backup()`:
1. Copy `/var/holmium/memory/facts.db` to `/mnt/backup/holmium-backup-<date>/facts.db`
2. Export LanceDB to `/mnt/backup/holmium-backup-<date>/lancedb_export/`
3. Copy `/var/holmium/vision_docs/`, `/var/holmium/sessions/`, `/var/holmium/notes/`
4. Copy `/etc/holmium/config.json` (with secrets redacted)
5. All into a single `.zip` at `/mnt/backup/holmium-backup-<date>.zip`
6. USB auto-mounted via udev rule at `/mnt/backup/`
7. No git backup. No GitHub push for backup.
8. Called by `POST /backup` and `holmium --backup`. Never at shutdown — consolidation only.

---

## PARAGRAPH 41 — Logging System

Write `backend/logger.py` — structured logger, writes to `/var/log/holmium/holmium.log` with rotation
(max 50MB, keep 5). Every line: ISO 8601 timestamp, level, component, message.
Create `/var/log/holmium/` on startup. All modules import and use this logger.
`/logs` endpoint streams this file live via `tail -f` subprocess.

---

## PARAGRAPH 42 — Status Endpoint

Write `backend/status.py` — `/status` endpoint:
- CPU%, RAM% via `psutil`
- GPU stats via `rocm-smi --json` parsed (NOT pynvml)
- Uptime from `/proc/uptime`
- vLLM health by pinging `/run/holmium/vllm.sock`
- WireGuard peer count + handshake times via `wg show` parsing
- NTP sync status via `chronyc tracking`
- All as single JSON object

---

## PARAGRAPH 43 — Security Model

Write `docs/security.md`: no public ports, WireGuard is the only ingress.
FastAPI listens on `0.0.0.0:8765` HTTPS + `/run/holmium/backend.sock` Unix socket.
Shared token required on all endpoints. HMAC comparison via `hmac.compare_digest`.
TLS encrypts transport. WireGuard encrypts network. Auth token stored in `~/.netsh/hosts.json` (chmod 600)
and Android EncryptedSharedPreferences.
Write `backend/auth.py` — FastAPI dependency `require_token`.

---

## PARAGRAPH 44 — archiso Custom Profile (not Calamares)

Write `installer/archiso/` — custom archiso profile for Holmium OS.
Uses Arch Linux's `mkarchiso` tooling. Not Calamares.
Profile includes:
- `packages.x86_64` — all packages from `os/packages.txt`
- `root-image/` — custom root filesystem overlay with `/etc/holmium/`, OpenRC services, kernel config
- `efiboot/` — GRUB EFI boot entry
- `syslinux/` — BIOS boot
- Custom hook that runs first-boot setup

Partitioning during install:
- Prompt for target disk (default `/dev/nvme0n1`)
- Partition: 512MiB ESP (vfat) + 884GiB ext4 root + 16GiB swap + remaining unallocated (for Debian)
- Label: root partition labeled `holmium-root`
- Install GRUB. Single boot entry: Holmium OS. No fallback — recovery via USB rescue stick.
- Write ISO to USB: `dd bs=4M if=holmium-os-<date>.iso of=/dev/sda status=progress`

Document in `installer/README.md`.

---

## PARAGRAPH 45 — ASCII Holmium Logo

Write `tui/logo.py` — Holmium ASCII art in block letters (~6 lines tall), using `█`, `▀`, `▄`, box chars.
Appears in: TUI header, first-run wizard, boot splash, `holmium status` output.
Also a single-line version `HOLMIUM >` for prompts and status bars.

---

## PARAGRAPH 46 — `holmium` Interactive Shell UX

Interactive shell (`holmium` no args):
- Prompt: `> ` (right-angle bracket + space)
- Streaming effect: tokens print immediately, no buffering
- Blank line between responses
- Ctrl+C cancels stream without exiting
- Ctrl+D exits with goodbye message
- Up/Down arrows: input history from `~/.holmium_history`
- 80-char max line width for readability

---

## PARAGRAPH 47 — `holmium send` File Transfer

`holmium send ./local.txt /home/holmium/docs/file.txt` — upload via `POST /files/upload` with multipart.
`holmium send /home/holmium/docs/file.txt ./local.txt` — download via `GET /files/download?path=`.
Progress bar via `rich.Progress`. Corresponding FastAPI endpoints in backend.

---

## PARAGRAPH 48 — `holmium -m edit`

1. Fetch all facts via `GET /memory/list`
2. Serialize to `key: value` per line in temp file
3. Open in `$EDITOR` (default vim)
4. On save: diff old vs new
5. Call `/memory/add` for added/changed, `/memory/forget/<key>` for deleted
6. Print summary of changes
7. Syntax error → show error, re-open editor

---

## PARAGRAPH 49 — vLLM Tool Call Integration

Write `backend/tool_integration.py`:
- Buffer tokens as they stream from vLLM
- When buffer contains `TOOL_CALL:`, begin accumulating JSON
- When complete JSON object detected, parse via `tools/parser.py`
- Execute via `tools/executor.py`
- Inject `TOOL_RESULT: {...}` into stream
- Continue streaming
- Multiple tool calls in single response: handle sequentially
- If model needs to continue reasoning after tool: make second vLLM call with result appended

---

## PARAGRAPH 50 — ROCm Environment Setup (Arch)

Write `os/rocm_setup.sh` (Arch Linux):
- Install ROCm via pacman: `rocm-hip-sdk`, `rocm-opencl-sdk`, `rocm-dev`
- Add AMD ROCm repository if needed (Arch has ROCm in extra repos)
- `HSA_OVERRIDE_GFX_VERSION=11.0.0` in `/etc/environment` for RDNA4 if needed
- Verify with `rocminfo`
- Write `model/rocm_verify.py` that confirms ROCm sees GPU and can allocate VRAM

---

## PARAGRAPH 51 — Error Handling & Resilience

Write `backend/resilience.py`:
- vLLM not ready → queue request, retry every 5s for 2 minutes
- DuckDuckGo fails → fall back to SearXNG (Pi) → if Pi down too, return empty
- Kokoro fails → return text-only without audio
- LanceDB unavailable → continue with SQLite facts + session history only
- WireGuard down → continue serving localhost/Unix socket connections
- All errors logged with full stack traces
- Unhandled exceptions caught at FastAPI middleware level, logged, returned as clean JSON error

---

## PARAGRAPH 52 — Performance Targets

Document in `docs/performance.md`:
- vLLM first-token: <2s for <4096 token prompts
- Kokoro TTS: <500ms for <200 word responses
- Whisper STT: <3s for <30s audio clips
- `/status` endpoint: <100ms
- LanceDB search: <200ms

Write `backend/perf_monitor.py` — measures and logs these per-request. Warning at 2x threshold.

---

## PARAGRAPH 53 — Training Data Format

Document in `training/data_format.md` — ShareGPT JSONL.
Write `training/validate_data.py`: checks every entry has ≥1 human + 1 gpt turn,
no entry exceeds 4096 tokens (tiktoken), reports stats.
Write `training/split_data.py`: 90/10 train/eval split.

---

## PARAGRAPH 54 — Fine-Tuning with Unsloth (rank 16/32)

Write `training/finetune.sh`:
- Install Unsloth with ROCm support via pip
- Load base model in 4-bit with `FastLanguageModel`
- LoRA: rank 16, alpha 32, all 7 modules
- Batch size 1, gradient accumulation 8, 3 epochs
- Cosine LR, warmup 100 steps, peak LR 2e-4
- Evaluate every 100 steps, save checkpoints every 500 to `training/checkpoints/`
- After training: `training/merge.sh` merges adapter into base, saves to `model/holmium-merged/` in safetensors

---

## PARAGRAPH 55 — Startup Sequence

Document and implement in `docs/startup_sequence.md`:
1. OpenRC starts NetworkManager (WiFi connects)
2. OpenRC starts WireGuard (netsh wg up)
3. OpenRC starts holmium-vllm (launches vLLM on Unix socket, waits for health check)
4. OpenRC starts holmium-backend (waits for vLLM healthy, starts FastAPI on Unix socket + HTTPS)
5. Backend loads config, init SQLite, LanceDB, tool registry, plugins
6. Backend calls `greeting.py` — generates + plays boot greeting on PC speakers
7. OpenRC starts holmium-tui (Textual on tty1)
Target: <90s power-on to Holmium greeting (dominated by vLLM model load).

---

## PARAGRAPH 56 — `/var/holmium` Directory Structure

```
/var/holmium/
├── memory/
│   ├── facts.db            # SQLite
│   └── lancedb/            # LanceDB persistent storage
├── monitors.json
├── sessions/
├── uploads/
├── audio/
├── images/
├── vision_docs/
├── stats/
├── vault.enc
├── scheduler.json
├── mode.json
└── network/
    └── known_devices.json
```

Write `os/setup.sh` to create all directories with correct ownership and permissions.

---

## PARAGRAPH 57 — `/etc/holmium` Directory Structure

```
/etc/holmium/
├── config.json              # Main config (never in git)
├── system_prompt.txt        # Holmium's personality
├── token                    # Auth token (256-bit hex, root-only)
├── devices.json             # Registered remote devices
├── secrets.env              # API keys (Tavily removed, now empty or for GitHub)
├── tls/                     # Self-signed cert + key
├── ntfy_topic.txt           # ntfy.sh topic
├── plugins/                 # User-added tool plugins
├── vault.salt               # Vault encryption salt
├── response_rules.txt       # Response formatting rules
└── VERSION                  # Semantic version string
```

All files owned by root, readable by `holmium` user group.

---

## PARAGRAPH 58 — Android App Settings Screen

Write `SettingsActivity.kt`:
- Server IP (default 10.0.0.1)
- Server port (default 8765)
- Auth token (EncryptedSharedPreferences)
- TTS enabled/disabled toggle
- STT language (default English)
- Notification sound on/off
- Text size for chat bubbles
- Theme toggle: dark/light/system
- Wake word on/off (default OFF)
- "Test Connection" button (pings `/status`)
- "Re-register FCM" button
- Wake word access key field (Porcupine free key)
- WG TCP image listener port

All settings persist via EncryptedSharedPreferences.

---

## PARAGRAPH 59 — Embedding Model (all-MiniLM-L6-v2 ONNX)

Write `memory/embeddings.py`: `sentence-transformers/all-MiniLM-L6-v2` ONNX (OrtValue format).
~80MB, 384d, CPU via `onnxruntime-cpu`. Bundled in ISO at `/usr/lib/holmium/embeddings/model.onnx`.
`embed(text)` → list of floats. `embed_batch(texts)` → batch.
Registered as LanceDB's embedding function. Runs on CPU to avoid competing with vLLM for VRAM.

---

## PARAGRAPH 60 — Session Management

Write `backend/sessions.py`:
- Each connection gets UUID session ID
- Session fields: session_id, start_time, client_type (tui/cli/android/macos), last_activity, message buffer (last 50 turns)
- On session end: full conversation saved to `/var/holmium/sessions/<session_id>.json`
- `/chat` WebSocket creates session on connect, closes on disconnect
- `/memory/recent` returns combined last 20 turns across recent sessions
- 30-min inactivity timeout
- Session replay: `session_list(n=20)`, `session_get(id)`
- Sessions older than 90 days auto-archived to `/var/holmium/sessions/archive/`

---

## PARAGRAPH 61 — Testing

Write `tests/` with pytest:
- `test_tools.py` — unit tests for every tool
- `test_memory.py` — SQLite CRUD, LanceDB insert/search
- `test_api.py` — FastAPI endpoint tests with `httpx.AsyncClient`
- `test_streaming.py` — SSE streaming end-to-end
- `test_tool_parser.py` — JSON TOOL_CALL parsing edge cases
- `test_config.py` — config loading + validation
- `tests/run_all.sh` — runs all tests, reports pass/fail
- Mock external services (vLLM, DuckDuckGo, ntfy) via `unittest.mock`

---

## PARAGRAPH 62 — Documentation

Write: `docs/README.md` (overview + ASCII arch diagram), `docs/holmium_cli.md` (full command reference),
`docs/android_setup.md` (step by step: WireGuard → APK → settings),
`docs/mac_setup.md` (WireGuard → install.sh → daemon),
`docs/adding_tools.md` (plugin API), `docs/training.md` (data gen → fine-tune → merge),
`docs/troubleshooting.md`, `docs/performance.md`, `docs/startup_sequence.md`, `docs/security.md`,
`docs/api.md` (external script auth with API keys), `docs/roadmap.md`.

---

## PARAGRAPH 63 — Task Scheduler

Write `backend/scheduler.py`:
- Detect scheduling intent in user messages via structured vLLM call returning:
  `task_description`, `tool_calls`, `schedule` (cron or ISO datetime), `repeat` (bool)
- Store tasks in `/var/holmium/scheduler.json`
- `backend/scheduler_runner.py` — background asyncio loop, wakes every minute, executes due tasks
- Results logged to `/var/log/holmium/scheduler.log`
- FCM + Mac notification if task produced output
- Functions: `scheduler_list()`, `scheduler_cancel(id)`, `scheduler_add(task)`
- FastAPI endpoints: `/scheduler/list`, `/scheduler/cancel/<id>`
- Registered as tools: `schedule_task`, `cancel_task`
- Tasks persist across reboots. No cron.

---

## PARAGRAPH 64 — Markdown Rendering

Write `holmium-cmd/renderer.py` using `rich`:
- Detect headers, bold, italic, inline code, code blocks, lists, blockquotes
- Headers in bold cyan, code blocks in dark panel with `rich.syntax.Syntax` (auto-detect language)
- Inline code in yellow, bold in bold white, bullets as proper list items
- Handle partial tokens — buffer until markdown element complete before rendering
- Apply in both `holmium` CLI and TUI conversation panel

---

## PARAGRAPH 65 — Vision & Image Support

Write `tools/vision.py`:
- `analyze_image(image_path, question=None)` — base64-encode image, send to vLLM multimodal via Unix socket
- `fetch_url_image(url)` — download URL image to `/var/holmium/uploads/`, pass to `analyze_image`
- Register `vision_analyze_file` and `vision_analyze_url` as tools
- `backend/image_upload.py`: `POST /upload/file` accepts images + documents, saves to `/var/holmium/uploads/`
- CLI detects drag-and-drop/pasted image paths and auto-uploads before sending
- Android app has attachment button (paperclip) that opens image picker

---

## PARAGRAPH 66 — Action History

Write `memory/action_history.py`:
- Every tool call recorded: action_id (UUID), timestamp, tool_name, parameters, result_summary (500 chars), session_id, success
- Stored in SQLite `action_history` table
- `log_action()` called by tool executor after every call
- `get_recent_actions(n=50)`, `search_actions(query)` — LIKE search on tool_name + result_summary
- FastAPI: `GET /actions/recent`, `GET /actions/search?q=<query>`
- CLI: `holmium -a list`, `holmium -a search <query>`
- TUI: `/actions list`, `/actions search <query>`
- Included in USB backup

---

## PARAGRAPH 67 — Self-Update System

Write `backend/updater.py`:
- `holmium update` or `POST /update`
- `git fetch origin`, check if `origin/main` ahead
- If no updates: return "already up to date"
- If updates: show diff summary, `git pull`, `pip install -r requirements.txt --upgrade`
- Restart OpenRC services in order: stop tui → backend → scheduler, restart vLLM only if model changed, start backend → scheduler → tui
- Send ntfy.sh notification: "Holmium updated — version <commit hash>"
- Version bump: auto-increment patch version, generate CHANGELOG entry via vLLM
- `holmium version` prints: `Holmium OS v1.0.3 (abc1234) — 2025-06-15`
- Token limiting: 48000 context window

---

## PARAGRAPH 68 — APK Build System

Write `android/build.md`:
- Gradle, minSdk 29, targetSdk 34, compileSdk 34
- Dependencies: OkHttp 4.x, Kotlin Coroutines, ntfy Java client, EncryptedSharedPreferences, ExoPlayer, Retrofit, Gson
- `android/release.sh`: `./gradlew assembleRelease` → sign with keystore → `android/release/holmium.apk`
- Sideload via `adb install holmium.apk` or direct file transfer
- WireGuard must be configured before first launch

---

## PARAGRAPH 69 — TTS Voice Mode (Android)

Write `VoiceSession.kt`:
- Hold mic → capture audio → upload to `/stt` → transcript → auto-send to `/ws/chat`
- Holmium's streamed text displayed in chat AND simultaneously sent to `/tts` sentence-by-sentence
- TTS audio chunks queued in `AudioPlayer` and played back-to-back with no gaps
- Target: <3s from finishing speaking to hearing Holmium's first sentence

---

## PARAGRAPH 70 — Media Control Tool (Stub)

Write `tools/media.py` with `# FUTURE FEATURE` header.
Stub tools: `media_play()`, `media_pause()`, `media_next()`, `media_previous()`,
`media_volume(level)`, `media_get_current()`, `media_spotify_search(query)`.
All return `"Media control coming soon"`. Register in tool registry so Holmium knows they exist.
Document in `docs/roadmap.md` as next major addition.

---

## PARAGRAPH 71 — Response Formatting Rules

Write `/etc/holmium/response_rules.txt` (appended to system prompt in context assembly):
1. Use markdown freely — headers, code blocks, bullet lists, bold
2. Keep conversational replies short (1-3 sentences) unless detail requested
3. Task results: lead with outcome first, then details
4. Never use filler phrases ("Certainly!", "Of course!", "Great question!")
5. When executing tools silently, don't narrate — just show the result
6. Code blocks always include language tag
7. For long outputs (>50 lines), summarize and offer to show full
8. Time/date always in user's local timezone

---

## PARAGRAPH 72 — Conversation Modes (Think / Work / Image)

Write `backend/modes.py`. Active mode stored in `/var/holmium/mode.json` (persists across sessions).
Switching: Tab key in TUI, `holmium mode <think|work|image>` CLI, mode button in Android app.

**Think mode** (temp=0.1, top_p=0.85):
- Extended thinking enabled (`enable_thinking=True` in vLLM)
- Read-only: no file writes, no shell execution — analysis and planning only
- Auto-runs web search before every response
- At session end: generate **Vision Doc** at `/var/holmium/vision_docs/<timestamp>_<slug>.md`
  - Title, problem, findings, options, recommendation, next steps
  - Auto-summarized into SQLite fact

**Work mode** (temp=0.5, top_p=0.9):
- Aggressive tool use (no user confirmation per step)
- Multi-step planning: internal numbered plan, execute sequentially, report progress
- Task-first responses: no small talk, lead with action
- **Default mode**

**Image mode** (temp=0.8, top_p=0.95):
- Auto-detect generation (descriptive prompt → FLUX.1) vs analysis (file/URL → Qwen3 vision)
- Display mode badge in all UIs: `[THINK]`, `[WORK]`, `[IMG]`

---

## PARAGRAPH 73 — Shutdown Memory Consolidation

Write `backend/shutdown.py` — runs on SIGTERM:
1. Call vLLM with last 50 turns + active monitors → generate session summary (bullet list: discussed, done, unfinished, side notes)
2. Save summary as SQLite fact `session_summary_<timestamp>`
3. Summarize Vision Docs created this session → key decisions into memory
4. Save current mode, monitors, scheduler tasks to their JSON files
5. Flush LanceDB to disk
6. Log "Holmium signing off." Play Kokoro TTS goodbye on PC speakers
7. **No backup.** Only USB backup if explicitly triggered.
8. Register SIGTERM handler in `backend/main.py`. OpenRC `stop()` hook.

---

## PARAGRAPH 74 — Vision Docs System

Write `memory/vision_docs.py`:
- `create_vision_doc(title, content)` — saves markdown to `/var/holmium/vision_docs/<YYYYMMDD_HHMMSS>_<slug>.md`, writes SQLite fact `vision_doc_<slug>` with 500-char summary
- `list_vision_docs()` — returns list with title, path, created_at, summary
- `get_vision_doc(slug_or_path)` — full markdown content
- `delete_vision_doc(slug_or_path)` — remove file + fact
- Tools: `vision_doc_create`, `vision_doc_list`, `vision_doc_get`, `vision_doc_delete`
- CLI: `holmium -v list/show/delete`, `holmium send vd-<slug>`, `holmium send vd-all`
- Think mode auto-calls `vision_doc_create` at end of every session (not optional)

---

## PARAGRAPH 75 — Debian Dual Boot

Free space after Holmium's partition is reserved for Debian. The GRUB menu shows both OSes via os-prober.

Write `tools/debian_bridge.py`:
- Debian partition detected by label `debian-root` (primary) or auto-detected from free space.
- Mounted at `/mnt/debian` on demand.
- `debian_drop(src_path, dest_rel_path)` — copy file to Debian partition
- `debian_patch(debian_path, new_content)` — write content directly
- `debian_discard(debian_path)` — delete from Debian partition
- `debian_list(path)` — list files on Debian partition
- Image router also copies output images to `/mnt/debian/holmium/images/` on TUI/CLI routes.
- Workflow: develop in Holmium → `debian_drop` to Debian → test in KDE Plasma on Debian → `debian_patch` if fixes needed.


---

## PARAGRAPH 76 — Email Tool

Write `tools/email.py` (Python stdlib `imaplib` + `smtplib`, no external email libs):
- Config from `/etc/holmium/secrets.env`: `email_address`, `imap_host`, `imap_port`, `smtp_host`, `smtp_port`, `email_password`
- `email_fetch_inbox(n=10)` — last N emails (from, subject, date, body_preview, message_id)
- `email_read(message_id)` — full body
- `email_send(to, subject, body)` — plain-text via SMTP+TLS
- `email_search(query)` — IMAP SEARCH
- `email_reply(message_id, body)` — preserve thread
- `email_delete(message_id)` — move to trash
- Register all six as tools.

---

## PARAGRAPH 77 — Stock & Finance Tool

Write `tools/finance.py` (yfinance):
- `stock_price(ticker)` — price, change %, volume. Supports BIST (`.IS` suffix) + US
- `stock_history(ticker, period)` — OHLCV for period
- `stock_portfolio_summary()` — reads `/var/holmium/finance/portfolio.json`, returns current value, gain/loss, per-holding
- `stock_add_holding(ticker, shares, avg_buy_price)`, `stock_remove_holding(ticker)`
- `stock_analyze(ticker)` — 3 months OHLCV + news → vLLM analysis
- `stock_suggest(risk_level)` — top gainers/losers + news sentiment + filter by risk level → 3 suggestions
- Portfolio auto-snapshot daily at market close via scheduler

---

## PARAGRAPH 78 — Web Browsing Tool

Write `tools/browser.py` (httpx + BeautifulSoup + html2text):
- `browse_url(url)` — fetch, strip to markdown, extract links + images + title
- `browse_search_and_open(query)` — DuckDuckGo search → top result → `browse_url`
- `browse_follow_link(base_url, link_text)` — navigate by visible link text
- `browse_extract_table(url)` — `pandas.read_html` → JSON tables
- Realistic Chrome UA, session state via `tools/browser_state.py` (last 5 URLs remembered)

---

## PARAGRAPH 79 — Notes & Todo Tool

Write `tools/notes.py`:
- SQLite tables: `notes` (id, title, content, created_at, updated_at, tags)
- `todos` (id, title, done, due_date, priority, created_at, completed_at)
- Functions for CRUD + search + list
- Holmium proactively calls `todo_overdue()` every morning at 9am via scheduler → alert
- CLI: `holmium -n list/add`, `holmium -t list/done`
- TUI: `/notes list`, `/todo list`, `/todo done <id>`

---

## PARAGRAPH 80 — GitHub Integration Tool

Write `tools/github.py` (PyGithub):
- `gh_list_repos()`, `gh_create_issue()`, `gh_list_issues()`, `gh_close_issue()`
- `gh_create_pr()`, `gh_list_prs()`, `gh_merge_pr()`
- `gh_push_file(repo, path, content, commit_message, branch)` — create/update via API
- `gh_get_file(repo, path, branch)` — read via API
- `gh_monitor_repo(repo)` — check new issues/PRs every 15 min → alert
- Token from `/etc/holmium/secrets.env`

---

## PARAGRAPH 81 — Wake Word (Android, OFF by default)

Write `WakeWordService.kt`:
- Porcupine wake word detection, fully on-device, free tier
- "Hey Holmium" custom wake word
- OFF by default (PTT is default). Toggle in `SettingsActivity`.
- On detection: vibrate, play chime, open MainActivity, auto-start voice session
- Foreground service with persistent notification "Holmium is listening" when enabled
- Requires `RECORD_AUDIO` + `FOREGROUND_SERVICE_MICROPHONE` permissions
- Porcupine access key field in Settings (free key from Picovoice console)

---

## PARAGRAPH 82 — GRUB Dual Boot Configuration (Arch)

Write `os/grub_setup.sh`:
- GRUB for dual boot: Holmium OS (default) + other OS via os-prober
- Partition detected by label: `holmium-root`
- 5-second timeout. Press key → menu with both entries
- Single boot entry if other OS not yet installed

---

## PARAGRAPH 83 — WireGuard Peer Registration

Write `wireguard/register_peers.sh`:
- Two permanent peers: Mac (10.0.0.2), Android (10.0.0.3)
- Generate keypairs, write peer entries to `/etc/wireguard/wg0.conf`
- Output `wireguard/clients/mac.conf` and `wireguard/clients/android.conf`
- Android: `AllowedIPs = 0.0.0.0/0` (full tunnel)
- Mac: `AllowedIPs = 10.0.0.0/24` (Holmium only)
- Android config shown as QR code via `qrencode -t ansiutf8` during first-run
- Mac config saved at `/etc/holmium/devices.json`
- Pi (10.0.0.4) as optional third peer: `wireguard/add_pi_peer.sh`

---

## PARAGRAPH 84 — Contacts System

Write `tools/contacts.py`:
- SQLite `contacts` table: id, name, email, phone, notes, created_at
- `contact_add/get/list/update/delete/search`
- `contacts_learner.py`: runs after `email_fetch_inbox`, extracts sender display name + email, upserts into contacts
- When Holmium sends email: resolves name → email via contacts

---

## PARAGRAPH 85 — Portfolio History & P&L

Write `tools/finance_history.py`:
- Daily snapshot at market close via scheduler → inserts rows into `portfolio_snapshots`
- `portfolio_history(ticker, period)` — time series query
- `portfolio_report()` — markdown report: total value, P&L, best/worst, ASCII sparkline chart
- Sent as ntfy.sh push every Monday at 9am via scheduler

---

## PARAGRAPH 86 — Image Output Routing

Write `backend/image_router.py`:
- If request from TUI (client_type == 'tui'): save to `/var/holmium/images/`
- If from macOS CLI (client_type == 'macos'): save locally + transfer via WG TCP to `~/Pictures/Holmium/`
- If from Android (client_type == 'android'): base64-encode + send as `image` message type in WebSocket → inline in chat
- If from terminal CLI (client_type == 'cli'): save to `/var/holmium/images/` + print file path
- All images archived in `/var/holmium/images/`

---

## PARAGRAPH 87 — Pi Remote Control (Stub)

Write `tools/pi_control.py`:
- Pi not yet online → all tools return `"Pi is not available (not yet connected)."`
- Stub tools: `pi_status()`, `pi_service(action, service)`, `pi_reboot()`, `pi_shutdown()`, `pi_run(command)`, `pi_display(text)`
- When Pi comes online: registered as `pi` in `/etc/holmium/devices.json` at 10.0.0.4

---

## PARAGRAPH 88 — Help & Capability Discovery

- `holmium --help` — rich table of all CLI subcommands by category
- `holmium --tools` — calls `GET /tools/list`, prints live tool registry
- `GET /tools/list` — FastAPI endpoint, returns all registered tools as JSON
- Holmium knows his capabilities: when asked "what can you do?", lists tools by category from system prompt
- `holmium --version` — git hash + build date + model name + active mode + semantic version

---

## PARAGRAPH 89 — Vision Doc Export

- `holmium send vd-<slug>` — fetch Vision Doc, save as `<slug>.md` locally
- `holmium send vd-all` — zip all Vision Docs, download zip
- `GET /vision_docs/<slug>` — raw markdown endpoint
- `backend/vision_doc_export.py` — zip all files from `/var/holmium/vision_docs/`

---

## PARAGRAPH 90 — FLUX.1-schnell Image Generation (not SD 1.5)

Write `model/flux_setup.sh`:
- Install `diffusers` via pip
- Model: `black-forest-labs/FLUX.1-schnell` (not SD 1.5). Downloaded on first image gen request.
- Write `tools/image_gen.py`:
  - `FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-schnell", torch_dtype=torch.bfloat16).to("cuda")`
  - `generate_image(prompt, steps=4, guidance_scale=0.0, width=1024, height=1024)`
  - 4 inference steps, no CFG (schnell is distilled), saves PNG to `/var/holmium/images/`
- **VRAM management**: When `image_gen` called, vLLM minimizes VRAM (offloads to CPU via `--swap-space`).
  FLUX takes full 16GB VRAM, generates image, user sees in TUI and approves/disapproves.
  On approval: FLUX killed, vLLM maximizes VRAM again. Sequential, never concurrent.

---

## PARAGRAPH 91 — NTP & Timezone

Write `os/ntp_setup.sh`:
- Install `chrony`, configure `/etc/chrony/chrony.conf` with `pool.ntp.org`
- Enable `chronyd` OpenRC service
- Timezone set during first-run (default UTC) → stored in config.json as `timezone`
- All datetimes use Python `zoneinfo` with user's timezone
- NTP sync status in `holmium status` output

---

## PARAGRAPH 92 — Briefing System

Write `backend/briefing.py`:
- On trigger ("briefing", "give me a briefing", `holmium briefing`):
  1. Scrape weather
  2. Check overdue todos
  3. Portfolio summary
  4. Fetch last 5 unread emails
  5. List important notes
  6. List upcoming scheduled tasks
- Pass all data to vLLM: "Synthesize into concise spoken briefing. Lead with most important. Under 3 minutes. Use user's name."
- Stream text response + simultaneously synthesize via Kokoro TTS on PC speakers (TUI) or send as audio (Android)
- Can be scheduled: "briefing every weekday at 8am"

---

## PARAGRAPH 93 — Audio System Control

Write `tools/audio.py` (via `pactl`, PulseAudio/PipeWire):
- `audio_get_volume()`, `audio_set_volume(percent)`, `audio_mute()`, `audio_unmute()`, `audio_toggle_mute()`
- `audio_list_outputs()`, `audio_set_output(sink)`, `audio_get_current_output()`
- TUI shows volume % + mute state in status bar

---

## PARAGRAPH 94 — Boot Diagnostics

Write `backend/boot_diagnostics.py`:
- Runs silently on startup before greeting
- Checks: vLLM health (30s), LanceDB accessible, SQLite tables exist, WG up, NTP synced, ROCm visible, VRAM free ≥2GB, disk free ≥5GB, internet connectivity
- PASS/FAIL with timing, logged to `/var/log/holmium/boot_diagnostics.log`
- Critical failures → ntfy.sh notification immediately
- Non-critical → mentioned casually in greeting
- Complete in <5s

---

## PARAGRAPH 95 — Boot Splash

Write `os/splash/holmium-theme/` — plymouth theme:
- Black background, Holmium ASCII logo in white, progress bar at bottom, "HOLMIUM OS" small text below
- `os/splash/install_splash.sh` — installs theme, rebuilds initramfs
- Each OpenRC service calls `plymouth message --text="Starting <service>..."`
- When TUI launches: `plymouth quit --retain-splash` → clear screen → TUI
- No splash shown headless

---

## PARAGRAPH 96 — Session Replay

Extend session management:
- `session_list(n=20)` — last N sessions with id, start/end time, message count, client_type, first message preview
- `session_get(session_id)` — full message array (role, content, timestamp, tools_used, mode)
- FastAPI: `GET /sessions/list`, `GET /sessions/<id>`
- CLI: `holmium -s list`, `holmium -s show <id>` (markdown-rendered, color-coded, timestamps)
- TUI: `/sessions list`, `/sessions show <id>`
- Sessions >90d auto-archived to `/var/holmium/sessions/archive/`

---

## PARAGRAPH 97 — Encrypted Secrets Vault

Write `tools/vault.py` (Fernet + PBKDF2):
- Master key derived from passphrase + random salt (`/etc/holmium/vault.salt`)
- Encrypted data at `/var/holmium/vault.enc`
- Passphrase: first-run wizard → stored in memory only, never on disk
- On startup: prompt via TUI for passphrase OR auto-unlock from machine-id hash
- `vault_add(key, value)` — encrypt + store
- `vault_get(key)` — decrypt + return
- `vault_list()` — key names only
- `vault_delete(key)`
- `vault_search(query)` — search key names
- CLI: `holmium --vault add/get/list/delete`
- NOT included in USB backup — machine-local only

---

## PARAGRAPH 98 — Clipboard Tool

Write `tools/clipboard.py`:
- For Mac: daemon exposes WebSocket `clipboard_read` (pbpaste) and `clipboard_write` (pbcopy)
- For other OS: remote_shell via `xclip` or `wl-clipboard` (auto-detect X11/Wayland)
- `clipboard_read(device)`, `clipboard_write(device, content)`, `clipboard_sync(from, to)`

---

## PARAGRAPH 99 — LAN Scanner Tool

Write `tools/lan_scanner.py` (python-nmap):
- `lan_scan()` — ping scan on local subnet, discover devices with IP, MAC, hostname, vendor
- `lan_scan_device(ip)` — full port scan with `-sV`
- `lan_get_known_devices()` — from `/var/holmium/network/known_devices.json`
- `lan_register_device(mac, name)` — add to known registry
- `lan_unknown_devices()` — last scan devices not in known registry
- First scan: auto-populate with Holmium PC, Mac, Android
- Unknown device alert: "Unknown device on your network: <ip> (<vendor>)" via ntfy

---

## PARAGRAPH 100 — Android Share Sheet

Write `ShareReceiver.kt`: `ACTION_SEND` with `text/plain`, `text/html`, `image/*`.
Text → pre-filled in input field + "Shared from <source_app>: " prefix → auto-send.
Image → upload to `/upload/file` → send "Shared image from <source_app>" → Image mode auto.
Share target appears as "Holmium" with app icon in Android share sheet.

---

## PARAGRAPH 101 — Android Theme System

Write `ThemeManager.kt`:
- `dark` (default), `light`, `system` — stored in EncryptedSharedPreferences
- `AppCompatDelegate.setDefaultNightMode()` on apply
- Dark: `#0D0D0D` background, `#1A1A1A` surfaces, white text, `#00BCD4` accent for Holmium's messages
- Light: white backgrounds, light gray surfaces, dark text, same cyan accent
- Toggle in SettingsActivity + long-press settings icon on chat screen

---

## PARAGRAPH 102 — Benchmark Tool

Write `backend/benchmark.py`:
- `holmium benchmark` → runs all: vLLM speed (100-token prompt), vLLM context (4096-token), Kokoro latency, Whisper RTF, LanceDB search latency, SQLite ops/s, disk I/O, ROCm GPU stats during vLLM
- Save to `/var/holmium/benchmarks/<timestamp>.json`
- Print rich table: test, result, pass/fail vs targets
- `holmium benchmark --quick` → vLLM + TTS only
- `holmium benchmark --history` → trend table of past results

---

## PARAGRAPH 103 — Document Reading Tool

Write `tools/documents.py`:
- `pymupdf` (PDF), `python-docx` (DOCX), `openpyxl` (XLSX), `python-pptx` (PPTX)
- `doc_read(path)` — auto-detect by extension, extract to markdown
- `doc_summarize(path)` — read + pass to vLLM for summary
- `POST /upload/file` handles both images AND documents
- On document upload: auto-summarize, respond with summary, offer Q&A

---

## PARAGRAPH 104 — External API Key System

Write `backend/api_keys.py`:
- SQLite `api_keys` table: key_hash, label, created_at, last_used, enabled
- Keys stored as SHA-256 hashes — raw key shown once at creation
- `api_key_create(label)` → generate random 32-byte key, store hash, return raw key once
- `api_key_list()`, `api_key_revoke(label)`
- `require_token` accepts either primary token OR valid API key hash
- CLI: `holmium --key create/list/revoke`
- FastAPI endpoints: `POST /keys/create`, `GET /keys/list`, `DELETE /keys/<label>`
- Document in `docs/api.md`

---

## PARAGRAPH 105 — Version Tracking & Changelog

Write `os/version.py`:
- `/etc/holmium/VERSION` as semantic version string (initial `1.0.0`)
- On `holmium update` success: auto-bump patch version
- Generate CHANGELOG entry: `git log HEAD~N..HEAD --format:"%s"` → vLLM summary → prepend to `CHANGELOG.md`
- Commit updated `CHANGELOG.md` + `VERSION` with `chore: bump to v<new_version>`
- `holmium version` output: `Holmium OS v1.0.3 (abc1234) — 2025-06-15`

---

## PARAGRAPH 106 — Usage Stats Tracker

Write `backend/usage_stats.py`:
- SQLite `usage_stats` table: date, hours_active, messages_sent, tools_used, top_topics, sessions_count
- On session end: update today's row
- `usage_extract_topics()` — vLLM extracts 3-5 topic tags from session messages
- `usage_weekly_report()` — aggregate last 7 days: total messages, hours active, top tools, top topics, busiest day/hour
- Weekly report scheduled every Monday at 8am → ntfy push + save to `/var/holmium/stats/weekly_<date>.md`
- CLI: `holmium stats`, `holmium stats --week`, `holmium stats --history`

---

## PARAGRAPH 107 — Data Analysis Tool

Write `tools/data_analysis.py`:
- `analyze_data(file_path, question=None)`:
  1. Detect CSV or JSON
  2. Load with pandas, generate `df.describe()` + column names + row count + sample (5 rows)
  3. Pass summary + question to vLLM: "You are a data analyst. Answer the question or provide key insights. Then write a Python script using pandas and matplotlib to visualize the most interesting aspect."
  4. Extract Python code block
  5. Execute via `shell_run` in workspace `/home/holmium/projects/`
  6. If chart generated (detect `plt.savefig`), route via `image_router.py`
  Script saved to `/home/holmium/projects/analysis_<timestamp>.py`

---

## PARAGRAPH 108 — Build Order (Final)

Strict order. Do not skip. Each step depends on all previous:

1. Project directory structure + all READMEs
2. `os/packages.txt` + `os/setup.sh`
3. `os/ntp_setup.sh` + `os/set_timezone.sh`
4. `os/version.py` + `/etc/holmium/VERSION` (initial 1.0.0)
5. `backend/config.py` + `backend/config_validator.py`
6. `backend/logger.py`
7. `wireguard/setup_server.sh` + `wireguard/register_peers.sh` + `wireguard/add_pi_peer.sh` + `wireguard/gen_cert.sh`
8. `os/rocm_setup.sh`
9. `os/grub_setup.sh` + `os/fstab_setup.sh`
10. `os/splash/holmium-theme/` + `os/splash/install_splash.sh`
11. `model/setup.sh` + `model/start_vllm.sh` + `model/health_check.py` (vLLM Unix socket)
12. `model/flux_setup.sh` (FLUX.1-schnell, not SD 1.5)
13. `memory/sqlite_store.py` (all tables: facts, action_history, notes, todos, contacts, portfolio_snapshots, api_keys, usage_stats)
14. `memory/embeddings.py` (all-MiniLM-L6-v2 ONNX)
15. `memory/vector_store.py` (LanceDB)
16. `memory/vision_docs.py`
17. `memory/action_history.py`
18. `tools/registry.py` + `tools/executor.py` + `tools/parser.py` (JSON TOOL_CALL format)
19. `tools/github.py` (PyGithub, token from secrets.env, extended with CI/code review/releases/branches)
20. `tools/git_local.py` (git CLI wrapper, 18 operations)
21. `tools/file_ops.py`
22. `tools/shell.py`
23. `tools/app_control.py`
24. `tools/remote.py`
25. `tools/monitor.py` (non-persistent, reset on boot)
26. `tools/plugins.py` + example plugin
27. `tools/vision.py`
28. `tools/image_gen.py` (FLUX.1-schnell)
29. `tools/media.py` (stub)
30. `tools/framepack_generate.py`
31. `tools/email.py`
32. `tools/contacts.py` + `contacts_learner.py`
33. `tools/finance.py` + `tools/finance_history.py`
34. `tools/browser.py` + `tools/browser_state.py`
35. `tools/notes.py`
36. `tools/pi_control.py` (stub — Pi not yet online)
37. `tools/audio.py`
38. `tools/vault.py`
39. `tools/clipboard.py`
40. `tools/lan_scanner.py`
41. `tools/documents.py`
42. `tools/data_analysis.py`
43. `tools/debian_bridge.py`
44. `tools/video.py`
45. `tools/calendar.py`
46. `tools/containers.py`
47. `search/duckduckgo.py` + `search/ddg_fallback.py` + all scrapers
48. `stt/whisper_stt.py` + `stt/stt_service.py`
49. `tts/kokoro_tts.py` + `tts/tts_service.py` (am_michael voice)
50. `backend/modes.py` (think 0.1/0.85, work 0.5/0.9, image 0.8/0.95)
51. `backend/context.py`
52. `backend/streaming.py` + `backend/tool_integration.py`
53. `backend/scheduler.py` + `backend/scheduler_runner.py`
54. `backend/updater.py` (with version bump + CHANGELOG generation)
55. `backend/shutdown.py` (consolidation + USB backup only if explicitly triggered)
56. `backend/boot_diagnostics.py`
57. `backend/briefing.py`
58. `backend/benchmark.py`
59. `backend/image_router.py`
60. `backend/vision_doc_export.py`
61. `backend/api_keys.py`
62. `backend/usage_stats.py`
63. `backend/main.py` (all endpoints, Unix socket + HTTPS)
64. `backend/alerts.py` + `backend/backup.py` + `backend/status.py` + `backend/greeting.py`
65. `notifications/ntfy_push.py` + `notifications/mac_notify.py`
66. `holmium-cmd/renderer.py`
67. `holmium-cmd/holmium.py` + `holmium-cmd/install.sh` (all subcommands)
68. `holmium-cmd/daemon.py` (clipboard + `/receive_file` + notification WebSocket)
69. `tui/logo.py` + `tui/main.py` (Textual, Unix socket, Tab modes, TomCol theme)
70. `/etc/holmium/response_rules.txt`
71. `os/services/` (all OpenRC service files, Arch format)
72. `installer/first_run.py` (in-TUI wizard)
73. `installer/archiso/` (custom archiso profile, not Calamares)
74. `training/` (self-distillation data gen → validate → split → finetune rank 16/32 → merge)
75. Android app: all Kotlin files + build system + release
76. `tests/` (all tests with pytest)
77. `CHANGELOG.md` (initial entry v1.0.0) + all documentation

---

## PARAGRAPH 109 — Dev Tools (Git + GitHub)

Write `tools/github.py` (extended) and `tools/git_local.py`:

**GitHub tools (PyGithub, token from `/etc/holmium/secrets.env`):**
- Full PR lifecycle: create, list, merge, review (approve/comment/request_changes), comment, diff viewing, status details (mergeability, CI, labels)
- Issue management: create, list, close, labels (add/remove)
- Branch management: list, create (from ref), delete
- CI: list workflows, trigger workflow dispatch, list workflow runs
- Releases: list releases, create release (with tag, draft, prerelease)

**Local git tools (`git` CLI wrapper, operates on any local path):**
- Repo lifecycle: init, clone (with depth/branch), remote management
- Workflow: status, add, commit (with -a), push (with force), pull (with rebase), fetch (with prune)
- History: log (oneline/short/full format), show, diff (staged, between refs, file-filtered)
- Branching: branch (list/create/delete), checkout (with -b), merge (with --no-ff)
- Recovery: stash (push/pop/list/drop/apply), reset (soft/mixed/hard)
- Tagging: tag (list/create/delete, annotated)
