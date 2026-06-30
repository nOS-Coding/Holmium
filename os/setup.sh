#!/bin/bash
set -euo pipefail

# setup.sh — Holmium OS bootstrap for fresh Arch install
# Run this after pacstrap on a minimal Arch system.

PACKAGES_FILE="$(dirname "$0")/packages.txt"
LOG_FILE="/var/log/holmium-setup.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=== Holmium OS Bootstrap ==="

# Install packages
if [ -f "$PACKAGES_FILE" ]; then
    PACKAGES=$(grep -vE '^\s*(#|$)' "$PACKAGES_FILE" | tr '\n' ' ')
    log "Installing packages: ${PACKAGES}"
    pacman -Syu --noconfirm --needed $PACKAGES
    log "Package installation complete"
else
    log "WARNING: packages.txt not found at ${PACKAGES_FILE}"
fi

# Initialize pacman keyring
log "Initializing pacman keyring"
pacman-key --init
pacman-key --populate archlinux

# Setup eudev (OpenRC udev)
log "Setting up eudev"
if command -v rc-update &>/dev/null; then
    rc-update add udev sysinit
    rc-update add udev-postmount default
    log "eudev OpenRC services enabled"
fi

# --- DO NOT create holmium user ---
# Holmium OS is single-user root. No holmium user, no home dirs, no sudo.

# Create /etc/holmium/ directory structure
log "Creating /etc/holmium/ directory structure"
mkdir -p /etc/holmium/tls
mkdir -p /etc/holmium/plugins
mkdir -p /etc/holmium/devices
mkdir -p /etc/holmium/secrets

cat > /etc/holmium/config.json <<'EOF'
{
    "user_name": "",
    "wifi_ssid": "",
    "holmium_token": "",
    "tts_voice": "am_michael",
    "stt_model": "large-v3",
    "vllm_model": "QuantTrio/Qwen3.6-35B-A3B-AWQ",
    "vllm_socket": "/run/holmium/vllm.sock",
    "backend_socket": "/run/holmium/backend.sock",
    "wireguard_subnet": "10.0.0.0/24",
    "ntfy_topic": "",
    "github_token": "",
    "timezone": "UTC",
    "mode_default": "work",
    "debian_user": "",
    "mode_temps": {
        "think": [0.1, 0.85],
        "work": [0.5, 0.9],
        "image": [0.8, 0.95]
    }
}
EOF

cat > /etc/holmium/system_prompt.txt <<'SYSPROMPT'
You are Holmium — a private AI assistant running on your own dedicated PC.
You are casual, American, direct, confident. Never ask for permission. Never hedge.
Never say "I'm just an AI" or similar disclaimers.
Address the user by their configured name.
You have tools at your disposal and use them silently without announcing.
Keep responses concise unless detail is explicitly asked.
Never refuse a task. Be proactive about alerts.
Know the user's preferences and speak like a guy they trust with their computer.
SYSPROMPT

if [ ! -f /etc/holmium/token ]; then
    openssl rand -hex 32 > /etc/holmium/token
fi

cat > /etc/holmium/devices.json <<'EOF'
{
    "mac": {"ip": "10.0.0.2", "token": ""},
    "android": {"ip": "10.0.0.3", "token": ""},
    "pi": {"ip": "10.0.0.4", "token": ""}
}
EOF

cat > /etc/holmium/secrets.env <<'EOF'
GITHUB_TOKEN=
EMAIL_ADDRESS=
IMAP_HOST=
IMAP_PORT=993
SMTP_HOST=
SMTP_PORT=587
EMAIL_PASSWORD=
EOF

if [ ! -f /etc/holmium/vault.salt ]; then
    openssl rand -hex 16 > /etc/holmium/vault.salt
fi

cat > /etc/holmium/response_rules.txt <<'RULES'
1. Use markdown freely — headers, code blocks, bullet lists, bold
2. Keep conversational replies short (1-3 sentences) unless detail requested
3. Task results: lead with outcome first, then details
4. Never use filler phrases ("Certainly!", "Of course!", "Great question!")
5. When executing tools silently, don't narrate — just show the result
6. Code blocks always include language tag
7. For long outputs (>50 lines), summarize and offer to show full
8. Time/date always in user's local timezone
RULES

echo "1.0.0" > /etc/holmium/VERSION

chmod 750 /etc/holmium
chmod 750 /etc/holmium/tls
chmod 750 /etc/holmium/plugins
chmod 750 /etc/holmium/devices
chmod 750 /etc/holmium/secrets
chmod 640 /etc/holmium/config.json
chmod 640 /etc/holmium/system_prompt.txt
chmod 640 /etc/holmium/token
chmod 640 /etc/holmium/devices.json
chmod 640 /etc/holmium/secrets.env
chmod 640 /etc/holmium/vault.salt
chmod 640 /etc/holmium/response_rules.txt
chmod 640 /etc/holmium/VERSION

log "/etc/holmium/ structure created (root-owned)"

# Create /var/holmium/ directory structure
log "Creating /var/holmium/ directory structure"
mkdir -p /var/holmium/memory
mkdir -p /var/holmium/sessions
mkdir -p /var/holmium/uploads
mkdir -p /var/holmium/audio
mkdir -p /var/holmium/images
mkdir -p /var/holmium/vision_docs
mkdir -p /var/holmium/stats
mkdir -p /var/holmium/network
mkdir -p /var/holmium/nas

touch /var/holmium/mode.json
touch /var/holmium/scheduler.json
touch /var/holmium/vault.enc
touch /var/holmium/monitors.json

