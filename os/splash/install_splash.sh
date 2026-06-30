#!/bin/bash
set -euo pipefail

# install_splash.sh — Holmium OS Plymouth theme installer
# Installs holmium-theme, rebuilds initramfs.

THEME_NAME="holmium-theme"
THEME_DIR="/usr/share/plymouth/themes/${THEME_NAME}"
SOURCE_DIR="$(dirname "$0")/${THEME_NAME}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "=== Holmium OS Splash Theme Installation ==="

# ---------------------------------------------------------------------------
# 1. Check for Plymouth
# ---------------------------------------------------------------------------
if ! command -v plymouth &>/dev/null; then
    log "ERROR: Plymouth is not installed"
    log "Install plymouth and plymouth-openrc first"
    exit 1
fi

# ---------------------------------------------------------------------------
# 2. Create theme directory
# ---------------------------------------------------------------------------
log "Creating theme directory: ${THEME_DIR}"
mkdir -p "$THEME_DIR"

# ---------------------------------------------------------------------------
# 3. Copy theme files
# ---------------------------------------------------------------------------
if [ -d "$SOURCE_DIR" ]; then
    log "Copying theme files from ${SOURCE_DIR}"
    cp -v "${SOURCE_DIR}"/*.plymouth "$THEME_DIR/" 2>/dev/null || true
    cp -v "${SOURCE_DIR}"/*.script "$THEME_DIR/" 2>/dev/null || true
    cp -v "${SOURCE_DIR}"/*.png "${SOURCE_DIR}"/*.jpg "${SOURCE_DIR}"/*.svg "$THEME_DIR/" 2>/dev/null || true
else
    log "SOURCE_DIR ${SOURCE_DIR} not found — creating minimal theme files"
fi

# ---------------------------------------------------------------------------
# 4. Ensure theme files exist
# ---------------------------------------------------------------------------
if [ ! -f "${THEME_DIR}/${THEME_NAME}.plymouth" ]; then
    log "WARNING: holmium.plymouth not found — creating default"
    cat > "${THEME_DIR}/${THEME_NAME}.plymouth" <<EOF
[Plymouth Theme]
Name=Holmium OS
Description=Holmium OS boot splash
ModuleName=script

[script]
ImageDir=${THEME_DIR}
ScriptFile=${THEME_DIR}/${THEME_NAME}.script
EOF
fi

if [ ! -f "${THEME_DIR}/${THEME_NAME}.script" ]; then
    log "WARNING: holmium.script not found — creating default"
    cat > "${THEME_DIR}/${THEME_NAME}.script" <<EOF
/* Default Holmium OS Plymouth script */
Window.SetBackgroundTopColor(0.0, 0.0, 0.0);
Window.SetBackgroundBottomColor(0.0, 0.0, 0.0);
label = Text("HOLMIUM OS");
label.SetColor(1.0, 1.0, 1.0, 1.0);
label.SetPosition(Window.GetWidth() / 2 - 40, Window.GetHeight() / 2);
label.Show();
EOF
fi

# ---------------------------------------------------------------------------
# 5. Set as default Plymouth theme
# ---------------------------------------------------------------------------
log "Setting ${THEME_NAME} as default Plymouth theme"
plymouth-set-default-theme "$THEME_NAME" 2>/dev/null || {
    # Fallback: manually write to config
    mkdir -p /etc/plymouth
    cat > /etc/plymouth/plymouthd.conf <<EOF
[Daemon]
Theme=${THEME_NAME}
ShowDelay=0
DeviceTimeout=5
EOF
}

# ---------------------------------------------------------------------------
# 6. Verify theme
# ---------------------------------------------------------------------------
if command -v plymouth-set-default-theme &>/dev/null; then
    CURRENT_THEME=$(plymouth-set-default-theme 2>/dev/null || echo "unknown")
    log "Default Plymouth theme: ${CURRENT_THEME}"
fi

# ---------------------------------------------------------------------------
# 7. Rebuild initramfs
# ---------------------------------------------------------------------------
log "Rebuilding initramfs to include Plymouth theme..."
if command -v mkinitcpio &>/dev/null; then
    mkinitcpio -P
    log "initramfs rebuilt"
elif command -v dracut &>/dev/null; then
    dracut --force
    log "initramfs rebuilt (dracut)"
else
    log "WARNING: mkinitcpio not found — rebuild initramfs manually"
fi

# ---------------------------------------------------------------------------
# 8. Enable Plymouth in OpenRC boot
# ---------------------------------------------------------------------------
if command -v rc-update &>/dev/null; then
    rc-update add plymouth boot 2>/dev/null || true
    log "Plymouth OpenRC service enabled at boot level"
fi

log "=== Splash Theme Installation Complete ==="
echo ""
echo "Plymouth theme '${THEME_NAME}' installed at ${THEME_DIR}"
echo "initramfs rebuilt"
