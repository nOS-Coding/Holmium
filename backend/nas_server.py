"""WebDAV NAS server — runs wsgidav as a managed subprocess."""

import asyncio
import os
import signal
from pathlib import Path
from typing import Optional

from backend.config import HolmiumConfig
from backend.logger import get_logger

logger = get_logger("nas_server")

_NAS_PID_PATH = Path("/run/holmium/nas.pid")
_NAS_CONFIG_PATH = Path("/run/holmium/nas_config.yml")


class NasServer:
    def __init__(self, config: HolmiumConfig) -> None:
        self._config = config
        self._process: Optional[asyncio.subprocess.Process] = None

    @property
    def enabled(self) -> bool:
        return self._config.nas_enabled

    @property
    def nas_path(self) -> str:
        return self._config.nas_path

    @property
    def port(self) -> int:
        return self._config.nas_port

    async def start(self) -> bool:
        if not self.enabled:
            logger.info("NAS server is disabled in config")
            return False

        # Check if already running (via PID file or in-process)
        if self.is_running:
            logger.info("NAS server already running")
            return True
        if self._process is not None and self._process.returncode is None:
            logger.info("NAS server already running (in-process)")
            return True

        nas_dir = Path(self.nas_path)
        if nas_dir != Path("/"):
            nas_dir.mkdir(parents=True, exist_ok=True)

        password = self._config.nas_password or "holmium"
        user = self._config.nas_user

        logger.info("Starting WebDAV NAS server on port %d (path: %s)", self.port, self.nas_path)
        self._process = await asyncio.create_subprocess_exec(
            "python3", "-m", "wsgidav",
            "--host", "0.0.0.0",
            "--port", str(self.port),
            "--root", self.nas_path,
            "--auth", "simple",
            "--user", f"{user}:{password}",
            "--no-ssl",
        )
        _NAS_PID_PATH.write_text(str(self._process.pid))
        logger.info("WebDAV NAS server started (pid %d)", self._process.pid)
        return True

    async def stop(self) -> bool:
        if self._process is None or self._process.returncode is not None:
            logger.info("NAS server not running")
            return False

        logger.info("Stopping WebDAV NAS server (pid %d)", self._process.pid)
        self._process.send_signal(signal.SIGTERM)
        try:
            await asyncio.wait_for(self._process.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("NAS server did not stop gracefully, sending SIGKILL")
            self._process.send_signal(signal.SIGKILL)
            await self._process.wait()

        self._process = None
        if _NAS_PID_PATH.exists():
            _NAS_PID_PATH.unlink()
        logger.info("WebDAV NAS server stopped")
        return True

    @property
    def is_running(self) -> bool:
        if self._process is not None and self._process.returncode is None:
            return True
        if _NAS_PID_PATH.exists():
            pid = int(_NAS_PID_PATH.read_text().strip())
            try:
                os.kill(pid, 0)
                return True
            except (OSError, ValueError):
                pass
        return False

    def get_status(self) -> dict:
        path = Path(self.nas_path)
        usage = {}
        if path.exists():
            try:
                st = path.stat()
                usage["path"] = str(path.resolve())
                usage["exists"] = True
            except OSError:
                usage["exists"] = False
        else:
            usage["exists"] = False

        return {
            "running": self.is_running,
            "enabled": self.enabled,
            "port": self.port,
            "path": self.nas_path,
            "auth": self._config.nas_user + ":***" if self._config.nas_password else "holmium:holmium (default)",
            **usage,
        }
