#!/bin/bash
set -euo pipefail

# grub_setup.sh — Holmium OS dual-boot GRUB configuration
# Visible menu with Holmium OS (default) + Debian via os-prober.

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "=== Holmium OS GRUB Setup (Dual Boot) ==="

# Determine Holmium root partition by label or UUID
HOLMIUM_ROOT_PART=$(blkid -L "holmium-root" 2>/dev/null || echo "")
if [ -z "$HOLMIUM_ROOT_PART" ]; then
    log "WARNING: holmium-root partition not found by label"
fi
log "Holmium root partition: ${HOLMIUM_ROOT_PART:-not found}"

HOLMIUM_UUID=""
if [ -n "$HOLMIUM_ROOT_PART" ]; then
    HOLMIUM_UUID=$(blkid -s UUID -o value "$HOLMIUM_ROOT_PART" 2>/dev/null || echo "")
fi

# Enable os-prober in /etc/default/grub
GRUB_DEFAULT_FILE="/etc/default/grub"
if [ -f "$GRUB_DEFAULT_FILE" ]; then
    log "Updating ${GRUB_DEFAULT_FILE} for dual boot"
    sed -i 's/^GRUB_DEFAULT=.*/GRUB_DEFAULT=holmium-os/' "$GRUB_DEFAULT_FILE"
    sed -i 's/^GRUB_TIMEOUT=.*/GRUB_TIMEOUT=5/' "$GRUB_DEFAULT_FILE"
    sed -i 's/^GRUB_TIMEOUT_STYLE=.*/GRUB_TIMEOUT_STYLE=menu/' "$GRUB_DEFAULT_FILE"
    sed -i 's/^#GRUB_GFXMODE=.*/GRUB_GFXMODE=1920x1080/' "$GRUB_DEFAULT_FILE"
    sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT=.*/GRUB_CMDLINE_LINUX_DEFAULT="quiet loglevel=3 plymouth.enable=1"/' "$GRUB_DEFAULT_FILE"

    grep -q '^GRUB_DEFAULT=' "$GRUB_DEFAULT_FILE" || echo 'GRUB_DEFAULT=holmium-os' >> "$GRUB_DEFAULT_FILE"
    grep -q '^GRUB_TIMEOUT=' "$GRUB_DEFAULT_FILE" || echo 'GRUB_TIMEOUT=5' >> "$GRUB_DEFAULT_FILE"
    grep -q '^GRUB_TIMEOUT_STYLE=' "$GRUB_DEFAULT_FILE" || echo 'GRUB_TIMEOUT_STYLE=menu' >> "$GRUB_DEFAULT_FILE"

    # Enable os-prober
    if grep -q '^GRUB_DISABLE_OS_PROBER=' "$GRUB_DEFAULT_FILE"; then
        sed -i 's/^GRUB_DISABLE_OS_PROBER=.*/GRUB_DISABLE_OS_PROBER=false/' "$GRUB_DEFAULT_FILE"
    else
        echo 'GRUB_DISABLE_OS_PROBER=false' >> "$GRUB_DEFAULT_FILE"
    fi
fi

# Write /etc/grub.d/40_holmium_custom — Holmium OS entry
CUSTOM_GRUB="/etc/grub.d/40_holmium_custom"
log "Writing ${CUSTOM_GRUB}"

cat > "$CUSTOM_GRUB" <<'GRUBHEADER'
#!/bin/sh
# 40_holmium_custom — Holmium OS GRUB entry (default)
GRUBHEADER

cat >> "$CUSTOM_GRUB" <<'GRUBSETTINGS'
set menu_color_normal=cyan/black
set menu_color_highlight=black/cyan
set color_normal=white/black
set color_highlight=white/black
GRUBSETTINGS

if [ -n "$HOLMIUM_UUID" ]; then
    cat >> "$CUSTOM_GRUB" <<EOF
menuentry "Holmium OS" --id holmium-os {
    set root_uuid=${HOLMIUM_UUID}
    search --fs-uuid --no-floppy --set=root \${root_uuid}
    linux /boot/vmlinuz-linux root=UUID=${HOLMIUM_UUID} rw quiet loglevel=3 vt.global_cursor_default=0 plymouth.enable=1
    initrd /boot/initramfs-linux.img
}
EOF
else
    cat >> "$CUSTOM_GRUB" <<EOF
menuentry "Holmium OS" --id holmium-os {
    search --label --no-floppy --set=root holmium-root
    linux /boot/vmlinuz-linux root=LABEL=holmium-root rw quiet loglevel=3 vt.global_cursor_default=0 plymouth.enable=1
    initrd /boot/initramfs-linux.img
}
EOF
fi

# Add Debian installer entry (loopback from included ISO)
DEBIAN_ISO_PATH="/usr/share/holmium/debian-netinst.iso"
if [ -f "$DEBIAN_ISO_PATH" ]; then
    log "Adding Debian installer GRUB entry (loopback)"
    cat >> "$CUSTOM_GRUB" <<EOF

menuentry "Install Debian (from included ISO)" --id debian-installer {
    search --label --no-floppy --set=root holmium-root
    loopback loop ${DEBIAN_ISO_PATH}
    linux (loop)/install.amd/vmlinuz video=vesafb vga=788 --- quiet
    initrd (loop)/install.amd/initrd.gz
}
menuentry "Install Debian (graphical) (from included ISO)" --id debian-installer-gtk {
    search --label --no-floppy --set=root holmium-root
    loopback loop ${DEBIAN_ISO_PATH}
    linux (loop)/install.amd/gtk/vmlinuz video=vesafb vga=788 --- quiet
    initrd (loop)/install.amd/gtk/initrd.gz
}
EOF
else
    log "WARNING: Debian ISO not found at ${DEBIAN_ISO_PATH}, skipping loopback entry"
fi

chmod 755 "$CUSTOM_GRUB"
log "${CUSTOM_GRUB} written"

# Regenerate GRUB config (os-prober will find Debian)
log "Regenerating GRUB configuration with os-prober..."
if command -v grub-mkconfig &>/dev/null; then
    grub-mkconfig -o /boot/grub/grub.cfg
    log "GRUB configuration regenerated"
else
    log "WARNING: grub-mkconfig not found"
fi

log "=== GRUB Setup Complete ==="
echo ""
echo "Boot: Dual boot with GRUB menu (5s timeout)"
echo "  Default: Holmium OS"
echo "  Debian installer: loopback from included ISO (auto-launched on first boot)"
echo "  Debian system: auto-detected by os-prober (once installed)"
echo ""
echo "To manually regenerate after installing Debian:"
echo "  sudo grub-mkconfig -o /boot/grub/grub.cfg"
