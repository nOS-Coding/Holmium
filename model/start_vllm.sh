#!/bin/bash
set -euo pipefail

export HIP_VISIBLE_DEVICES=0
export ROCR_VISIBLE_DEVICES=0

MODEL_DIR="/usr/share/holmium/models/QuantTrio/Qwen3.6-35B-A3B-AWQ"
SOCKET="/run/holmium/vllm.sock"

exec python -m vllm.entrypoints.openai.api_server \
  --model "${MODEL_DIR}" \
  --unix-socket "${SOCKET}" \
  --max-model-len 131072 \
  --gpu-memory-utilization 0.90 \
  --swap-space 16 \
  --num-scheduler-steps 8 \
  --dtype float16 \
  --api-key none
