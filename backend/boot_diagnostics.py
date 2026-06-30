"""Boot diagnostics — run system health checks on startup."""

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

logger = get_logger("boot_diagnostics")


class BootDiagnostics:
    def __init__(self, config: Optional[HolmiumConfig] = None) -> None:
        self._config = config or HolmiumConfig.load()

    async def run_all(self) -> list[dict]:
        checks = [
            self._check_vllm_health,
            self._check_lancedb,
            self._check_sqlite,
            self._check_debian_mounted,
            self._check_wireguard,
            self._check_ntp,
            self._check_rocm,
            self._check_vram,
            self._check_disk,
            self._check_internet,
        ]

        results: list[dict] = []
        for check in checks:
            start = time.monotonic()
            try:
                if asyncio.iscoroutinefunction(check):
                    status = await check()
                else:
                    status = check()
            except Exception as exc:
                status = {"status": "fail", "detail": str(exc)}
            duration = time.monotonic() - start
            results.append({
                "check": check.__name__.replace("_check_", ""),
                "status": status.get("status", "error"),
                "detail": status.get("detail", ""),
                "duration": round(duration, 3),
            })

        return results

    def critical_failures(self, results: list[dict]) -> list[dict]:
        critical_checks = {"vllm_health", "sqlite", "rocm", "disk"}
        return [r for r in results if r["check"] in critical_checks and r["status"] != "pass"]

    async def _check_vllm_health(self) -> dict:
        transport = httpx.AsyncHTTPTransport(uds=self._config.vllm_socket, retries=1)
        async with httpx.AsyncClient(transport=transport, timeout=10.0) as client:
            resp = await client.post(
                "http://localhost/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
            )
            if resp.status_code == 200:
                return {"status": "pass", "detail": "vLLM responding"}
            return {"status": "fail", "detail": f"HTTP {resp.status_code}"}

    def _check_lancedb(self) -> dict:
        try:
            vs = VectorStore()
            vs.search_similar("health check", n=1)
            return {"status": "pass", "detail": "LanceDB accessible"}
        except Exception as exc:
            return {"status": "fail", "detail": str(exc)}

    def _check_sqlite(self) -> dict:
        try:
            store = SQLiteStore()
            store.fact_list()
            return {"status": "pass", "detail": "SQLite accessible"}
        except Exception as exc:
            return {"status": "fail", "detail": str(exc)}

    def _check_debian_mounted(self) -> dict:
        try:
            result = subprocess.run(
                ["mountpoint", "-q", "/mnt/debian"],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                return {"status": "pass", "detail": "/mnt/debian mounted"}
            return {"status": "warn", "detail": "/mnt/debian not mounted"}
        except FileNotFoundError:
            return {"status": "warn", "detail": "mountpoint not available"}
        except subprocess.TimeoutExpired:
            return {"status": "fail", "detail": "mountpoint check timed out"}

    def _check_wireguard(self) -> dict:
        try:
            result = subprocess.run(
                ["wg", "show", "interfaces"],
                capture_output=True, text=True, timeout=5,
            )
            ifaces = result.stdout.strip().split()
            if ifaces:
                return {"status": "pass", "detail": f"WG interfaces: {', '.join(ifaces)}"}
            return {"status": "warn", "detail": "No WG interfaces"}
        except FileNotFoundError:
            return {"status": "warn", "detail": "wg not available"}
        except subprocess.TimeoutExpired:
            return {"status": "fail", "detail": "wg timed out"}

    def _check_ntp(self) -> dict:
        try:
            result = subprocess.run(
                ["chronyc", "tracking"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "Stratum" in line:
                        return {"status": "pass", "detail": line.strip()}
                return {"status": "pass", "detail": "chronyc responding"}
            return {"status": "fail", "detail": result.stderr.strip()}
        except FileNotFoundError:
            return {"status": "warn", "detail": "chronyc not available"}
        except subprocess.TimeoutExpired:
            return {"status": "fail", "detail": "chronyc timed out"}

    def _check_rocm(self) -> dict:
        try:
            result = subprocess.run(
                ["rocm-smi", "--json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                gpu_count = len(data) if isinstance(data, dict) else 0
                return {"status": "pass", "detail": f"{gpu_count} GPU(s) detected"}
            return {"status": "fail", "detail": result.stderr.strip()}
        except FileNotFoundError:
            return {"status": "warn", "detail": "rocm-smi not available"}
        except (json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
            return {"status": "fail", "detail": str(exc)}

    def _check_vram(self) -> dict:
        try:
            result = subprocess.run(
                ["rocm-smi", "--showmeminfo", "vram", "--json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return {"status": "pass", "detail": "VRAM info available"}
            return {"status": "warn", "detail": "VRAM info unavailable"}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return {"status": "warn", "detail": "rocm-smi not available"}

    def _check_disk(self) -> dict:
        try:
            result = subprocess.run(
                ["df", "-h", "/var/holmium"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().splitlines()
                if len(lines) >= 2:
                    parts = lines[1].split()
                    usage = parts[4] if len(parts) > 4 else "unknown"
                    return {"status": "pass", "detail": f"Disk usage: {usage}"}
            return {"status": "fail", "detail": result.stderr.strip()}
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return {"status": "warn", "detail": str(exc)}

    async def _check_internet(self) -> dict:
        try:
            transport = httpx.AsyncHTTPTransport(retries=1)
            async with httpx.AsyncClient(transport=transport, timeout=10.0) as client:
                resp = await client.get("https://1.1.1.1")
                if resp.status_code == 200:
                    return {"status": "pass", "detail": "Internet reachable"}
                return {"status": "fail", "detail": f"HTTP {resp.status_code}"}
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            return {"status": "fail", "detail": str(exc)}
