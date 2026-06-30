#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <pi_public_key>"
  exit 1
fi

PI_PUB="$1"

cat >> /etc/wireguard/wg0.conf <<EOF

# Pi
[Peer]
PublicKey = $PI_PUB
AllowedIPs = 10.0.0.4/32
EOF

echo "Pi peer (10.0.0.4) added to /etc/wireguard/wg0.conf"
echo "Restart WireGuard to apply: wg syncconf wg0 <(wg-quick strip wg0)"
