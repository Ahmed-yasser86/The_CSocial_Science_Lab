from __future__ import annotations

import logging
import os
import threading
from typing import Any

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from Ingestion_Pipline.config.settings import DEFAULT_EMBEDDING_MODEL, EmbeddingSettings

logger = logging.getLogger(__name__)

# Project-wide cap on Gemini embedding *requests* per minute. The Gemini free
# tier quota (``embed_content_free_tier_requests`` = 100/min) is shared by
# EVERY caller in this project (ingestion, retrieval, content-homophily), so a
# per-caller limiter cannot prevent the shared 429. A single global limiter is
# the only correct guard. Env-overridable via GEMINI_EMBED_RPM (set 0 to disable).
_DEFAULT_GLOBAL_EMBED_RPM = 90


def _global_embed_rpm() -> int:
    raw = os.environ.get("GEMINI_EMBED_RPM")
    if raw is None or raw == "":
        return _DEFAULT_GLOBAL_EMBED_RPM
    try:
        return int(raw)
    except ValueError:
        return _DEFAULT_GLOBAL_EMBED_RPM


class _RequestRateLimitedEmbedder:
    """Wrap any embedder so every ``embed_documents``/``embed_query`` call is
    paced by a single, process-wide request limiter (the real Gemini 429 guard).

    Never drops a request: it queues (sleeps) until a request slot is free.
    """

    def __init__(self, embedder: Any, limiter: Any) -> None:
        self._embedder = embedder
        self._limiter = limiter

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self._limiter.acquire()
        return self._embedder.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        self._limiter.acquire()
        return self._embedder.embed_query(text)

    def __getattr__(self, name: str) -> Any:
        # Delegate any other attribute (model_name, batch_size, etc.) to the
        # wrapped embedder so callers see a transparent proxy.
        return getattr(self._embedder, name)


_global_limiter: Any = None
_global_limiter_lock = threading.Lock()


def _get_global_embed_request_limiter() -> Any:
    global _global_limiter
    rpm = _global_embed_rpm()
    if rpm <= 0:
        return None
    if _global_limiter is None:
        with _global_limiter_lock:
            if _global_limiter is None:
                from Ingestion_Pipline.infra.rate_limiter import RequestRateLimiter

                _global_limiter = RequestRateLimiter(max_requests_per_minute=rpm)
                logger.info("Global Gemini embedding request limiter active: %d req/min", rpm)
    return _global_limiter


def build_embeddings(
    settings: EmbeddingSettings | None = None,
) -> GoogleGenerativeAIEmbeddings:
    settings = settings or EmbeddingSettings()
    embedder = GoogleGenerativeAIEmbeddings(model=settings.model or DEFAULT_EMBEDDING_MODEL)
    limiter = _get_global_embed_request_limiter()
    if limiter is not None:
        embedder = _RequestRateLimitedEmbedder(embedder, limiter)
    return embedder