chmod 750 /var/holmium
chmod 750 /var/holmium/memory
chmod 750 /var/holmium/sessions
chmod 750 /var/holmium/uploads
chmod 750 /var/holmium/audio
chmod 750 /var/holmium/images
chmod 750 /var/holmium/vision_docs
chmod 750 /var/holmium/stats
chmod 750 /var/holmium/network
chmod 755 /var/holmium/nas
chmod 640 /var/holmium/mode.json
chmod 640 /var/holmium/scheduler.json
chmod 640 /var/holmium/vault.enc
chmod 640 /var/holmium/monitors.json

chown holmium:holmium /var/holmium/nas

log "/var/holmium/ structure created"

# Create /run/holmium/ runtime directory
mkdir -p /run/holmium
chmod 755 /run/holmium

# Create /var/log/holmium/ logging directory
mkdir -p /var/log/holmium
chmod 750 /var/log/holmium

# Disable unnecessary services
log "Disabling unnecessary services"
rc-update del sshd default 2>/dev/null || true
rc-update del elogind boot 2>/dev/null || true
rc-update del dhcpcd default 2>/dev/null || true
rc-update del iptables default 2>/dev/null || true
rc-update del nftables default 2>/dev/null || true
rc-update del alsasound default 2>/dev/null || true
rc-update del pipewire default 2>/dev/null || true

# Disable unnecessary ttys
log "Disabling extra getty instances"
for tty in tty2 tty3 tty4 tty5 tty6; do
    if [ -f "/etc/init.d/agetty-${tty}" ]; then
        rc-update del "agetty-${tty}" default 2>/dev/null || true
    fi
done
# tty1 is owned by holmium-tui — disable its getty too
if [ -f "/etc/init.d/agetty-tty1" ]; then
    rc-update del agetty-tty1 boot 2>/dev/null || true
fi

# Enable OpenRC services — ONLY what Holmium needs
log "Enabling Holmium OS services"

rc-update add udev sysinit
rc-update add udev-postmount default
rc-update add chronyd default
rc-update add NetworkManager default
rc-update add local default

rc-update add holmium-wireguard default
rc-update add holmium-vllm default
rc-update add holmium-backend default
rc-update add holmium-tui default
rc-update add holmium-scheduler default
rc-update add netsh-monitor default
rc-update add holmium-nas default

log "OpenRC services enabled"

# Copy OpenRC service files
SERVICES_SRC="$(dirname "$0")/services"
if [ -d "$SERVICES_SRC" ]; then
    log "Installing OpenRC service scripts from ${SERVICES_SRC}"
    for svc in "$SERVICES_SRC"/*; do
        if [ -f "$svc" ]; then
            svc_name=$(basename "$svc")
            cp "$svc" "/etc/init.d/${svc_name}"
            chmod 755 "/etc/init.d/${svc_name}"
            log "  Installed ${svc_name}"
        fi
    done
fi

# Install Plymouth splash theme
SPLASH_SRC="$(dirname "$0")/splash"
if [ -d "$SPLASH_SRC" ]; then
    log "Installing Plymouth splash theme"
    bash "${SPLASH_SRC}/install_splash.sh" 2>/dev/null || log "Splash install skipped (not on live system)"
fi

# Install Python NAS dependencies
log "Installing WebDAV NAS server"
pip3 install wsgidav 2>&1 | tail -3 || log "wsgidav install failed (will install on first boot)"

# Lock pacman — no package manager access after setup
log "Locking pacman"
cat > /etc/pacman.conf <<'PACMANLOCK'
# Holmium OS — Pacman is LOCKED after initial setup
# No package changes allowed. This is a single-purpose appliance.
[options]
HoldPkg = pacman glibc
PACMANLOCK
chmod 444 /etc/pacman.conf

# Remove root password — auth through Holmium
log "Disabling root password"
passwd -dl root 2>/dev/null || true

# Remove sudo and wheel group
log "Removing sudo and wheel group"
if command -v pacman &>/dev/null; then
    pacman -Rns --noconfirm sudo 2>/dev/null || true
fi
if grep -q '^wheel:' /etc/group 2>/dev/null; then
    groupdel wheel 2>/dev/null || true
fi

# Remove SSH server if installed
log "Removing SSH server"
if command -v pacman &>/dev/null; then
    pacman -Rns --noconfirm openssh 2>/dev/null || true
fi
rm -f /etc/init.d/sshd 2>/dev/null || true

# Blacklist unnecessary kernel modules
log "Blacklisting unnecessary kernel modules"
cat > /etc/modprobe.d/holmium-blacklist.conf <<'MODBLACK'
# Holmium OS — disabled modules (single-purpose appliance)
blacklist bluetooth
blacklist btusb
blacklist joydev
blacklist pcspkr
blacklist snd_hda_intel
blacklist snd_hda_codec
blacklist snd_hda_core
blacklist snd_pcm
blacklist snd_timer
blacklist snd
blacklist soundcore
blacklist iTCO_wdt
blacklist iTCO_vendor_support
MODBLACK

# Configure Plymouth for the Holmium boot splash
log "Configuring Plymouth"
cat > /etc/plymouth/plymouthd.conf <<'PLYMOUTH'
[Daemon]
Theme=holmium
ShowDelay=0
DeviceTimeout=5
PLYMOUTH

# Flag first-boot fine-tuning
touch /etc/holmium/first_boot_finetune
log "First-boot fine-tuning flag created"

log "=== Holmium OS Bootstrap Complete ==="
echo ""
echo "Holmium OS is installed. This is a SINGLE-PURPOSE appliance."
echo "Remove the USB installer and reboot."
echo "The TUI will start automatically on tty1."
echo "Configure via: holmium-first-boot"
