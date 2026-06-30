#!/usr/bin/env python3
import subprocess
import sys


def check_rocminfo():
    try:
        result = subprocess.run(
            ["rocminfo"], capture_output=True, text=True, timeout=30
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"rocminfo failed:\n{result.stderr}", file=sys.stderr)
            return False
        return True
    except FileNotFoundError:
        print("rocminfo not found — ROCm not installed", file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        print("rocminfo timed out", file=sys.stderr)
        return False


def check_pytorch_gpu():
    try:
        import torch
    except ImportError:
        print("PyTorch not installed", file=sys.stderr)
        return False

    if not torch.cuda.is_available():
        print("CUDA not available via PyTorch — ROCm not detected", file=sys.stderr)
        return False

    device = torch.cuda.get_device_properties(0)
    free_vram, total_vram = torch.cuda.mem_get_info(0)

    print(f"GPU Name: {device.name}")
    print(f"VRAM Total: {total_vram / (1024**3):.2f} GiB")
    print(f"VRAM Free:  {free_vram / (1024**3):.2f} GiB")

    x = torch.tensor([1.0, 2.0, 3.0], device="cuda")
    print(f"Tensor allocated on GPU: {x}")
    del x
    torch.cuda.empty_cache()
    return True


if __name__ == "__main__":
    print("=== ROCm Verification ===\n")

    rocm_ok = check_rocminfo()
    print()
    pytorch_ok = check_pytorch_gpu()
    print()

    if rocm_ok and pytorch_ok:
        print("ROCm verification PASSED")
        sys.exit(0)
    else:
        print("ROCm verification FAILED", file=sys.stderr)
        sys.exit(1)
