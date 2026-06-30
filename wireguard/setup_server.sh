#!/usr/bin/env bash
set -euo pipefail

KEY_DIR="$(dirname "$0")/keys"
mkdir -p "$KEY_DIR"

wg genkey | tee "$KEY_DIR/server.key" | wg pubkey > "$KEY_DIR/server.pub"

cat > /etc/wireguard/wg0.conf <<EOF
[Interface]
Address = 10.0.0.1/24
ListenPort = 51820
PrivateKey = $(cat "$KEY_DIR/server.key")

PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o $(ip route get 1 | awk '{print $5; exit}') -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o $(ip route get 1 | awk '{print $5; exit}') -j MASQUERADE
EOF

sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv4.conf.all.forwarding=1
sed -i 's/^#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/' /etc/sysctl.conf 2>/dev/null || true
grep -q '^net.ipv4.ip_forward=1' /etc/sysctl.conf 2>/dev/null || echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf

echo "WireGuard server setup complete."
echo "Server public key: $(cat "$KEY_DIR/server.pub")"
