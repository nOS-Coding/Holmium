#!/usr/bin/env bash
# NVIDIA variant — RTX 5060-5090
VARIANT_LABEL="NVIDIA"
GPU_PACKAGES="nvidia-dkms nvidia-utils cuda vllm-cuda"
VLLM_BACKEND="vllm-cuda"
KERNEL_FLAVOR="nvidia"
VARIANT_DESC="CUDA backend for NVIDIA GPUs. vLLM with AWQ quantization."
