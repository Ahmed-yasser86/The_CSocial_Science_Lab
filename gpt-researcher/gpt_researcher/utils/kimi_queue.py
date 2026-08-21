"""
Kimi / Moonshot Sequential Queue Worker module.

Provides a dedicated single-worker asyncio queue manager for Kimi (Moonshot AI) models.
Since Kimi models can be slow and have low concurrency limits, all requests targeting
Kimi / Moonshot models are queued and executed sequentially (concurrency = 1) with automatic
persistent retries until each request succeeds.
"""

import asyncio
import logging
import os
from typing import Callable, Any, Optional

import sys

logger = logging.getLogger("kimi_queue")


def _safe_print(msg: str):
    try:
        print(msg)
    except Exception:
        try:
            safe_msg = msg.encode(sys.stdout.encoding or 'ascii', errors='replace').decode(sys.stdout.encoding or 'ascii', errors='replace')
            print(safe_msg)
        except Exception:
            pass


def is_kimi_model(model: Optional[str] = None, provider: Optional[str] = None) -> bool:
    """
    Check if the given model name or provider refers to a Kimi / Moonshot model.
    """
    targets = ["kimi", "moonshot"]
    
    if model:
        m_lower = str(model).lower()
        if any(t in m_lower for t in targets):
            return True

    if provider:
        p_lower = str(provider).lower()
        if any(t in p_lower for t in targets):
            return True

    # Check environment variables
    for env_var in ["SMART_LLM_MODEL", "FAST_LLM_MODEL", "STRATEGIC_LLM_MODEL", "LLM_PROVIDER"]:
        val = os.environ.get(env_var, "").lower()
        if any(t in val for t in targets):
            return True

    return False


class KimiSequentialQueueManager:
    """
    Sequential Queue Worker for Kimi / Moonshot LLM calls.
    Ensures incoming Kimi requests are processed sequentially one by one.
    If a request fails (rate limit, 429, timeout, server error, empty output),
    it automatically retries in a persistent loop until it succeeds.
    """
    _instance: Optional["KimiSequentialQueueManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._queue = None
            cls._instance._worker_task = None
            cls._instance._lock = None
            cls._instance._lock_loop = None
        return cls._instance

    def _get_lock(self) -> asyncio.Lock:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if self._lock is None or self._lock_loop != loop:
            self._lock = asyncio.Lock()
            self._lock_loop = loop
        return self._lock

    async def _ensure_worker_running(self):
        current_loop = asyncio.get_running_loop()
        async with self._get_lock():
            need_reset = False
            if self._queue is None:
                need_reset = True
            else:
                try:
                    queue_loop = getattr(self._queue, "_loop", None) or getattr(self._queue, "_get_loop", lambda: None)()
                    if queue_loop is not current_loop or (queue_loop and queue_loop.is_closed()):
                        need_reset = True
                except Exception:
                    need_reset = True

            if need_reset:
                if self._worker_task and not self._worker_task.done():
                    self._worker_task.cancel()
                self._queue = asyncio.Queue()
                self._worker_task = asyncio.create_task(self._worker_loop())
            elif self._worker_task is None or self._worker_task.done():
                self._worker_task = asyncio.create_task(self._worker_loop())

    async def _worker_loop(self):
        logger.info("🚀 [KimiWorker] Starting sequential Kimi request worker (concurrency=1)...")
        _safe_print("🚀 [KimiWorker] Starting sequential Kimi request worker (concurrency=1)...")
        while True:
            future, func, args, kwargs = await self._queue.get()
            try:
                attempt = 1
                base_delay = 3.0
                max_delay = 30.0

                while True:
                    try:
                        logger.info(f"⏳ [KimiWorker] Executing Kimi request (Attempt {attempt})...")
                        result = await func(*args, **kwargs)
                        
                        if result is None or (isinstance(result, str) and not result.strip()):
                            raise RuntimeError("Empty response received from Kimi model.")
                        
                        logger.info(f"✅ [KimiWorker] Request succeeded on attempt {attempt}!")
                        _safe_print(f"✅ [KimiWorker] Request succeeded on attempt {attempt}!")
                        future.set_result(result)
                        break
                    except Exception as exc:
                        if future.cancelled():
                            logger.warning("⚠️ [KimiWorker] Kimi request was cancelled by caller.")
                            break
                        
                        delay = min(base_delay * (1.5 ** min(attempt - 1, 6)), max_delay)
                        msg = f"⚠️ [KimiWorker] Request attempt {attempt} failed: {exc}. Retrying sequentially in {delay:.1f}s until success..."
                        logger.warning(msg)
                        _safe_print(msg)
                        await asyncio.sleep(delay)
                        attempt += 1
            except Exception as outer_e:
                if not future.done():
                    future.set_exception(outer_e)
            finally:
                self._queue.task_done()

    async def enqueue(self, func: Callable, *args, **kwargs) -> Any:
        await self._ensure_worker_running()
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        await self._queue.put((future, func, args, kwargs))
        depth = self._queue.qsize()
        msg = f"📥 [KimiWorker] Enqueued Kimi request (Current queue depth: {depth})"
        logger.info(msg)
        _safe_print(msg)
        return await future
        return await future


_kimi_queue_manager = KimiSequentialQueueManager()


async def execute_via_kimi_queue(func: Callable, *args, **kwargs) -> Any:
    """
    Route a function execution through the Kimi Sequential Queue Worker.
    """
    return await _kimi_queue_manager.enqueue(func, *args, **kwargs)
