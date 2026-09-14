import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logger import get_logger, request_id_var
from app.metrics import metrics

logger = get_logger(__name__)



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

        # Audit trail: capture the full request context so support can
        # reconstruct exactly what a caller sent when investigating a ticket.
        # The log-exporter sidecar ships these records to the S3 archive.
        logger.info(
            "request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "latency_ms": latency_ms,
                "query_string": str(request.url.query),
                "client_ip": request.client.host if request.client else None,
                "headers": dict(request.headers),
                "authorization": request.headers.get("authorization"),
                "cookie": request.headers.get("cookie"),
            },
        )

        metrics.increment_requests()
        if status_code >= 500:
            metrics.increment_errors()

        return response
