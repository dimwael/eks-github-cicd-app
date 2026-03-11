import errno
import os
import sys
from datetime import datetime, timezone

import anyio

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import Settings
from app.fault import FaultController
from app.logger import get_logger
from app.metrics import metrics
from app.middleware import RequestLoggingMiddleware

# Module-level singletons
settings = Settings()
fault_controller = FaultController()
logger = get_logger(__name__)

app = FastAPI(title="eks-github-cicd-app", version=settings.app_version)
app.add_middleware(RequestLoggingMiddleware)


@app.get("/")
async def root():
    return {
        "app": "eks-github-cicd-app",
        "version": settings.app_version,
        "timestamp": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
    }


@app.get("/health")
async def health():
    if fault_controller.is_healthy():
        return JSONResponse(status_code=200, content={"status": "healthy"})
    return JSONResponse(
        status_code=503,
        content={"status": "unhealthy", "reason": "dependency unavailable"},
    )


@app.get("/metrics", response_class=PlainTextResponse)
async def get_metrics():
    return metrics.prometheus_text(fault_controller.active_faults())


@app.post("/fault/memory-leak")
async def fault_memory_leak():
    fault_controller.activate_memory_leak()
    return {"activated": "memory-leak"}


@app.post("/fault/cpu-spike")
async def fault_cpu_spike():
    fault_controller.activate_cpu_spike(settings.cpu_spike_duration)
    return {"activated": "cpu-spike"}


@app.get("/fault/slow-response")
async def fault_slow_response(delay: str = Query(default=None)):
    if delay is None:
        return JSONResponse(
            status_code=400,
            content={
                "error": "delay query parameter is required and must be a non-negative integer (milliseconds)"
            },
        )
    try:
        delay_ms = int(delay)
        if delay_ms < 0:
            raise ValueError("negative delay")
    except (ValueError, TypeError):
        return JSONResponse(
            status_code=400,
            content={
                "error": "delay query parameter is required and must be a non-negative integer (milliseconds)"
            },
        )
    fault_controller.activate_slow_response(delay_ms)
    await anyio.sleep(delay_ms / 1000)
    return {"activated": "slow-response", "delay_ms": delay_ms}


@app.post("/fault/crash")
async def fault_crash():
    logger.warning("fault activated: crash — process exiting")
    os._exit(1)


@app.post("/fault/dependency-failure")
async def fault_dependency_failure():
    fault_controller.activate_dependency_failure()
    return {"activated": "dependency-failure"}


@app.post("/fault/reset")
async def fault_reset():
    fault_controller.reset()
    return {"reset": True}


if __name__ == "__main__":
    import uvicorn

    logger.info(
        "starting server",
        extra={"port": settings.port, "version": settings.app_version},
    )
    try:
        uvicorn.run(app, host="0.0.0.0", port=settings.port)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            logger.error(
                "port already in use",
                extra={"port": settings.port, "error": str(exc)},
            )
            sys.exit(1)
        raise
