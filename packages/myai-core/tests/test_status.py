import threading
import time

from myai_core.status.service import AIState, Availability, InternetMonitor, _describe_ai


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


def _with_runtime(active: str | None = None, loaded: str | None = None) -> tuple[Availability, str]:
    return _describe_ai(
        AIState(
            runtime_available=True,
            runtime_detail="llama.cpp runtime 0.0.0",
            active_model_id=active,
            loaded_model_id=loaded,
        )
    )


def test_every_ai_state_says_why_in_its_own_words() -> None:
    """The status line is what a user reads when nothing works, so each state explains
    itself. These four are environment-dependent in real use: the inference runtime is
    an optional extra, so a plain install reports the first one and a full install the
    others. A test that only exercised one of them would pass on one machine and fail
    on another."""
    availability, detail = _describe_ai(
        AIState(
            runtime_available=False,
            runtime_detail="The local inference runtime (llama-cpp-python) is not installed.",
            active_model_id=None,
            loaded_model_id=None,
        )
    )
    assert availability is Availability.UNAVAILABLE
    assert "runtime" in detail.lower()

    availability, detail = _with_runtime()
    assert availability is Availability.NOT_CONFIGURED
    assert "model" in detail.lower()

    availability, detail = _with_runtime("a-model")
    assert availability is Availability.AVAILABLE
    assert "a-model" in detail and "installed" in detail

    availability, detail = _with_runtime("a-model", "a-model")
    assert availability is Availability.AVAILABLE
    assert "a-model" in detail and "ready" in detail

    assert _describe_ai(None)[0] is Availability.UNKNOWN
