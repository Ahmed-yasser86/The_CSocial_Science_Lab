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
) -> Any:
    """Build an embedder, honoring the ``EMBEDDING`` env var.

    ``EMBEDDING`` is ``provider:model`` — e.g. ``cohere:embed-multilingual-v3.0``,
    ``openai:text-embedding-3-large`` or ``google_genai:gemini-embedding-2-preview``.
    When unset or unrecognized, Google Generative AI embeddings are used (the
    historical default).
    """
    settings = settings or EmbeddingSettings()
    spec = (os.environ.get("EMBEDDING") or "").strip()
    if ":" in spec:
        provider, model = spec.split(":", 1)
        provider, model = provider.strip().lower(), model.strip()
    else:
        provider, model = "google_genai", (spec or settings.model or DEFAULT_EMBEDDING_MODEL)

    embedder: Any = None
    if provider in ("cohere",):
        try:
            from langchain_cohere import CohereEmbeddings
        except Exception:
            logger.warning("langchain_cohere unavailable; falling back to Google GenAI embeddings")
        else:
            embedder = CohereEmbeddings(
                model=model or "embed-multilingual-v3.0",
                cohere_api_key=os.environ.get("COHERE_API_KEY", ""),
            )
    elif provider in ("openai", "openai_compatible"):
        try:
            from langchain_openai import OpenAIEmbeddings
        except Exception:
            logger.warning("langchain_openai unavailable; falling back to Google GenAI embeddings")
        else:
            embedder = OpenAIEmbeddings(
                model=model,
                api_key=os.environ.get("OPENAI_API_KEY", ""),
                base_url=os.environ.get("OPENAI_BASE_URL") or None,
            )

    if embedder is None:
        embedder = GoogleGenerativeAIEmbeddings(model=model or settings.model or DEFAULT_EMBEDDING_MODEL)

    limiter = _get_global_embed_request_limiter()
    if limiter is not None:
        embedder = _RequestRateLimitedEmbedder(embedder, limiter)
    return embedder

