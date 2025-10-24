import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log: Dict[str, Any] = {
            "ts": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Attach exception information if present
        if record.exc_info:
            log["exc_info"] = self.formatException(record.exc_info)
        # Attach structured extras if provided as dict
        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            log.update(extra)
        return json.dumps(log, ensure_ascii=False)


def init_logging(level: str = "INFO") -> None:
    """Initialize root logger with JSON output to stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
