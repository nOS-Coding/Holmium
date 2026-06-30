# Changelog

## v1.0.0 (2026-06-28)

### Initial Release
- Full Android app with chat UI, voice recording/playback, settings, notifications
- FastAPI backend with Unix socket + HTTPS, SSE streaming, tool execution
- vLLM integration with Qwen3.6-35B-A3B-AWQ model on ROCm
- Whisper STT (large-v3) and Piper TTS (en_US-lessac-medium voice)
- SQLite memory system with facts, notes, todos, contacts, action history
- LanceDB vector store for semantic conversation memory (all-MiniLM-L6-v2)
- Tool system with JSON TOOL_CALL format: file_ops, shell, app_control, remote, monitor
- DuckDuckGo search with SearXNG fallback
- Custom web scrapers (Wikipedia, weather, GitHub, YouTube, Trendyol)
- OpenRC service management on Arch Linux minimal base
- WireGuard server with peer registration and QR code display
- ntfy.sh push notifications with Android + Mac clients
- macOS CLI client with rich terminal UI and daemon
- Local TUI with Textual on linux driver
- First-run wizard, USB backup, session management
- Fine-tuning pipeline with QLoRA (rank 16/32, Unsloth)
- Self-distillation training data generation (500+ pairs)
- Encrypted vault, scheduler, briefing, benchmark tools
- Plugin system with @holmium_tool decorator
- Vision Doc system for Think mode analysis
- Image generation with FLUX.1-schnell
- Email, finance, GitHub, media, clipboard, LAN scanner tools
- Usage stats, API keys, version tracking
- Full test suite with pytest
