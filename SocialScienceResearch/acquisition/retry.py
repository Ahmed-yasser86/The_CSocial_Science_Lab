"""Tenacity retry policies for the acquisition layer.

Follows the project's ``infra/retry_policies.py`` convention: factory
functions that return configured tenacity retry decorators. Only *retryable*
error types (network, rate limit) are retried; permanent failures propagate
immediately.
"""

from __future__ import annotations

import logging
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
    retries: int = 3,
    backoff: float = 2.0,
    max_wait: float = 60.0,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Return a tenacity retry decorator for transient acquisition failures.

    Uses exponential backoff starting at ``backoff`` seconds, capped at
    ``max_wait``. Retries only ``NetworkError``/``RateLimitError``.
    """
    return retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(max(retries, 1)),
        wait=wait_exponential(multiplier=backoff, min=backoff, max=max_wait),
        reraise=True,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
