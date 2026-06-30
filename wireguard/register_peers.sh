#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(dirname "$0")"
KEY_DIR="$SCRIPT_DIR/keys"
CLIENT_DIR="$SCRIPT_DIR/clients"
SERVER_PUB=$(cat "$KEY_DIR/server.pub")

mkdir -p "$CLIENT_DIR"

# Mac peer — split tunnel (Holmium only)
MAC_KEY="$KEY_DIR/mac.key"
wg genkey | tee "$MAC_KEY" | wg pubkey > "$KEY_DIR/mac.pub"
MAC_PUB=$(cat "$KEY_DIR/mac.pub")

# Android peer — full tunnel
ANDROID_KEY="$KEY_DIR/android.key"
wg genkey | tee "$ANDROID_KEY" | wg pubkey > "$KEY_DIR/android.pub"
ANDROID_PUB=$(cat "$KEY_DIR/android.pub")

cat >> /etc/wireguard/wg0.conf <<EOF

# Mac
[Peer]
PublicKey = $MAC_PUB
AllowedIPs = 10.0.0.2/32

# Android
[Peer]
PublicKey = $ANDROID_PUB
AllowedIPs = 10.0.0.3/32
EOF

cat > "$CLIENT_DIR/mac.conf" <<EOF
[Interface]
PrivateKey = $(cat "$MAC_KEY")
Address = 10.0.0.2/32
DNS = 10.0.0.1

[Peer]
PublicKey = $SERVER_PUB
Endpoint = $(ip route get 1 | awk '{print $5; exit}'):51820
AllowedIPs = 10.0.0.0/24
PersistentKeepalive = 25
EOF

cat > "$CLIENT_DIR/android.conf" <<EOF
[Interface]
PrivateKey = $(cat "$ANDROID_KEY")
Address = 10.0.0.3/32
DNS = 10.0.0.1

[Peer]
PublicKey = $SERVER_PUB
Endpoint = $(ip route get 1 | awk '{print $5; exit}'):51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
EOF

echo "Peers registered."
echo ""
echo "=== Android Config QR Code ==="
qrencode -t ansiutf8 < "$CLIENT_DIR/android.conf"

echo ""
echo "Mac config:  $CLIENT_DIR/mac.conf"
echo "Android config: $CLIENT_DIR/android.conf"
