"""Unit tests for Metrics class."""
import pytest

from app.metrics import Metrics


@pytest.fixture
def m():
    return Metrics()


def test_initial_request_count_zero(m):
    assert m.get_request_count() == 0


def test_initial_error_count_zero(m):
    assert m.get_error_count() == 0


def test_increment_requests(m):
    m.increment_requests()
    m.increment_requests()
    assert m.get_request_count() == 2


def test_increment_errors(m):
    m.increment_errors()
    assert m.get_error_count() == 1


def test_prometheus_text_contains_required_names(m):
    text = m.prometheus_text([])
    assert "http_requests_total" in text
    assert "http_errors_total" in text
    assert "active_faults" in text


def test_prometheus_text_has_help_and_type_lines(m):
    text = m.prometheus_text([])
    assert "# HELP http_requests_total" in text
    assert "# TYPE http_requests_total counter" in text
    assert "# HELP http_errors_total" in text
    assert "# TYPE http_errors_total counter" in text
    assert "# HELP active_faults" in text
    assert "# TYPE active_faults gauge" in text


def test_prometheus_text_reflects_counts(m):
    m.increment_requests()
    m.increment_requests()
    m.increment_requests()
    m.increment_errors()
    text = m.prometheus_text([])
    assert "http_requests_total 3" in text
    assert "http_errors_total 1" in text


def test_prometheus_text_active_faults_count(m):
    text = m.prometheus_text(["memory-leak", "cpu-spike"])
    assert "active_faults 2" in text


def test_prometheus_text_zero_active_faults(m):
    text = m.prometheus_text([])
    assert "active_faults 0" in text
