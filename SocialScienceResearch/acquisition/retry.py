"""Tenacity retry policies for the acquisition layer.

Follows the project's ``infra/retry_policies.py`` convention: factory
functions that return configured tenacity retry decorators. Only *retryable*
error types (network, rate limit) are retried; permanent failures propagate
immediately.
"""

from __future__ import annotations

import logging
import random
from typing import Any, Callable

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from SocialScienceResearch.utils.logger import get_logger

from .errors import NetworkError, RateLimitError

logger = get_logger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, (NetworkError, RateLimitError))


def retry_policy(
    retries: int = 10,
    backoff: float = 5.0,
    max_wait: float = 120.0,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Return a tenacity retry decorator for transient acquisition failures.

    Uses exponential backoff starting at ``backoff`` seconds, capped at
    ``max_wait``, with jitter. A rate-limit error carrying a ``retry_after``
    (e.g. from a ``Retry-After`` header) is obeyed exactly. Retries only
    ``NetworkError``/``RateLimitError``.
    """

    def _wait_for(retry_state: object) -> float:
        """Backoff that honors a server ``Retry-After`` on rate-limit errors.

        A ``RateLimitError.retry_after`` (seconds) is obeyed exactly;
        otherwise exponential backoff (with jitter) capped at ``max_wait``.
        """
        attempt = getattr(retry_state, "attempt_number", 1)
        outcome = getattr(retry_state, "outcome", None)
        exc = outcome.exception() if outcome is not None else None
        if isinstance(exc, RateLimitError) and exc.retry_after:
            return float(exc.retry_after)
        base = min(backoff * (2 ** (attempt - 1)), max_wait)
        return base + random.uniform(0, min(base, 2.0))

    return retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(max(retries, 1)),
        wait=_wait_for,
        reraise=True,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )


def retry_policy_budgeted(
    budget: Any,
    operation: str,
    run_id: str | None = None,
    retries: int = 10,
    backoff: float = 5.0,
    max_wait: float = 120.0,
    budget_on_first: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Retry policy that routes *every* attempt through the Global Budget
    Controller, so retries never bypass the shared bucket, and records
    rate-limit outcomes via ``budget.on_rate_limited``.

    ``budget_on_first`` controls whether the very first attempt is also charged
    to the budget. When the caller already gates the first attempt (e.g. the
    service layer), set it ``False`` to avoid double-charging; the default
    ``True`` makes the provider the single source of truth for pacing.
    """

    def _before(retry_state: object) -> None:
        attempt = getattr(retry_state, "attempt_number", 1) or 1
        if attempt == 1 and not budget_on_first:
            return
        # cost=None -> the controller applies the operation's weighted cost (Phase 3).
        budget.acquire(operation, run_id=run_id, cost=None)

    def _after(retry_state: object) -> None:
        outcome = getattr(retry_state, "outcome", None)
        if outcome is not None and outcome.failed:
            exc = outcome.exception()
            if isinstance(exc, RateLimitError):
                budget.on_rate_limited(
                    operation=operation,
                    run_id=run_id,
                    detail={"retry_after": getattr(exc, "retry_after", None)},
                )

    def _wait_for(retry_state: object) -> float:
        attempt = getattr(retry_state, "attempt_number", 1) or 1
        outcome = getattr(retry_state, "outcome", None)
        exc = outcome.exception() if outcome is not None else None
        if isinstance(exc, RateLimitError) and exc.retry_after:
            return float(exc.retry_after)
        base = min(backoff * (2 ** (attempt - 1)), max_wait)
        return base + random.uniform(0, min(base, 2.0))

    return retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(max(retries, 1)),
        wait=_wait_for,
        before=_before,
        after=_after,
        reraise=True,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
