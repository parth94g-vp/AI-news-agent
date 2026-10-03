"""Structured (JSON-lines) logging helpers."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

_RESERVED = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}
_configured = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        payload.update({k: v for k, v in record.__dict__.items() if k not in _RESERVED})
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    global _configured
    root = logging.getLogger()
    root.setLevel(level)
    if _configured:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
    for noisy in ("httpx", "httpcore", "urllib3", "groq"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields) -> None:
    """log_event(logger, "articles_deduplicated", removed=3) -> one JSON line."""
    logger.log(level, event, extra=fields)
