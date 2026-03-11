"""Unit tests for FaultController state transitions."""
import pytest

from app.fault import FaultController


@pytest.fixture
def fc():
    controller = FaultController()
    yield controller
    controller.reset()


def test_initial_state_is_healthy(fc):
    assert fc.is_healthy() is True


def test_initial_active_faults_empty(fc):
    assert fc.active_faults() == []


def test_initial_slow_delay_is_zero(fc):
    assert fc.slow_delay_ms() == 0


def test_dependency_failure_makes_unhealthy(fc):
    fc.activate_dependency_failure()
    assert fc.is_healthy() is False


def test_dependency_failure_in_active_faults(fc):
    fc.activate_dependency_failure()
    assert "dependency-failure" in fc.active_faults()


def test_reset_restores_healthy(fc):
    fc.activate_dependency_failure()
    fc.reset()
    assert fc.is_healthy() is True


def test_reset_clears_active_faults(fc):
    fc.activate_dependency_failure()
    fc.activate_slow_response(500)
    fc.reset()
    assert fc.active_faults() == []


def test_slow_response_sets_delay(fc):
    fc.activate_slow_response(250)
    assert fc.slow_delay_ms() == 250
    assert "slow-response" in fc.active_faults()


def test_slow_delay_zero_after_reset(fc):
    fc.activate_slow_response(100)
    fc.reset()
    assert fc.slow_delay_ms() == 0


def test_memory_leak_in_active_faults(fc):
    fc.activate_memory_leak()
    assert "memory-leak" in fc.active_faults()
    fc.reset()


def test_cpu_spike_in_active_faults(fc):
    fc.activate_cpu_spike(1)
    assert "cpu-spike" in fc.active_faults()
    fc.reset()
