import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

# Per-request context variable for request_id
request_id_var: ContextVar[str] = ContextVar("request_id_var", default="")


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON strings."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "level": record.levelname,
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%f"
            )[:-3] + "Z",
            "message": record.getMessage(),
        }

        # Include request_id if set in context
        request_id = request_id_var.get("")
        if request_id:
            log_entry["request_id"] = request_id

        # Include any extra fields attached to the record
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            ) and not key.startswith("_"):
                log_entry[key] = value

        return json.dumps(log_entry)


def _setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)


_setup_logging()


def get_logger(name: str) -> logging.Logger:
    """Return a named logger using the JSON formatter."""
    return logging.getLogger(name)
