#!/usr/bin/env bash
# AMD variant — RX 9060-9070 XT
VARIANT_LABEL="AMD"
GPU_PACKAGES="rocm-hip-sdk rocm-opencl-sdk rocm-hip-runtime rocminfo vllm-rocm"
VLLM_BACKEND="vllm-rocm"
KERNEL_FLAVOR="amd"
VARIANT_DESC="ROCm backend for AMD GPUs. vLLM with ROCm support."
