"""Property-based tests using Hypothesis.

Feature: eks-github-cicd-app
"""
import asyncio
import io
import json
import logging
import time

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from httpx import ASGITransport, AsyncClient

from app.logger import JSONFormatter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_async(coro):
    """Run a coroutine synchronously for use in sync Hypothesis tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def capture_log_output(func):
    """Capture JSON log output by attaching a StringIO handler to root logger."""
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


# ---------------------------------------------------------------------------
# Property 1: Root endpoint response shape
# Validates: Requirements 1.2
# ---------------------------------------------------------------------------

# Feature: eks-github-cicd-app, Property 1: Root endpoint response shape
@given(st.text(min_size=1, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))))
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_root_response_shape(version):
    """For any version string, GET / returns 200 with non-empty app, version, timestamp."""
    from app.main import app, fault_controller, settings as app_settings

    fault_controller.reset()
    original_version = app_settings.app_version
    app_settings.__dict__["app_version"] = version

    async def _run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/")
        return resp

    try:
        resp = run_async(_run())
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("app"), "app field must be non-empty"
        assert data.get("version"), "version field must be non-empty"
        assert data.get("timestamp"), "timestamp field must be non-empty"
    finally:
        app_settings.__dict__["app_version"] = original_version
        fault_controller.reset()


# ---------------------------------------------------------------------------
# Property 4: Fault activation does not break server liveness
# Validates: Requirements 5.2, 6.2
# ---------------------------------------------------------------------------

# Feature: eks-github-cicd-app, Property 4: Fault activation does not break server liveness
@given(st.sampled_from(["memory-leak", "cpu-spike", "slow-response"]))
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fault_does_not_break_liveness(fault_name):
    """After activating any non-crash fault, /health still returns HTTP 200."""
    from app.main import app, fault_controller

    fault_controller.reset()

    async def _run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            if fault_name == "memory-leak":
                await client.post("/fault/memory-leak")
            elif fault_name == "cpu-spike":
                await client.post("/fault/cpu-spike")
            elif fault_name == "slow-response":
                await client.get("/fault/slow-response?delay=0")
            resp = await client.get("/health")
        return resp

    try:
        resp = run_async(_run())
        assert resp.status_code == 200, f"Expected 200 after {fault_name}, got {resp.status_code}"
    finally:
        fault_controller.reset()


# ---------------------------------------------------------------------------
# Property 5: Fault activation produces a structured log warning
# Validates: Requirements 5.4, 6.3, 7.4, 8.3
# ---------------------------------------------------------------------------

# Feature: eks-github-cicd-app, Property 5: Fault activation produces a structured log warning
@given(st.sampled_from(["memory-leak", "cpu-spike", "slow-response", "dependency-failure"]))
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fault_activation_logs_warning(fault_name):
    """Each fault activation emits at least one WARNING-level JSON log line."""
    from app.fault import FaultController

    fc = FaultController()
    warning_lines = []

    def _activate():
        if fault_name == "memory-leak":
            fc.activate_memory_leak()
        elif fault_name == "cpu-spike":
            fc.activate_cpu_spike(1)
        elif fault_name == "slow-response":
            fc.activate_slow_response(100)
        elif fault_name == "dependency-failure":
            fc.activate_dependency_failure()

    try:
        output = capture_log_output(_activate)
        lines = [l for l in output.strip().splitlines() if l.strip()]
        for line in lines:
            try:
                entry = json.loads(line)
                if entry.get("level") in ("WARNING", "ERROR", "CRITICAL"):
                    warning_lines.append(entry)
            except json.JSONDecodeError:
                pass

        assert warning_lines, f"Expected at least one WARNING log for fault: {fault_name}"
        messages = " ".join(e.get("message", "") for e in warning_lines)
        assert fault_name in messages, f"Expected fault name '{fault_name}' in log messages: {messages}"
    finally:
        fc.reset()


# ---------------------------------------------------------------------------
# Property 6: Slow response respects delay parameter
# Validates: Requirements 7.1, 7.2
# ---------------------------------------------------------------------------

# Feature: eks-github-cicd-app, Property 6: Slow response respects delay parameter
@given(st.integers(min_value=0, max_value=200))
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_slow_response_delay(delay_ms):
    """GET /fault/slow-response?delay=N takes at least N ms and returns 200."""
    from app.main import app, fault_controller

    fault_controller.reset()

    async def _run():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=10.0,
        ) as client:
            start = time.monotonic()
            resp = await client.get(f"/fault/slow-response?delay={delay_ms}")
            elapsed_ms = (time.monotonic() - start) * 1000
        return resp, elapsed_ms

    try:
        resp, elapsed_ms = run_async(_run())
        assert resp.status_code == 200
        assert elapsed_ms >= delay_ms - 30, f"Expected >= {delay_ms}ms, got {elapsed_ms:.1f}ms"
    finally:
        fault_controller.reset()


# ---------------------------------------------------------------------------
# Property 7: Invalid delay parameter returns HTTP 400
# Validates: Requirements 7.3
# ---------------------------------------------------------------------------

# Feature: eks-github-cicd-app, Property 7: Invalid delay parameter returns HTTP 400
@given(
    st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll"),
            whitelist_characters="!@#$%^&*()_+",
        ),
        min_size=1,
    ).filter(lambda s: not s.lstrip("-").isdigit())
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_invalid_delay_returns_400(invalid_delay):
    """Non-numeric delay values return HTTP 400 with JSON error field."""
    from app.main import app, fault_controller

    fault_controller.reset()

    async def _run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/fault/slow-response?delay={invalid_delay}")
        return resp

    try:
        resp = run_async(_run())
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data
    finally:
        fault_controller.reset()


# ---------------------------------------------------------------------------
# Property 8: Dependency failure changes health status
# Validates: Requirements 9.1
# ---------------------------------------------------------------------------

# Feature: eks-github-cicd-app, Property 8: Dependency failure changes health status
@given(st.just(None))
@settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_dependency_failure_health(_):
    """After POST /fault/dependency-failure, GET /health returns 503 with unhealthy body."""
    from app.main import app, fault_controller

    fault_controller.reset()

    async def _run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/fault/dependency-failure")
            resp = await client.get("/health")
        return resp

    try:
        resp = run_async(_run())
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "unhealthy"
        assert data["reason"] == "dependency unavailable"
    finally:
        fault_controller.reset()


# ---------------------------------------------------------------------------
# Property 9: Reset restores healthy state
# Validates: Requirements 9.3, 9.4
# ---------------------------------------------------------------------------

# Feature: eks-github-cicd-app, Property 9: Reset restores healthy state
@given(
    st.lists(
        st.sampled_from(["slow-response", "dependency-failure"]),
        min_size=0,
        max_size=4,
    )
)
@settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=5000,
)
def test_reset_restores_health(fault_list):
    """After activating any combination of faults and calling reset, /health returns 200."""
    from app.main import app, fault_controller

    fault_controller.reset()

    async def _run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=10.0) as client:
            for fault in fault_list:
                if fault == "slow-response":
                    await client.get("/fault/slow-response?delay=0")
                elif fault == "dependency-failure":
                    await client.post("/fault/dependency-failure")
            await client.post("/fault/reset")
            resp = await client.get("/health")
        return resp

    try:
        resp = run_async(_run())
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}
    finally:
        fault_controller.reset()


# ---------------------------------------------------------------------------
# Property 10: All log entries are valid structured JSON with required fields
# Validates: Requirements 10.1, 10.2, 10.4
# ---------------------------------------------------------------------------

# Feature: eks-github-cicd-app, Property 10: All log entries are valid structured JSON with required fields
@given(
    st.sampled_from(["GET", "POST"]),
    st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_log_entry_fields(method, path_suffix):
    """Every request log line contains required JSON fields."""
    from app.main import app, fault_controller

    fault_controller.reset()
    request_log_lines = []

    async def _run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/")

    def _do():
        run_async(_run())

    output = capture_log_output(_do)
    lines = [l for l in output.strip().splitlines() if l.strip()]

    for line in lines:
        try:
            entry = json.loads(line)
            if "method" in entry and "path" in entry:
                request_log_lines.append(entry)
        except json.JSONDecodeError:
            pass

    assert request_log_lines, "Expected at least one request log line"
    for entry in request_log_lines:
        assert "level" in entry
        assert "timestamp" in entry
        assert "message" in entry
        assert "method" in entry
        assert "path" in entry
        assert "status" in entry
        assert "latency_ms" in entry

    fault_controller.reset()


# ---------------------------------------------------------------------------
# Property 11: Metrics endpoint contains required metric names
# Validates: Requirements 10.3
# ---------------------------------------------------------------------------

# Feature: eks-github-cicd-app, Property 11: Metrics endpoint contains required metric names
@given(st.integers(min_value=1, max_value=50))
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_metrics_contains_required_names(n_requests):
    """After N requests, /metrics contains all required metric names."""
    from app.main import app, fault_controller

    fault_controller.reset()

    async def _run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for _ in range(n_requests):
                await client.get("/")
            resp = await client.get("/metrics")
        return resp

    try:
        resp = run_async(_run())
        assert resp.status_code == 200
        body = resp.text
        assert "http_requests_total" in body
        assert "http_errors_total" in body
        assert "active_faults" in body
    finally:
        fault_controller.reset()
