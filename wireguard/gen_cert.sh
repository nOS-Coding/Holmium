#!/usr/bin/env bash
set -euo pipefail

TLS_DIR="/etc/holmium/tls"
mkdir -p "$TLS_DIR"

openssl req -x509 -nodes -days 3650 -newkey rsa:4096 \
  -keyout "$TLS_DIR/holmium.key" \
  -out "$TLS_DIR/holmium.crt" \
  -subj "/CN=holmium.local/O=Holmium OS/C=US" \
  -addext "subjectAltName=DNS:holmium.local,IP:10.0.0.1"

chmod 600 "$TLS_DIR/holmium.key"
chmod 644 "$TLS_DIR/holmium.crt"

echo "Self-signed TLS certificate generated (10-year validity)."
echo "  Cert: $TLS_DIR/holmium.crt"
echo "  Key:  $TLS_DIR/holmium.key"
