#!/bin/bash
set -euo pipefail

# ntp_setup.sh — Holmium OS NTP / Chrony setup
# Installs chrony, configures pool.ntp.org, enables chronyd OpenRC service.

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "=== Holmium OS NTP Setup ==="

# ---------------------------------------------------------------------------
# 1. Install chrony if not present
# ---------------------------------------------------------------------------
if ! command -v chronyd &>/dev/null; then
    log "Installing chrony"
    pacman -Syu --noconfirm chrony
fi

# ---------------------------------------------------------------------------
# 2. Configure /etc/chrony/chrony.conf
# ---------------------------------------------------------------------------
log "Configuring /etc/chrony/chrony.conf"
cat > /etc/chrony/chrony.conf <<'EOF'
# Holmium OS — Chrony NTP configuration

# Use pool.ntp.org servers
pool 0.pool.ntp.org iburst
pool 1.pool.ntp.org iburst
pool 2.pool.ntp.org iburst
pool 3.pool.ntp.org iburst

# Local clock fallback
local stratum 10

# Logging
logdir /var/log/chrony

# Serve time to local network (WireGuard subnet)
allow 10.0.0.0/24

# Make chrony step the system clock if offset > 1 second
makestep 1.0 3

# NTP client port
port 123

# RTC synchronization
rtcsync
EOF

# ---------------------------------------------------------------------------
# 3. Create chrony log directory
# ---------------------------------------------------------------------------
mkdir -p /var/log/chrony
chown root:root /var/log/chrony
chmod 755 /var/log/chrony

# ---------------------------------------------------------------------------
# 4. Enable and start chronyd OpenRC service
# ---------------------------------------------------------------------------
if command -v rc-update &>/dev/null; then
    rc-update add chronyd default
    log "chronyd added to default runlevel"
fi

if command -v rc-service &>/dev/null; then
    rc-service chronyd start 2>/dev/null || log "chronyd will start on next boot"
fi

log "=== NTP Setup Complete ==="
chronyc tracking 2>/dev/null | head -5 || log "chronyd not yet running — will sync on boot"
