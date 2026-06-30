#!/usr/bin/env bash
set -euo pipefail

print_green() { printf "\033[1;32m%s\033[0m\n" "$1"; }
print_cyan()  { printf "\033[1;36m%s\033[0m\n" "$1"; }
print_red()   { printf "\033[1;31m%s\033[0m\n" "$1"; }

print_cyan "Holmium CLI Installer — Linux"
echo ""

# Check platform
if [[ "$(uname)" == "Darwin" ]]; then
    print_red "This installer is for Linux only. Use the native Holmium app on macOS."
    exit 1
fi

# Check Python
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1 | awk '{print $2}')
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; }; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    print_red "Error: Python 3.10+ is required but not found."
    exit 1
fi

print_green "Found: $($PYTHON --version)"

# Install dependencies
print_cyan "Installing Python dependencies..."
$PYTHON -m pip install --quiet --upgrade pip 2>/dev/null || true
$PYTHON -m pip install --quiet httpx websockets rich textual 2>/dev/null || true

if [ $? -ne 0 ]; then
    print_red "pip install failed. Try: pip install httpx websockets rich textual"
    exit 1
fi

print_green "Dependencies installed."

# Install holmium command + TUI module
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
print_cyan "Installing holmium command to /usr/local/bin/holmium..."

if [ -f "$SCRIPT_DIR/holmium.py" ]; then
    cp "$SCRIPT_DIR/holmium.py" /usr/local/bin/holmium
    chmod +x /usr/local/bin/holmium
    # Copy TUI module alongside the script
    cp "$SCRIPT_DIR/tui_client.py" /usr/local/bin/tui_client.py
    cp "$SCRIPT_DIR/renderer.py" /usr/local/bin/renderer.py 2>/dev/null || true
    print_green "Installed from $SCRIPT_DIR"
else
    print_red "holmium.py not found in $SCRIPT_DIR"
    exit 1
fi

# Create config directory (~/.config/holmium/config.json)
CONFIG_DIR="$HOME/.config/holmium"
mkdir -p "$CONFIG_DIR"

if [ ! -f "$CONFIG_DIR/config.json" ]; then
    echo ""
    print_cyan "Configuration"
    echo "Holmium needs a server IP address and auth token."
    echo ""

    read -r -p "Server IP (e.g. 10.0.0.1): " SERVER_IP
    read -r -p "Auth Token (leave empty if none): " AUTH_TOKEN
    read -r -p "Port [443]: " PORT
    PORT="${PORT:-443}"

    cat > "$CONFIG_DIR/config.json" <<EOF
{
  "server": "${SERVER_IP:-10.0.0.1}",
  "port": ${PORT},
  "token": "${AUTH_TOKEN}",
  "user_name": "$(whoami)"
}
EOF

    chmod 600 "$CONFIG_DIR/config.json"
    print_green "Configuration saved to $CONFIG_DIR/config.json"
else
    print_green "$CONFIG_DIR/config.json already exists — skipping config."
fi

echo ""
print_green "Installation complete!"
echo ""
print_cyan "Usage:"
echo "  holmium                Launch Textual TUI (default)"
echo "  holmium status         System status"
echo "  holmium send file.jpg  Send a picture or file"
echo "  holmium chat 'hello'   One-shot message"
echo "  holmium --help         All commands"
echo ""
