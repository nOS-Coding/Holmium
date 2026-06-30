#!/bin/bash
set -euo pipefail

# configure_wifi.sh — Holmium OS WiFi setup via NetworkManager
# Usage: ./configure_wifi.sh <SSID> <password>
# Writes NM connection profile to /etc/NetworkManager/system-connections/holmium-wifi.nmconnection
# Auto-connect on boot, reconnect on drop.

if [ $# -lt 2 ]; then
    echo "Usage: $0 <SSID> <password>"
    exit 1
fi

SSID="$1"
PASSWORD="$2"
CONN_DIR="/etc/NetworkManager/system-connections"
CONN_FILE="${CONN_DIR}/holmium-wifi.nmconnection"
UUID="$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null || echo "$(date +%s)-$$")"

mkdir -p "$CONN_DIR"

cat > "$CONN_FILE" <<EOF
[connection]
id=holmium-wifi
uuid=${UUID}
type=wifi
interface-name=wlan0
autoconnect=true
autoconnect-priority=10
permissions=

[wifi]
mode=infrastructure
ssid=${SSID}
hidden=false
mac-address-blacklist=

[wifi-security]
key-mgmt=wpa-psk
psk=${PASSWORD}

[ipv4]
method=auto

[ipv6]
method=auto
EOF

chown root:root "$CONN_FILE"
chmod 600 "$CONN_FILE"

echo "WiFi profile written to ${CONN_FILE}"
echo "Auto-connect enabled for SSID: ${SSID}"

# Reload NetworkManager profiles
if command -v nmcli &>/dev/null; then
    nmcli connection reload
    echo "NetworkManager profiles reloaded"
fi
