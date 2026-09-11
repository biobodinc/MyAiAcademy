"""Bridge a blocking event generator to an SSE response with real cancellation.

Starlette cancels the response task when the client disconnects, but it does not close
a synchronous generator that was being driven through a thread pool. Left alone, the
generator stays suspended at its last ``yield`` forever: with llama.cpp that means the
model keeps its context, the runtime lock is never released, and the partial reply is
never written. This bridge runs the generator on its own thread and hands it a cancel
flag that is set the moment the response ends for any reason, so the generator can stop,
persist what it has and release its resources.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import AsyncIterator, Callable, Iterator

from starlette.concurrency import run_in_threadpool

log = logging.getLogger(__name__)

_POLL_SECONDS = 0.5
_EMPTY = object()


async def stream_with_cancel(
    make_events: Callable[[threading.Event], Iterator[str]],
    *,
    thread_name: str = "myai-stream",
) -> AsyncIterator[str]:
    """Yield items from ``make_events(cancel)`` run on a worker thread.

    ``cancel`` is set when the consumer stops iterating (client disconnect, server
    shutdown, or normal completion). Exceptions raised by the generator are re-raised
    here so FastAPI's error handling still applies.
    """
    cancel = threading.Event()
    items: queue.Queue[object] = queue.Queue()

    def worker() -> None:
        try:
            for item in make_events(cancel):
                items.put(item)
        except BaseException as exc:
            items.put(exc)
        finally:
            items.put(None)

    def take() -> object:
        try:
            return items.get(timeout=_POLL_SECONDS)
        except queue.Empty:
            return _EMPTY

    thread = threading.Thread(target=worker, name=thread_name, daemon=True)
    thread.start()
    try:
        while True:
            item = await run_in_threadpool(take)
            if item is _EMPTY:
                continue
            if item is None:
                return
            if isinstance(item, BaseException):
                raise item
            yield str(item)
    finally:
        if thread.is_alive():
            log.debug("stream consumer went away; asking %s to stop", thread_name)
        cancel.set()
