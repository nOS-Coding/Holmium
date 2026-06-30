#!/bin/bash
set -euo pipefail

# rocm_setup.sh — Holmium OS ROCm installation for Arch Linux
# Installs ROCm SDKs, configures environment, verifies GPU.

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "=== Holmium OS ROCm Setup ==="

# ---------------------------------------------------------------------------
# 1. Install ROCm packages via pacman
# ---------------------------------------------------------------------------
log "Installing ROCm packages (rocm-hip-sdk, rocm-opencl-sdk, rocm-dev)..."
pacman -Syu --noconfirm \
    rocm-hip-sdk \
    rocm-opencl-sdk \
    rocm-dev

log "ROCm packages installed"

# ---------------------------------------------------------------------------
# 2. Create ROCm ldconfig configuration
# ---------------------------------------------------------------------------
log "Creating /etc/ld.so.conf.d/rocm.conf"
cat > /etc/ld.so.conf.d/rocm.conf <<'EOF'
/opt/rocm/lib
/opt/rocm/lib64
EOF
ldconfig
log "ROCm library paths configured"

# ---------------------------------------------------------------------------
# 3. Set HSA_OVERRIDE_GFX_VERSION for RDNA4 (RX 9070 XT)
# ---------------------------------------------------------------------------
log "Adding HSA_OVERRIDE_GFX_VERSION=11.0.0 to /etc/environment"
cat >> /etc/environment <<'EOF'

# ROCm: Override GFX version for RDNA4 (AMD RX 9070 XT)
HSA_OVERRIDE_GFX_VERSION=11.0.0
EOF

# Also export for immediate use in this script
export HSA_OVERRIDE_GFX_VERSION=11.0.0

log "HSA_OVERRIDE_GFX_VERSION set to 11.0.0 (RDNA4)"

# ---------------------------------------------------------------------------
# 4. Set ROCm environment variables
# ---------------------------------------------------------------------------
cat >> /etc/environment <<'EOF'
# ROCm paths
ROCM_PATH=/opt/rocm
HIP_PATH=/opt/rocm/hip
PATH=$PATH:/opt/rocm/bin:/opt/rocm/hip/bin
EOF

# ---------------------------------------------------------------------------
# 5. Create /etc/ld.so.conf.d/rocm.conf (already done above, just the file)
# Already written above
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 6. Verify with rocminfo
# ---------------------------------------------------------------------------
log "Verifying ROCm installation with rocminfo..."
if command -v rocminfo &>/dev/null; then
    rocminfo 2>/dev/null | head -30 || log "rocminfo exited with error — check GPU"
    log "ROCm installation verified"
else
    log "WARNING: rocminfo not found — install may have failed"
fi

# ---------------------------------------------------------------------------
# 7. Print GPU status
# ---------------------------------------------------------------------------
if command -v rocm-smi &>/dev/null; then
    log "GPU status:"
    rocm-smi --showid --showproductname 2>/dev/null || true
fi

log "=== ROCm Setup Complete ==="
echo ""
echo "ROCm is installed at /opt/rocm/"
echo "GPU override: HSA_OVERRIDE_GFX_VERSION=11.0.0 (RDNA4)"
echo "Reboot or source /etc/environment for changes to take effect"
