#!/bin/bash
set -euo pipefail

# set_timezone.sh — Holmium OS timezone setup
# Usage: ./set_timezone.sh [timezone]
# Default: UTC

TZ="${1:-UTC}"
ZONEINFO="/usr/share/zoneinfo/${TZ}"

if [ ! -f "$ZONEINFO" ]; then
    echo "ERROR: Timezone file not found: ${ZONEINFO}"
    echo "Usage: $0 [timezone]"
    echo "Example: $0 UTC"
    exit 1
fi

ln -sf "$ZONEINFO" /etc/localtime

echo "Timezone set to: ${TZ}"
echo "  $(date)"

# Also write timezone to config.json if it exists
CONFIG_FILE="/etc/holmium/config.json"
if [ -f "$CONFIG_FILE" ]; then
    # Use python for safe JSON editing if available, otherwise sed
    if command -v python &>/dev/null; then
        python -c "
import json
with open('${CONFIG_FILE}', 'r') as f:
    config = json.load(f)
config['timezone'] = '${TZ}'
with open('${CONFIG_FILE}', 'w') as f:
    json.dump(config, f, indent=4)
"
    fi
    echo "Updated timezone in ${CONFIG_FILE}"
fi
