"""
Structured logger for Holmium backend.

Writes to /var/log/holmium/holmium.log with 50 MB rotation (5 backups)
and streams to stdout with coloured output.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("/var/log/holmium")
LOG_FILE = LOG_DIR / "holmium.log"
LOG_MAX_BYTES = 50 * 1024 * 1024  # 50 MB
LOG_BACKUP_COUNT = 5

_LEVEL_COLOURS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[41m\033[37m",
}
_RESET = "\033[0m"


class _ColouredStreamHandler(logging.StreamHandler):
    def emit(self, record):
        colour = _LEVEL_COLOURS.get(record.levelname, "")
        record.levelname = f"{colour}{record.levelname}{_RESET}"
        super().emit(record)


def _setup_root_logger():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    file_handler = RotatingFileHandler(
        str(LOG_FILE),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    root.addHandler(file_handler)

    stream_handler = _ColouredStreamHandler(sys.stdout)
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    root.addHandler(stream_handler)


_setup_root_logger()


def get_logger(component: str) -> logging.Logger:
    return logging.getLogger(component)
