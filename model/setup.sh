#!/bin/bash
set -euo pipefail

MODEL_REPO="QuantTrio/Qwen3.6-35B-A3B-AWQ"
MODEL_DIR="/usr/share/holmium/models/${MODEL_REPO}"
HF_BASE="https://huggingface.co/${MODEL_REPO}/resolve/main"
API_URL="https://huggingface.co/api/models/${MODEL_REPO}"

echo "[*] Installing vLLM with ROCm support..."
pip install --upgrade pip
pip install vllm[rocm]

echo "[*] Creating /run/holmium/..."
install -d -m 755 /run/holmium

if [ -d "${MODEL_DIR}" ] && [ "$(ls -A "${MODEL_DIR}" 2>/dev/null)" ]; then
    echo "[*] Model already downloaded at ${MODEL_DIR}, skipping."
else
    echo "[*] Downloading ${MODEL_REPO} via HuggingFace raw URLs..."

    wget -q -O /tmp/holmium_model_info.json "${API_URL}"

    python3 - "${MODEL_DIR}" "${HF_BASE}" << 'PYEOF'
import json, os, subprocess, sys

model_dir = sys.argv[1]
hf_base = sys.argv[2]

with open("/tmp/holmium_model_info.json") as f:
    data = json.load(f)

siblings = data.get("siblings", [])
if not siblings:
    print("[-] No files found in model repository.", file=sys.stderr)
    sys.exit(1)

for sibling in siblings:
    rfilename = sibling["rfilename"]
    file_url = f"{hf_base}/{rfilename}"
    dest_path = os.path.join(model_dir, rfilename)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    if os.path.exists(dest_path):
        print(f"  Skipping {rfilename} (exists)")
        continue
    print(f"  Downloading {rfilename}...")
    ret = subprocess.run(
        ["wget", "-q", "-c", file_url, "-O", dest_path], timeout=300
    )
    if ret.returncode != 0:
        print(f"  [-] Failed to download {rfilename}", file=sys.stderr)
        sys.exit(1)

print(f"[*] Model downloaded to {model_dir}")
PYEOF

    rm -f /tmp/holmium_model_info.json
fi

echo "[*] Setup complete."
