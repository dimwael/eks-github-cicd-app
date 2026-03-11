"""Unit tests for structured JSON logger output shape."""
import io
import json
import logging
import sys

import pytest

from app.logger import JSONFormatter, get_logger, request_id_var


def capture_log(func):
    """Helper: capture JSON log output by attaching a StringIO handler."""
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        func()
    finally:
        root.removeHandler(handler)
    return buf.getvalue()


def test_log_line_is_valid_json():
    logger = get_logger("test.logger")
    output = capture_log(lambda: logger.info("hello world"))
    lines = [l for l in output.strip().splitlines() if l.strip()]
    assert lines, "Expected at least one log line"
    entry = json.loads(lines[-1])
    assert "level" in entry
    assert "timestamp" in entry
    assert "message" in entry


def test_log_level_field():
    logger = get_logger("test.level")
    output = capture_log(lambda: logger.warning("warn msg"))
    lines = [l for l in output.strip().splitlines() if l.strip()]
    entry = json.loads(lines[-1])
    assert entry["level"] == "WARNING"


def test_log_message_field():
    logger = get_logger("test.message")
    output = capture_log(lambda: logger.info("specific message text"))
    lines = [l for l in output.strip().splitlines() if l.strip()]
    entry = json.loads(lines[-1])
    assert entry["message"] == "specific message text"


def test_request_id_included_when_set():
    logger = get_logger("test.reqid")
    token = request_id_var.set("abc123")
    try:
        output = capture_log(lambda: logger.info("with request id"))
        lines = [l for l in output.strip().splitlines() if l.strip()]
        entry = json.loads(lines[-1])
        assert entry.get("request_id") == "abc123"
    finally:
        request_id_var.reset(token)


def test_request_id_absent_when_not_set():
    logger = get_logger("test.noreqid")
    token = request_id_var.set("")
    try:
        output = capture_log(lambda: logger.info("no request id"))
        lines = [l for l in output.strip().splitlines() if l.strip()]
        entry = json.loads(lines[-1])
        # request_id should be absent or empty when not set
        assert "request_id" not in entry or entry.get("request_id") == ""
    finally:
        request_id_var.reset(token)
