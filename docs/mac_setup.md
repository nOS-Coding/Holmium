# macOS Setup Guide

## Prerequisites
- macOS 12+ (Monterey or later)
- Homebrew (recommended)
- Python 3.10+

## Step 1: WireGuard

1. Install WireGuard:
   ```bash
   brew install wireguard-tools
   ```
2. Copy the Mac client config from the first-run wizard:
   ```bash
   # Contents of wireguard/clients/mac.conf:
   [Interface]
   PrivateKey = <private key from wizard>
   Address = 10.0.0.2/32
   DNS = 10.0.0.1
   
   [Peer]
   PublicKey = <server public key>
   AllowedIPs = 10.0.0.0/24
   Endpoint = <server-public-ip>:51820
   PersistentKeepalive = 25
   ```
3. Save to `/usr/local/etc/wireguard/holmium.conf`
4. Connect: `wg-quick up holmium`

## Step 2: Install Holmium CLI

```bash
curl -sSf https://holmium.local/install.sh | bash
# OR from the source:
cd holmium-cmd
chmod +x install.sh
./install.sh
```

The installer will:
- Check Python 3.10+
- Install pip packages (httpx, websockets, rich)
- Copy `holmium.py` to `/usr/local/bin/holmium`
- Prompt for Holmium PC's WG IP + auth token
- Write `~/.netsh/hosts.json`

## Step 3: Start Daemon (Background Notifications)

```bash
holmium-daemon &
# Or add to Login Items in System Settings
```

The daemon:
- Maintains persistent WebSocket to Holmium
- Displays native macOS notifications
- Handles clipboard commands
- Receives files from Holmium

## Usage

```bash
holmium                    # Interactive REPL shell
holmium status             # Dashboard
holmium status -l          # Stream logs
holmium send file.txt remote_path  # Upload
holmium briefing           # Spoken briefing
```

## Auto-Start

Add to macOS Login Items:
1. System Settings → General → Login Items
2. Add `holmium-daemon` and WireGuard
