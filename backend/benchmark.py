"""Benchmark tool — measure vLLM, Piper, Whisper, LanceDB, SQLite, disk, ROCm."""

import asyncio
import json
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from ..memory.vector_store import VectorStore
from ..memory.sqlite_store import SQLiteStore
from .config import HolmiumConfig
from .logger import get_logger

logger = get_logger("benchmark")

_BENCHMARK_DB = "/var/holmium/benchmarks.json"


async def run_benchmark(quick: bool = False) -> dict:
    config = HolmiumConfig.load()
    results: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "quick": quick,
    }

    results["vllm_speed"] = await _bench_vllm_speed(config)
    results["vllm_context"] = await _bench_vllm_context(config)
    results["tts_latency"] = await _bench_tts_latency()
    results["whisper_rtf"] = await _bench_whisper_rtf()
    results["lancedb_search"] = await _bench_lancedb_search()
    results["sqlite_ops"] = await _bench_sqlite_ops()
    results["disk_io"] = await _bench_disk_io(quick)
    results["rocm_stats"] = await _bench_rocm_stats()

    _save_results(results)
    return results


async def get_benchmark_history() -> list[dict]:
    try:
        path = Path(_BENCHMARK_DB)
        if path.exists():
            data = json.loads(path.read_text())
            if isinstance(data, list):
                return data
            return [data]
        return []
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load benchmark history: %s", exc)
        return []


async def _bench_vllm_speed(config: HolmiumConfig) -> dict:
    start = time.monotonic()
    try:
        transport = httpx.AsyncHTTPTransport(uds=config.vllm_socket, retries=1)
        async with httpx.AsyncClient(transport=transport, timeout=120.0) as client:
            resp = await client.post(
                "http://localhost/v1/chat/completions",
                json={
                    "model": config.vllm_model,
                    "messages": [{"role": "user", "content": "Write a short paragraph about AI."}],
                    "max_tokens": 200,
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            tokens_out = len(content.split())
            elapsed = time.monotonic() - start
            tokens_per_sec = tokens_out / elapsed if elapsed > 0 else 0
            return {
                "tokens_generated": tokens_out,
                "elapsed_seconds": round(elapsed, 3),
                "tokens_per_second": round(tokens_per_sec, 2),
            }
    except Exception as exc:
        return {"error": str(exc)}


async def _bench_vllm_context(config: HolmiumConfig) -> dict:
    start = time.monotonic()
    try:
        context_messages = [{"role": "user", "content": f"Test message {i}"} for i in range(50)]
        transport = httpx.AsyncHTTPTransport(uds=config.vllm_socket, retries=1)
        async with httpx.AsyncClient(transport=transport, timeout=120.0) as client:
            resp = await client.post(
                "http://localhost/v1/chat/completions",
                json={
                    "model": config.vllm_model,
                    "messages": context_messages,
                    "max_tokens": 50,
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            elapsed = time.monotonic() - start
            return {"status": "ok", "context_messages": 50, "elapsed_seconds": round(elapsed, 3)}
    except Exception as exc:
        return {"error": str(exc)}


async def _bench_tts_latency() -> dict:
    try:
        from ..tts.piper_tts import PiperTTS
        start = time.monotonic()
        engine = PiperTTS()
        wav = engine.synthesize("Hello, this is a test of the Piper text to speech system.")
        elapsed = time.monotonic() - start
        return {"status": "ok", "elapsed_seconds": round(elapsed, 3), "wav_bytes": len(wav)}
    except ImportError:
        return {"status": "skipped", "reason": "piper not installed"}
    except Exception as exc:
        return {"error": str(exc)}


async def _bench_whisper_rtf() -> dict:
    try:
        import faster_whisper
        start = time.monotonic()
        model = faster_whisper.WhisperModel("large-v3", device="cpu", compute_type="int8")
        segments, info = model.transcribe("test_audio.wav", beam_size=1)
        audio_duration = info.duration if info else 1.0
        segments_list = list(segments)
        elapsed = time.monotonic() - start
        rtf = elapsed / audio_duration if audio_duration > 0 else 0
        return {"status": "ok", "rtf": round(rtf, 3), "audio_duration_seconds": round(audio_duration, 2)}
    except ImportError:
        return {"status": "skipped", "reason": "faster_whisper not installed"}
    except Exception as exc:
        return {"error": str(exc)}


async def _bench_lancedb_search() -> dict:
    start = time.monotonic()
    try:
        vs = VectorStore()
        results = vs.search_similar("benchmark test query", n=10)
        elapsed = time.monotonic() - start
        return {"status": "ok", "results": len(results), "elapsed_seconds": round(elapsed, 4)}
    except Exception as exc:
        return {"error": str(exc)}


async def _bench_sqlite_ops() -> dict:
    start = time.monotonic()
    try:
        store = SQLiteStore()
        store.fact_set("benchmark_test", "test_value")
        result = store.fact_get("benchmark_test")
        store.fact_delete("benchmark_test")
        elapsed = time.monotonic() - start
        return {"status": "ok", "ops_per_second": round(3 / elapsed, 2) if elapsed > 0 else 0}
    except Exception as exc:
        return {"error": str(exc)}


async def _bench_disk_io(quick: bool) -> dict:
    try:
        path = "/var/holmium/benchmark_disk_test"
        size_mb = 10 if quick else 100
        data = b"x" * (size_mb * 1024 * 1024)

        write_start = time.monotonic()
        Path(path).write_bytes(data)
        write_elapsed = time.monotonic() - write_start

        read_start = time.monotonic()
        _ = Path(path).read_bytes()
        read_elapsed = time.monotonic() - read_start

        Path(path).unlink(missing_ok=True)

        return {
            "status": "ok",
            "size_mb": size_mb,
            "write_speed_mbps": round(size_mb / write_elapsed, 2) if write_elapsed > 0 else 0,
            "read_speed_mbps": round(size_mb / read_elapsed, 2) if read_elapsed > 0 else 0,
        }
    except Exception as exc:
        return {"error": str(exc)}


async def _bench_rocm_stats() -> dict:
    try:
        result = subprocess.run(
            ["rocm-smi", "--json"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            cards = []
            for card_id, info in data.items():
                if isinstance(info, dict):
                    cards.append({
                        "card": card_id,
                        "temperature": info.get("Temperature (Sensor memory) (C)", ""),
                        "power": info.get("Average Graphics Package Power (W)", ""),
                        "vram_used": info.get("VRAM Total Memory (MiB)", ""),
                    })
            return {"status": "ok", "cards": cards}
        return {"status": "fail", "detail": result.stderr.strip()}
    except FileNotFoundError:
        return {"status": "skipped", "reason": "rocm-smi not available"}
    except (json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        return {"error": str(exc)}


def _save_results(results: dict) -> None:
    from pathlib import Path
    try:
        path = Path(_BENCHMARK_DB)
        path.parent.mkdir(parents=True, exist_ok=True)
        history: list = []
        if path.exists():
            history = json.loads(path.read_text())
        history.append(results)
        path.write_text(json.dumps(history, indent=2))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to save benchmark results: %s", exc)


from pathlib import Path
