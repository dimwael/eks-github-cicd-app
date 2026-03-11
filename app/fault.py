import concurrent.futures
import threading
import time

from app.logger import get_logger

logger = get_logger(__name__)

# Module-level list to hold leaked memory chunks
_leaked_memory: list = []


class FaultController:
    def __init__(self) -> None:
        self._dependency_failure: bool = False
        self._slow_delay_ms: int = 0
        self._stop_event: threading.Event = threading.Event()
        self._lock: threading.Lock = threading.Lock()
        self._active_faults: set[str] = set()
        self._executor: concurrent.futures.ThreadPoolExecutor = (
            concurrent.futures.ThreadPoolExecutor(max_workers=2)
        )

    def activate_memory_leak(self) -> None:
        logger.warning("fault activated: memory-leak")
        stop = self._stop_event

        def _leak(stop_event: threading.Event) -> None:
            while not stop_event.is_set():
                _leaked_memory.append(bytearray(10 * 1024 * 1024))  # 10 MB
                time.sleep(1)

        t = threading.Thread(target=_leak, args=(stop,), daemon=True)
        t.start()
        with self._lock:
            self._active_faults.add("memory-leak")

    def activate_cpu_spike(self, duration_sec: int) -> None:
        start_time = time.time()
        logger.warning(
            "fault activated: cpu-spike",
            extra={"start_time": start_time, "duration_sec": duration_sec},
        )
        stop = self._stop_event

        def _spike(stop_event: threading.Event) -> None:
            deadline = time.time() + duration_sec
            while not stop_event.is_set() and time.time() < deadline:
                # Tight arithmetic loop
                _ = sum(i * i for i in range(10000))

        self._executor.submit(_spike, stop)
        with self._lock:
            self._active_faults.add("cpu-spike")

    def activate_slow_response(self, delay_ms: int) -> None:
        logger.warning("fault activated: slow-response", extra={"delay_ms": delay_ms})
        with self._lock:
            self._slow_delay_ms = delay_ms
            self._active_faults.add("slow-response")

    def activate_dependency_failure(self) -> None:
        logger.warning("fault activated: dependency-failure")
        with self._lock:
            self._dependency_failure = True
            self._active_faults.add("dependency-failure")

    def reset(self) -> None:
        with self._lock:
            self._stop_event.set()
            self._dependency_failure = False
            self._slow_delay_ms = 0
            self._active_faults.clear()
            # Create a fresh stop event for future faults
            self._stop_event = threading.Event()
            # Clear leaked memory
            _leaked_memory.clear()
        logger.info("all faults reset")

    def is_healthy(self) -> bool:
        with self._lock:
            return not self._dependency_failure

    def slow_delay_ms(self) -> int:
        with self._lock:
            return self._slow_delay_ms

    def active_faults(self) -> list[str]:
        with self._lock:
            return sorted(self._active_faults)
