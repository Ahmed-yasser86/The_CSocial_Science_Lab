import asyncio
import time
from typing import Dict, Coroutine, Optional

# Simple global registry to track outstanding embedding requests across the process.
# Callers can register a coroutine that will complete when an embedding request finishes
# (for example, pipeline._wait_for_completion(request_id)). Later, code can await
# wait_all() to block until all registered embedding coroutines finish.

_registry: Dict[str, asyncio.Task] = {}
_lock = None
_lock_loop = None


def _get_lock() -> asyncio.Lock:
    global _lock, _lock_loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if _lock is None or _lock_loop != loop:
        _lock = asyncio.Lock()
        _lock_loop = loop
    return _lock


async def register(request_id: str, waiter: Coroutine) -> asyncio.Task:
    """Register an embedding waiter coroutine under request_id.

    The waiter will be wrapped in a Task so it runs independently.
    Returns the asyncio.Task created so callers can await its result if needed.
    """
    async with _get_lock():
        if request_id in _registry:
            # Already registered — don't replace
            return _registry[request_id]
        task = asyncio.create_task(_wrap_and_remove(request_id, waiter))
        _registry[request_id] = task
        return task


async def _wrap_and_remove(request_id: str, waiter: Coroutine) -> None:
    try:
        await waiter
    except Exception:
        # swallow - registry is for coordination, not failure routing
        pass
    finally:
        async with _get_lock():
            _registry.pop(request_id, None)


async def wait_all(timeout: Optional[float] = None) -> None:
    """Wait for all currently-registered embedding waiters to finish.

    If timeout is provided, wait at most that many seconds.
    """
    start = time.time()
    while True:
        async with _get_lock():
            tasks = list(_registry.values())
        if not tasks:
            return
        done, pending = await asyncio.wait(tasks, timeout=0.5)
        if timeout is not None and (time.time() - start) > timeout:
            return


async def pending_count() -> int:
    async with _get_lock():
        return len(_registry)
