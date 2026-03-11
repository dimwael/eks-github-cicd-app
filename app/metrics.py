import threading


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._request_count: int = 0
        self._error_count: int = 0

    def increment_requests(self) -> None:
        with self._lock:
            self._request_count += 1

    def increment_errors(self) -> None:
        with self._lock:
            self._error_count += 1

    def get_request_count(self) -> int:
        with self._lock:
            return self._request_count

    def get_error_count(self) -> int:
        with self._lock:
            return self._error_count

    def prometheus_text(self, active_faults: list[str]) -> str:
        with self._lock:
            req_count = self._request_count
            err_count = self._error_count

        fault_count = len(active_faults)
        lines = [
            "# HELP http_requests_total Total number of HTTP requests",
            "# TYPE http_requests_total counter",
            f"http_requests_total {req_count}",
            "",
            "# HELP http_errors_total Total number of HTTP 5xx responses",
            "# TYPE http_errors_total counter",
            f"http_errors_total {err_count}",
            "",
            "# HELP active_faults Number of currently active fault scenarios",
            "# TYPE active_faults gauge",
            f"active_faults {fault_count}",
            "",
        ]
        return "\n".join(lines)


# Module-level singleton
metrics = Metrics()
