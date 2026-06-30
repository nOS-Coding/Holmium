# Startup Sequence

Target: <90s from power-on to Holmium greeting.

## Boot Order

```
1. GRUB bootloader appears (10s timeout)
   ├── Option A: Holmium OS (default)
    └── Option B: Other OS (if installed)

2. Linux kernel loads (5s)
   ├── plymouth splash: Holmium ASCII logo
   └── Initramfs loads

3. OpenRC init starts (3s)
   ├── eudev device manager
   ├── NetworkManager connects to WiFi
   └── Filesystems mounted (/var/holmium/, /etc/holmium/)

4. OpenRC service: holmium-wireguard (2s)
   ├── netsh wg up
   ├── WireGuard interface wg0 at 10.0.0.1
   └── IP forwarding + iptables NAT

5. OpenRC service: holmium-vllm (45s - dominant)
   ├── ROCm device initialized
   ├── Model loaded from disk (Qwen3.6-35B-A3B-AWQ)
   ├── Unix socket at /run/holmium/vllm.sock
   └── Health check: wait until responding

6. OpenRC service: holmium-backend (5s)
   ├── Wait: vLLM healthy (up to 2 min, 5s retry)
   ├── Load config from /etc/holmium/config.json
   ├── Initialize SQLite /var/holmium/memory/facts.db
   ├── Initialize LanceDB /var/holmium/memory/lancedb/
   ├── Load tool registry + plugins
   ├── Start FastAPI on Unix socket + HTTPS :8765
   ├── Run boot diagnostics
   ├── Generate greeting via vLLM
   ├── Synthesize via Kokoro TTS → aplay
   ├── Check for overdue tasks → alerts
   └── Log: "Holmium signing on."

7. OpenRC service: holmium-tui (1s)
   ├── Plymouth splash dismissed
   ├── Textual TUI on tty1
   ├── Connect to backend via Unix socket
   └── Show status: "Holmium ready — good morning <user>"

8. OpenRC service: holmium-scheduler (1s)
   ├── Load scheduled tasks from /var/holmium/scheduler.json
   ├── Start background asyncio loop (wakes every 60s)
   └── Execute any overdue tasks immediately

9. netsh-monitor (background)
   ├── Monitor WireGuard peer connections
   └── Network quality checks

Total: ~72s (dominant: vLLM model load at ~45s)
```

## Boot Diagnostics

Run silently in step 6. Checks:

| Check | Expected | Critical |
|-------|----------|----------|
| vLLM health | Responds within 30s | Yes |
| LanceDB | Accessible | No (falls back to SQLite) |
| SQLite tables | Exist | Yes |
| Other OS mount | Optional | No |
| WireGuard | Interface up | Yes |
| NTP synced | Within 5s | No |
| ROCm visible | GPU detected | Yes |
| VRAM free | ≥2GB | Yes |
| Disk free | ≥5GB | No |
| Internet | Connectivity | No |

Results logged to `/var/log/holmium/boot_diagnostics.log`.
Critical failures → immediate ntfy.sh notification.

## Boot Greeting

Generated fresh each boot via vLLM. Casual, acknowledges time of day, uses user's name.
Synthesized via Kokoro TTS → played on PC speakers via aplay.
Example: "Morning. Had a good rest? Let's see what's on deck today."
