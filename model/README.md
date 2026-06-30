# model — vLLM + Qwen3.6-35B-A3B-AWQ

vLLM server serving QuantTrio/Qwen3.6-35B-A3B-AWQ (AWQ 4-bit, group size 128) over Unix socket `/run/holmium/vllm.sock`. ROCm setup, model download via wget, VRAM management.

- `serve.sh` — launches vLLM with correct flags
- `download.sh` — downloads model weights from HuggingFace raw URLs
- `vram.py` — VRAM manager (kill/restore for FLUX)
