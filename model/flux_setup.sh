#!/bin/bash
set -euo pipefail

echo "[*] Installing diffusers for FLUX.1-schnell..."
pip install diffusers transformers accelerate sentencepiece

echo "[*] FLUX environment prepared."
echo "[*] Model (black-forest-labs/FLUX.1-schnell) will be downloaded on first image gen request."
