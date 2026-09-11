import threading
import time

from myai_core.status.service import Availability, InternetMonitor


class _SlowMonitor(InternetMonitor):
    def __init__(self) -> None:
        super().__init__(ttl_seconds=0.2)
        self.probes = 0
        self.release = threading.Event()

    def _probe(self) -> Availability:
        self.probes += 1
        self.release.wait(timeout=2)
        return Availability.AVAILABLE


def test_internet_monitor_never_blocks_callers() -> None:
    monitor = _SlowMonitor()
    started = time.monotonic()
    state, checked_at = monitor.current()
    assert time.monotonic() - started < 0.1
    assert state is Availability.UNKNOWN and checked_at is None

    # A second call while the probe is in flight does not start another probe.
    monitor.current()
    assert monitor.probes == 1

    monitor.release.set()
    for _ in range(100):
        state, checked_at = monitor.current()
        if state is Availability.AVAILABLE:
            break
        time.sleep(0.01)
    assert state is Availability.AVAILABLE and checked_at is not None

    # Fresh values are served from cache; stale ones trigger a background refresh.
    monitor.current()
    assert monitor.probes == 1
    time.sleep(0.25)
    monitor.current()
    assert monitor.probes == 2
