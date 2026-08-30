"""Tests for the unified embedding rate limiter.

These verify the single ``RateLimitedEmbedder`` pattern used by every embedding
caller (ingestion, gpt-researcher, content-homophily): token budgeting (TPM) and
the project-wide request budget (RPM). No network calls are made.
"""

from __future__ import annotations

import Ingestion_Pipline.infra.embeddings as emb_mod
from Ingestion_Pipline.infra import rate_limiter as rl_mod
from Ingestion_Pipline.infra.embeddings import (
    EmbeddingRateLimitConfig,
    RateLimitedEmbedder,
)


class FakeEmbedder:
    """Minimal embedder that records calls and returns deterministic vectors."""

    model_name = "fake-embedder-123"

    def __init__(self):
        self.docs_calls = []
        self.query_calls = []

    def embed_documents(self, texts):
        self.docs_calls.append(list(texts))
        return [[float(i)] * 3 for i in range(len(texts))]

    def embed_query(self, text):
        self.query_calls.append(text)
        return [1.0, 2.0, 3.0]


class FakeTokenLimiter:
    def __init__(self, max_tokens_per_minute, encoding_name, window_seconds):
        self.max_tokens_per_minute = max_tokens_per_minute
        self.encoding_name = encoding_name
        self.window_seconds = window_seconds
        self.throttle_calls = []

    def count_tokens_text(self, texts):
        # word-count proxy -> deterministic, fast, no tiktoken dependency
        return sum(len(str(t).split()) for t in texts)

    def throttle(self, token_count):
        self.throttle_calls.append(token_count)


class FakeRequestLimiter:
    def __init__(self, max_requests_per_minute):
        self.max_requests_per_minute = max_requests_per_minute
        self.acquire_calls = 0

    def acquire(self):
        self.acquire_calls += 1


def _patch_token_limiter(monkeypatch):
    instances = []

    def _make(*args, **kwargs):
        lim = FakeTokenLimiter(*args, **kwargs)
        instances.append(lim)
        return lim

    monkeypatch.setattr(rl_mod, "TokenRateLimiter", _make)
    return instances


def test_tpm_throttles_before_embedding(monkeypatch):
    instances = _patch_token_limiter(monkeypatch)
    base = FakeEmbedder()
    wrapped = RateLimitedEmbedder(
        base, EmbeddingRateLimitConfig(max_tokens_per_minute=1000)
    )

    vectors = wrapped.embed_documents(["hello world", "foo bar baz"])

    assert len(instances) == 1
    lim = instances[0]
    assert lim.max_tokens_per_minute == 1000
    # token budget = 2 + 3 = 5 words
    assert lim.throttle_calls == [5]
    assert base.docs_calls == [["hello world", "foo bar baz"]]
    assert vectors == [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]


def test_tpm_disabled_when_zero(monkeypatch):
    instances = _patch_token_limiter(monkeypatch)
    base = FakeEmbedder()
    wrapped = RateLimitedEmbedder(base, EmbeddingRateLimitConfig(max_tokens_per_minute=0))

    wrapped.embed_documents(["hi there"])

    # No TokenRateLimiter should be constructed when TPM is disabled.
    assert instances == []
    assert base.docs_calls == [["hi there"]]


def test_rpm_acquires_shared_limiter(monkeypatch):
    # Force the global RPM limiter on and reset its cached singleton.
    monkeypatch.setenv("GEMINI_EMBED_RPM", "45")
    emb_mod._global_limiter = None
    req_instances = []

    def _make(*args, **kwargs):
        lim = FakeRequestLimiter(*args, **kwargs)
        req_instances.append(lim)
        return lim

    monkeypatch.setattr(rl_mod, "RequestRateLimiter", _make)

    base = FakeEmbedder()
    wrapped = RateLimitedEmbedder(
        base, EmbeddingRateLimitConfig(enable_shared_rpm=True)
    )

    wrapped.embed_documents(["a", "b"])
    wrapped.embed_query("q")

    assert len(req_instances) == 1
    assert req_instances[0].max_requests_per_minute == 45
    assert req_instances[0].acquire_calls == 2
    assert base.docs_calls == [["a", "b"]]
    assert base.query_calls == ["q"]


def test_proxy_delegates_attributes():
    base = FakeEmbedder()
    wrapped = RateLimitedEmbedder(base, EmbeddingRateLimitConfig())
    # Attribute not defined on the wrapper is delegated to the wrapped embedder.
    assert wrapped.model_name == "fake-embedder-123"


def test_disabled_wrapper_passes_through():
    base = FakeEmbedder()
    wrapped = RateLimitedEmbedder(base, EmbeddingRateLimitConfig())
    assert wrapped.embed_documents(["x"]) == [[0.0, 0.0, 0.0]]
    assert wrapped.embed_query("y") == [1.0, 2.0, 3.0]
