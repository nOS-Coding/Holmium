"""System status endpoint logic — CPU, RAM, GPU, uptime, vLLM, WG, NTP."""

import json
import subprocess
from typing import Any

import httpx
import psutil

from .config import HolmiumConfig
from .logger import get_logger

logger = get_logger("status")


async def get_system_status() -> dict:
    config = HolmiumConfig.load()
    status: dict[str, Any] = {
        "cpu": _get_cpu(),
        "memory": _get_memory(),
        "gpu": await _get_gpu(),
        "uptime": _get_uptime(),
        "vllm": await _get_vllm_health(config),
        "wireguard": _get_wireguard(),
        "ntp": _get_ntp(),
    }
    return status


def _get_cpu() -> dict:
    try:
        return {
            "percent": psutil.cpu_percent(interval=0.5),
            "count": psutil.cpu_count(),
            "load_avg": [round(x, 2) for x in psutil.getloadavg()],
        }
    except Exception as exc:
        logger.warning("CPU stats failed: %s", exc)
        return {"error": str(exc)}


def _get_memory() -> dict:
    try:
        mem = psutil.virtual_memory()
        return {
            "total_gb": round(mem.total / (1024 ** 3), 2),
            "available_gb": round(mem.available / (1024 ** 3), 2),
            "percent": mem.percent,
        }
    except Exception as exc:
        logger.warning("Memory stats failed: %s", exc)
        return {"error": str(exc)}


async def _get_gpu() -> dict:
    try:
        result = subprocess.run(
            ["rocm-smi", "--json"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            gpus: list[dict] = []
            for card_id, info in data.items():
                if isinstance(info, dict):
                    gpus.append({
                        "card": card_id,
                        "name": info.get("Card series", ""),
                        "temperature": info.get("Temperature (Sensor memory) (C)", ""),
                        "power": info.get("Average Graphics Package Power (W)", ""),
                        "vram_total": info.get("VRAM Total Memory (MiB)", ""),
                        "vram_used": info.get("VRAM Total Used Memory (MiB)", ""),
                    })
            return {"gpus": gpus}
        return {"error": result.stderr.strip()}
    except FileNotFoundError:
        return {"note": "rocm-smi not available"}
    except (json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        return {"error": str(exc)}


def _get_uptime() -> dict:
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.read().split()[0])
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        return {
            "seconds": round(uptime_seconds, 2),
            "human": f"{days}d {hours}h {minutes}m",
        }
    except (FileNotFoundError, OSError, IndexError, ValueError) as exc:
        try:
            import psutil as _psutil
            uptime_seconds = _psutil.boot_time()
            return {"seconds": round(uptime_seconds, 2)}
        except Exception:
            return {"error": str(exc)}


async def _get_vllm_health(config: HolmiumConfig) -> dict:
    try:
        transport = httpx.AsyncHTTPTransport(uds=config.vllm_socket, retries=1)
        async with httpx.AsyncClient(transport=transport, timeout=5.0) as client:
            resp = await client.post(
                "http://localhost/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
            )
            if resp.status_code == 200:
                return {"status": "healthy"}
            return {"status": "unhealthy", "http": resp.status_code}
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        return {"status": "unreachable", "error": str(exc)}


def _get_wireguard() -> dict:
    try:
        result = subprocess.run(
            ["wg", "show", "all", "dump"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip()}

        peers: list[dict] = []
        lines = result.stdout.strip().splitlines()
        for line in lines:
            parts = line.split("\t")
            if len(parts) >= 5:
                endpoint = parts[2] if parts[2] != "(none)" else ""
                latest_handshake = parts[4] if parts[4] != "0" else ""
                transfer_rx = parts[5] if len(parts) > 5 else ""
                transfer_tx = parts[6] if len(parts) > 6 else ""
                peers.append({
                    "endpoint": endpoint,
                    "latest_handshake": latest_handshake,
                    "transfer_rx": transfer_rx,
                    "transfer_tx": transfer_tx,
                })

        return {
            "interface_count": len({l.split("\t")[0] for l in lines}) if lines else 0,
            "peers": peers,
        }
    except FileNotFoundError:
        return {"note": "wg not available"}
    except (subprocess.TimeoutExpired, IndexError) as exc:
        return {"error": str(exc)}


def _get_ntp() -> dict:
    try:
        result = subprocess.run(
            ["chronyc", "tracking"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip()}

        data: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if ": " in line:
                key, val = line.split(": ", 1)
                data[key.strip()] = val.strip()

        return {
            "stratum": data.get("Stratum", ""),
            "ref_time": data.get("Reference ID", ""),
            "last_offset": data.get("Last offset", ""),
            "rms_offset": data.get("RMS offset", ""),
        }
    except FileNotFoundError:
        return {"note": "chronyc not available"}
    except subprocess.TimeoutExpired as exc:
        return {"error": str(exc)}
