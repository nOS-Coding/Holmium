# tui — Local PC Textual TUI

Textual TUI running on linux console framebuffer driver. Auto-starts on tty1. TomCol theme (orange/pink/cyan/black). Connects to backend via Unix socket.

- `app.py` — Textual app entrypoint
- `screens/` — screen definitions (chat, mode switch, settings)
- `theme.py` — TomCol theme
- `service/` — OpenRC service wrapper
