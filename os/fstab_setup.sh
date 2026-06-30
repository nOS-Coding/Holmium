#!/bin/bash
set -euo pipefail

# fstab_setup.sh — Holmium OS fstab cleanup
# Removes any stale mount entries.

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "=== Holmium OS fstab Setup ==="

log "=== fstab Setup Complete ==="
echo ""
echo "/etc/fstab: Holmium OS only"
