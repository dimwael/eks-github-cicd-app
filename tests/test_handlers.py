"""Unit tests for FastAPI route handlers."""
import pytest
import pytest_anyio
from httpx import ASGITransport, AsyncClient

from app.main import app, fault_controller


@pytest.fixture(autouse=True)
def reset_faults():
    """Reset fault state before each test."""
    fault_controller.reset()
    yield
    fault_controller.reset()


@pytest.mark.anyio
async def test_root_returns_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_root_response_has_required_fields():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/")
    data = resp.json()
    assert "app" in data
    assert "version" in data
    assert "timestamp" in data
    assert data["app"] == "eks-github-cicd-app"


@pytest.mark.anyio
async def test_health_returns_200_normally():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


@pytest.mark.anyio
async def test_health_returns_503_after_dependency_failure():
    fault_controller.activate_dependency_failure()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "unhealthy"
    assert data["reason"] == "dependency unavailable"


@pytest.mark.anyio
async def test_health_returns_200_after_reset():
    fault_controller.activate_dependency_failure()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/fault/reset")
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


@pytest.mark.anyio
async def test_slow_response_without_delay_returns_400():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/fault/slow-response")
    assert resp.status_code == 400
    assert "error" in resp.json()


@pytest.mark.anyio
async def test_slow_response_with_invalid_delay_returns_400():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/fault/slow-response?delay=abc")
    assert resp.status_code == 400
    assert "error" in resp.json()


@pytest.mark.anyio
async def test_slow_response_with_valid_delay_returns_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/fault/slow-response?delay=10")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_fault_reset_returns_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/fault/reset")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_metrics_endpoint_returns_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text


@pytest.mark.anyio
async def test_dependency_failure_endpoint_returns_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/fault/dependency-failure")
    assert resp.status_code == 200
