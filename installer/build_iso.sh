#!/usr/bin/env bash
set -euo pipefail

# Holmium OS ISO Builder with variant support
# Usage: ./build_iso.sh [--variant nvidia-std|nvidia-pro|amd] [--debian-iso path]

DATE=$(date +%Y%m%d)
PROFILE_DIR="$(cd "$(dirname "$0")/archiso" && pwd)"
VARIANT="nvidia-std"
DEBIAN_ISO=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --variant)
            VARIANT="$2"
            shift 2
            ;;
        --debian-iso)
            DEBIAN_ISO="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--variant nvidia-std|nvidia-pro|amd] [--debian-iso path]"
            echo ""
            echo "Variants:"
            echo "  nvidia-std  - NVIDIA RTX 5060-5070, balanced config, AWQ"
            echo "  nvidia-pro  - NVIDIA RTX 5080-5090, max performance, AWQ"
            echo "  amd         - AMD RX 9060-9070 XT, ROCm backend"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--variant nvidia-std|nvidia-pro|amd] [--debian-iso path]"
            exit 1
            ;;
    esac
done

# Validate variant
case "$VARIANT" in
    nvidia-std|nvidia-pro|amd) ;;
    *) echo "Invalid variant: $VARIANT. Use: nvidia-std, nvidia-pro, amd"; exit 1 ;;
esac

echo "============================================"
echo "  Holmium OS ISO Builder"
echo "  Variant: ${VARIANT}"
echo "  Date:    ${DATE}"
echo "============================================"
echo ""

# Source variant config
VARIANT_DIR="${PROFILE_DIR}/variants/${VARIANT}"
if [ ! -d "$VARIANT_DIR" ]; then
    echo "Error: Variant profile not found: ${VARIANT_DIR}"
    exit 1
fi

source "${VARIANT_DIR}/config.sh"

OUTPUT_ISO="/opt/holmium/holmium-os-${VARIANT}-${DATE}.iso"
WORKDIR="/var/tmp/archiso-work"
DEBIAN_ISO="${DEBIAN_ISO:-/var/cache/holmium/debian-netinst.iso}"
DEBIAN_ISO_DEST="${PROFILE_DIR}/airootfs/usr/share/holmium/debian-netinst.iso"

# Use variant-specific packages
cp "${VARIANT_DIR}/packages.x86_64" "${PROFILE_DIR}/packages.x86_64"

# Use variant-specific profiledef
cp "${VARIANT_DIR}/profiledef.sh" "${PROFILE_DIR}/profiledef.sh"

if ! command -v mkarchiso &>/dev/null; then
    echo "Error: mkarchiso not found. Install archiso: pacman -S archiso" >&2
    exit 1
fi

if [ ! -f "$DEBIAN_ISO" ]; then
    echo "Warning: Debian netinst ISO not found at ${DEBIAN_ISO}"
    echo "Continuing without Debian ISO..."
    DEBIAN_ISO=""
fi

if [ -n "$DEBIAN_ISO" ]; then
    echo "==> Copying Debian netinst ISO into airootfs..."
    cp "$DEBIAN_ISO" "$DEBIAN_ISO_DEST"
fi

echo "==> Building Holmium OS ${VARIANT} ISO..."
echo "==> Output: ${OUTPUT_ISO}"
echo ""

# Clean working directory
rm -rf "$WORKDIR"

# Set variant-specific environment
export HOLMIUM_VARIANT="${VARIANT}"
export HOLMIUM_GPU_PACKAGES="${GPU_PACKAGES}"
export HOLMIUM_VLLM_BACKEND="${VLLM_BACKEND}"
export HOLMIUM_KERNEL_FLAVOR="${KERNEL_FLAVOR}"

PACMAN="pacman --noconfirm" mkarchiso -v -w "$WORKDIR" -o "$(dirname "$OUTPUT_ISO")" "${PROFILE_DIR}"

echo ""
echo "============================================"
echo "Build complete!"
echo "ISO: ${OUTPUT_ISO}"
echo "Variant: ${VARIANT}"
echo ""
echo "Write to USB:"
echo "  dd bs=4M if=${OUTPUT_ISO} of=/dev/sda status=progress"
echo ""
echo "Boot from the USB and run: holmium-install"
echo "============================================"

# Cleanup Debian ISO from airootfs
rm -f "$DEBIAN_ISO_DEST"

# Restore default packages/profiledef
git -C "$PROFILE_DIR" checkout -- packages.x86_64 profiledef.sh 2>/dev/null || true
