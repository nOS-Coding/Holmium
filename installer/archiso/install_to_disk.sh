#!/bin/bash
# Holmium OS Installer — runs from the USB live environment
# Partitions the target drive and installs Holmium OS to it.
# Leaves free space for another OS (e.g. Debian).

set -e

TARGET_DISK="${1:-/dev/nvme0n1}"
GPU_PACKAGES="${HOLMIUM_GPU_PACKAGES:-nvidia-dkms nvidia-utils cuda}"
HOLMIUM_TARBALL="/usr/share/holmium/holmium-os.tar.xz"
MOUNT="/mnt"
HOLMIUM_SIZE_GiB=900
SWAP_SIZE_GiB=16
ROOT_SIZE_GiB=$((HOLMIUM_SIZE_GiB - SWAP_SIZE_GiB))

echo "============================================"
echo "  Holmium OS Installer — Dual Boot"
echo "  Target: ${TARGET_DISK}"
echo "  Holmium:  ${HOLMIUM_SIZE_GiB}GiB  |  Debian: rest of disk"
echo "============================================"
echo ""
echo "WARNING: This will DESTROY ALL DATA on ${TARGET_DISK}"
echo "Press Ctrl+C to abort, or Enter to continue..."
read -r

# Partition layout (shared ESP for dual boot):
#   p1: ESP vfat      512MiB     (shared with Debian)
#   p2: Holmium root    ext4       rest of Holmium's 900GiB minus 16GiB swap
#   p3: Holmium swap    linux-swap 16GiB
#   free: remaining space for Debian installer
echo "==> Partitioning ${TARGET_DISK}..."
parted "$TARGET_DISK" -- mklabel gpt
parted "$TARGET_DISK" -- mkpart ESP fat32 1MiB 513MiB
parted "$TARGET_DISK" -- set 1 esp on
parted "$TARGET_DISK" -- mkpart primary ext4 513MiB "${ROOT_SIZE_GiB}GiB"
parted "$TARGET_DISK" -- mkpart primary linux-swap "${ROOT_SIZE_GiB}GiB" "${HOLMIUM_SIZE_GiB}GiB"

echo "==> Formatting partitions..."
mkfs.vfat -F32 "${TARGET_DISK}p1"
mkfs.ext4 -L holmium-root "${TARGET_DISK}p2"
mkswap -L holmium-swap "${TARGET_DISK}p3"

echo "==> Mounting..."
mount "${TARGET_DISK}p2" "$MOUNT"
mkdir -p "$MOUNT/boot"
mount "${TARGET_DISK}p1" "$MOUNT/boot"

echo "==> Installing base system via pacstrap..."
pacstrap "$MOUNT" base linux linux-firmware grub efibootmgr os-prober openrc eudev networkmanager wireguard-tools python python-pip git vim htop chrony plymouth tzdata dosfstools $GPU_PACKAGES

echo "==> Generating fstab..."
genfstab -U "$MOUNT" >> "$MOUNT/etc/fstab"

echo "==> Extracting Holmium OS files..."
if [ -f "$HOLMIUM_TARBALL" ]; then
    tar -xJf "$HOLMIUM_TARBALL" -C "$MOUNT" --strip-components=1
else
    echo "FATAL: Holmium OS tarball not found at ${HOLMIUM_TARBALL}"
    echo "The USB installer is incomplete. Rebuild the ISO."
    exit 1
fi

echo "==> Copying Debian netinst ISO to installed system..."
DEBIAN_ISO_SRC="/usr/share/holmium/debian-netinst.iso"
if [ -f "$DEBIAN_ISO_SRC" ]; then
    mkdir -p "$MOUNT/usr/share/holmium"
    cp "$DEBIAN_ISO_SRC" "$MOUNT/usr/share/holmium/debian-netinst.iso"
    echo "  Debian ISO copied (will be available for GRUB loopback)"
else
    echo "  WARNING: Debian ISO not found in live environment at ${DEBIAN_ISO_SRC}"
fi

echo "==> Chrooting for system configuration..."
arch-chroot "$MOUNT" /bin/bash << 'CHROOT'
    echo "==> Running Holmium OS setup..."
    if [ -f /usr/lib/holmium/setup.sh ]; then
        bash /usr/lib/holmium/setup.sh
    elif [ -f /opt/holmium/os/setup.sh ]; then
        bash /opt/holmium/os/setup.sh
    else
        echo "WARNING: setup.sh not found — running manual setup"
    fi

    echo "==> Installing GRUB..."
    grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=Holmium --recheck

    echo "==> Running GRUB configuration (dual boot)..."
    for grub_script in /os/grub_setup.sh /usr/lib/holmium/grub_setup.sh /opt/holmium/os/grub_setup.sh; do
        if [ -f "$grub_script" ]; then
            bash "$grub_script"
            break
        fi
    done

    echo "==> Setting Debian installer as default for first boot..."
    grub-reboot debian-installer 2>/dev/null || true

    echo "==> Generating initramfs..."
    mkinitcpio -P

    echo "==> Disabling root password..."
    passwd -dl root || true

    echo "==> Enabling Holmium OpenRC services..."
    rc-update add holmium-wireguard default 2>/dev/null || true
    rc-update add holmium-vllm default 2>/dev/null || true
    rc-update add holmium-backend default 2>/dev/null || true
    rc-update add holmium-tui default 2>/dev/null || true
    rc-update add holmium-scheduler default 2>/dev/null || true
    rc-update add netsh-monitor default 2>/dev/null || true
CHROOT

echo "==> Unmounting..."
umount -R "$MOUNT"

echo ""
echo "============================================"
echo "  Holmium OS installed successfully!"
echo "  Target: ${TARGET_DISK}"
echo "  Partition layout:"
echo "    p1: ESP       512MiB  (shared)"
echo "    p2: root       ${ROOT_SIZE_GiB}GiB  (holmium-root)"
echo "    p3: swap       16GiB  (holmium-swap)"
echo "    free:          rest of disk (for Debian)"
echo ""
echo "  Next steps:"
echo "    1. Reboot (Debian installer will launch automatically on first boot)"
echo "    2. Complete Debian installation in the free space"
echo "    3. Debian's installer will detect the shared ESP"
echo "    4. Tom's GRUB will auto-detect Debian via os-prober"
echo "============================================"
