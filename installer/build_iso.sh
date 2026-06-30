#!/usr/bin/env bash
set -euo pipefail

DATE=$(date +%Y%m%d)
PROFILE_DIR="$(cd "$(dirname "$0")/archiso" && pwd)"
VARIANT="nvidia"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --variant) VARIANT="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: $0 --variant nvidia|amd"
            echo ""
            echo "Variants:"
            echo "  nvidia  - NVIDIA RTX 5060-5090, CUDA, AWQ"
            echo "  amd     - AMD RX 9060-9070 XT, ROCm backend"
            exit 0 ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 --variant nvidia|amd"
            exit 1 ;;
    esac
done

case "$VARIANT" in nvidia|amd) ;; *) echo "Invalid variant: $VARIANT"; exit 1 ;; esac

echo "============================================"
echo "  Holmium OS ISO Builder"
echo "  Variant: ${VARIANT}"
echo "  Date:    ${DATE}"
echo "============================================"
echo ""

VARIANT_DIR="${PROFILE_DIR}/variants/${VARIANT}"
if [ ! -d "$VARIANT_DIR" ]; then
    echo "Error: Variant profile not found: ${VARIANT_DIR}"
    exit 1
fi

source "${VARIANT_DIR}/config.sh"

OUTPUT_ISO="/opt/holmium/holmium-os-${VARIANT}-${DATE}.iso"
WORKDIR="/var/tmp/archiso-work"

# Copy variant-specific config
cp "${VARIANT_DIR}/packages.x86_64" "${PROFILE_DIR}/packages.x86_64"
cp "${VARIANT_DIR}/profiledef.sh" "${PROFILE_DIR}/profiledef.sh"

if ! command -v mkarchiso &>/dev/null; then
    echo "Error: mkarchiso not found. Install archiso: pacman -S archiso" >&2
    exit 1
fi

# Clean workdir (handle leftover mounts gracefully)
if [ -d "$WORKDIR" ]; then
    echo "==> Cleaning previous work directory..."
    find "$WORKDIR" -type f -name '*.sfs' -delete 2>/dev/null || true
    find "$WORKDIR" -depth -type d -exec rmdir {} \; 2>/dev/null || true
    rm -rf "$WORKDIR" 2>/dev/null || {
        echo "==> Workdir cleanup incomplete, continuing anyway..."
    }
fi

echo "==> Building Holmium OS ${VARIANT} ISO..."
echo "==> Output: ${OUTPUT_ISO}"
echo ""

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

# Restore default packages/profiledef
git -C "$PROFILE_DIR" checkout -- packages.x86_64 profiledef.sh 2>/dev/null || true
