from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
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


@dataclass
class EmbeddingRateLimitConfig:
    """User-configurable rate-limit budget for one embedding caller.

    * ``max_tokens_per_minute`` — token budget (TPM), enforced per-caller. Set 0
      to disable token pacing. This is the per-module knob the UI exposes.
    * ``encoding_name`` — tiktoken encoding used to count tokens for the TPM budget.
    * ``enable_shared_rpm`` — when True, this caller also participates in the
      single, project-wide request limiter (the only correct guard against the
      shared Gemini free-tier 429). Disabled by default because the Gemini
      embedder is usually already wrapped with the global RPM limiter upstream
      (see ``build_embeddings``). Enable it only on raw embedders.
    """

    max_tokens_per_minute: int = 0
    encoding_name: str = "cl100k_base"
    tpm_window_seconds: int = 70
    enable_shared_rpm: bool = False

    @property
    def tpm_enabled(self) -> bool:
        return self.max_tokens_per_minute and self.max_tokens_per_minute > 0


class RateLimitedEmbedder:
    """Unified rate-limiting wrapper shared by EVERY embedding caller.

    This is the single pattern used by ingestion, gpt-researcher and
    content-homophily so their rate limiting cannot drift apart. It paces
    ``embed_documents``/``embed_query`` by:

    * an optional per-caller **token** budget (TPM), and
    * the optional project-wide **request** budget (RPM, shared singleton).

    Nothing is ever dropped: requests queue (sleep) until budget is available.

    The wrapper is a transparent proxy: any attribute not defined here (e.g.
    ``model_name``, ``batch_size``) is delegated to the wrapped embedder.
    """

    def __init__(self, embedder: Any, config: EmbeddingRateLimitConfig | None = None) -> None:
        self._embedder = embedder
        cfg = config or EmbeddingRateLimitConfig()

        self._tpm: Any = None
        if cfg.tpm_enabled:
            from Ingestion_Pipline.infra.rate_limiter import TokenRateLimiter

            self._tpm = TokenRateLimiter(
                max_tokens_per_minute=cfg.max_tokens_per_minute,
                encoding_name=cfg.encoding_name,
                window_seconds=cfg.tpm_window_seconds,
            )

        self._rpm: Any = None
        if cfg.enable_shared_rpm:
            self._rpm = _get_global_embed_request_limiter()

    def _throttle_tokens(self, texts) -> None:
        if self._tpm is None:
            return
        self._tpm.throttle(self._tpm.count_tokens_text(list(texts)))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if self._rpm is not None:
            self._rpm.acquire()
        self._throttle_tokens(texts)
        return self._embedder.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        if self._rpm is not None:
            self._rpm.acquire()
        self._throttle_tokens([text])
        return self._embedder.embed_query(text)

    def __getattr__(self, name: str) -> Any:
        # Delegate any other attribute (model_name, batch_size, etc.) to the
        # wrapped embedder so callers see a transparent proxy.
        return getattr(self._embedder, name)


#: Backwards-compatible alias for the old RPM-only wrapper.
_RequestRateLimitedEmbedder = RateLimitedEmbedder

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
    historical default). The returned embedder is wrapped with the project-wide
    request limiter so every caller shares the single Gemini 429 guard.
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

    if _get_global_embed_request_limiter() is not None:
        embedder = RateLimitedEmbedder(embedder, EmbeddingRateLimitConfig(enable_shared_rpm=True))
    return embedder
