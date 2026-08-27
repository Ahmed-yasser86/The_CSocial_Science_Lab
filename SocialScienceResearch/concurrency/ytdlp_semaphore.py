"""Process-global semaphore capping concurrent ``YoutubeDL`` contexts.

Independent of the budget controller: the controller paces *when* an operation
may start, while this limiter caps *how many* ``YoutubeDL(...)`` contexts can be
active at the same instant across the entire process (all services, all jobs).
This closes the gap where each enrichment pool / job previously spun up its own
uncoordinated contexts.

The limiter is a module-level singleton so it is shared no matter how services or
jobs are constructed.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

#: Default cap on simultaneously-active YoutubeDL contexts (Phase 1: conservative).
DEFAULT_MAX_YTDL_CONTEXTS = 4


class YtdlContextLimiter:
    """Bounded permit holder for active ``YoutubeDL`` contexts."""

    def __init__(self, max_contexts: int = DEFAULT_MAX_YTDL_CONTEXTS) -> None:
        self._max = max(1, int(max_contexts))
        self._sem = threading.Semaphore(self._max)

    @contextmanager
    def acquire(self) -> Iterator[None]:
        self._sem.acquire()
        try:
            yield
        finally:
            self._sem.release()

    @property
    def max_contexts(self) -> int:
        return self._max


_GLOBAL: YtdlContextLimiter | None = None
_GLOBAL_LOCK = threading.Lock()


def get_ytdl_limiter(
    max_contexts: int = DEFAULT_MAX_YTDL_CONTEXTS,
) -> YtdlContextLimiter:
    """Return the process-wide YoutubeDL context limiter (created once)."""
    global _GLOBAL
    if _GLOBAL is None:
        with _GLOBAL_LOCK:
            if _GLOBAL is None:
                _GLOBAL = YtdlContextLimiter(max_contexts)
    return _GLOBAL
