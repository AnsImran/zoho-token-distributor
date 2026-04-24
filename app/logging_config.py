"""Structured logging setup.

Supports two output formats:
- ``json`` (default) — structured JSON, one object per line, for log aggregation
- ``text`` — human-readable, for local development
"""

import json
import logging
import logging.handlers
import os
import sys
from datetime import UTC, datetime
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Configure the root logger with the chosen format and level."""
    root = logging.getLogger()
    root.setLevel(level.upper())

    if fmt == "json":
        formatter: logging.Formatter = JSONFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s — %(message)s")

    stderr_handler = logging.StreamHandler(sys.stdout)
    stderr_handler.setFormatter(formatter)
    handlers: list[logging.Handler] = [stderr_handler]

    # Phase-2 observability: when WLS_LOG_FILE is set, also write to a
    # rotating file so Promtail can tail it and ship to Loki. Same env
    # var used across every service in the monorepo for a consistent
    # log-shipper config.
    file_path = os.environ.get("WLS_LOG_FILE")
    if file_path:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            file_path,
            maxBytes=50 * 1024 * 1024,   # 50 MB per file
            backupCount=5,               # 5 backups -> ~250 MB ceiling
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    root.handlers = handlers
