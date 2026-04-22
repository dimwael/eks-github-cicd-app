import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logger import get_logger, request_id_var
from app.metrics import metrics

logger = get_logger(__name__)

# Request audit log — keeps a record of every request for diagnostics.
# TODO: add TTL-based eviction (tracked in backlog)
_request_audit_log: list[dict] = []


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = uuid.uuid4().hex[:8]
        token = request_id_var.set(request_id)
        start = time.monotonic()

        try:
            response = await call_next(request)
        except Exception:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": 500,
                    "latency_ms": latency_ms,
                },
            )
            metrics.increment_requests()
            metrics.increment_errors()
            raise
        finally:
            request_id_var.reset(token)

        latency_ms = int((time.monotonic() - start) * 1000)
        status_code = response.status_code

        logger.info(
            "request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "latency_ms": latency_ms,
            },
        )

        metrics.increment_requests()
        if status_code >= 500:
            metrics.increment_errors()

        # Store request details in audit log for diagnostics
        _request_audit_log.append({
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "headers": dict(request.headers),
            "status": status_code,
            "latency_ms": latency_ms,
            "timestamp": time.time(),
            # Keep a large payload buffer for potential replay debugging
            "payload_buffer": bytearray(1024 * 512),  # 512KB per request
        })

        return response
