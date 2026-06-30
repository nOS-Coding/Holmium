# Performance Targets and Monitoring

## Targets

| Component | Target | Threshold (2x warning) |
|-----------|--------|----------------------|
| vLLM first-token latency (<4096 prompt) | <2s | >4s |
| Kokoro TTS (<200 words) | <500ms | >1s |
| Whisper STT (<30s audio) | <3s | >6s |
| `/status` endpoint | <100ms | >200ms |
| LanceDB search | <200ms | >400ms |
| SQLite query (single row) | <10ms | >20ms |
| Boot to greeting | <90s | >180s |
| Audio pipeline (speak → hear Holmium) | <3s | >6s |

## Monitoring

`perf_monitor.py` measures and logs each operation. Warnings at 2x threshold.

### Running Benchmark

```bash
holmium benchmark          # Full suite
holmium benchmark --quick  # vLLM + TTS only
holmium benchmark --history # Trend table
```

### Benchmark Tests

| Test | What it measures |
|------|-----------------|
| vLLM speed | 100-token prompt → first token |
| vLLM context | 4096-token prompt → first token |
| Kokoro latency | Text → audio generation |
| Whisper RTF | Real-time factor (audio time / processing time) |
| LanceDB search | Query → results |
| SQLite ops/s | CRUD operations per second |
| Disk I/O | Sequential read/write speed |
| ROCm GPU | VRAM usage, temperature during vLLM |

Results saved to `/var/holmium/benchmarks/<timestamp>.json`.

## Hardware

- **CPU**: x86_64 (AMD, >=6 cores)
- **GPU**: AMD GPU with >=16GB VRAM
- **RAM**: >=32GB
- **Storage**: >=1TB NVMe (ext4)
- **Network**: WireGuard over internet

## GPU Memory Allocation

| Component | VRAM | Notes |
|-----------|------|-------|
| vLLM (model + KV cache) | ~10-12GB | AWQ 4-bit + 131k context |
| Whisper STT | ~2GB | On CPU fallback if needed |
| Kokoro TTS | ~500MB | CPU-only |
| FLUX.1 Image Gen | ~16GB | vLLM swaps out during image gen |
