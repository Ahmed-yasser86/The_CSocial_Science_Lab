"""Verify gpt-researcher Memory applies the shared RateLimitedEmbedder pattern."""

from __future__ import annotations

from Ingestion_Pipline.infra import rate_limiter as rl_mod
from Ingestion_Pipline.infra.embeddings import RateLimitedEmbedder


class _FakeTokenLimiter:
    def __init__(self, max_tokens_per_minute, encoding_name, window_seconds):
        self.max_tokens_per_minute = max_tokens_per_minute
        self.encoding_name = encoding_name
        self.window_seconds = window_seconds
        self.throttle_calls = []

    def count_tokens_text(self, texts):
        return sum(len(str(t).split()) for t in texts)

    def throttle(self, token_count):
        self.throttle_calls.append(token_count)


def test_memory_wraps_embedder_with_tpm(monkeypatch):
    monkeypatch.setenv("GPT_RESEARCHER_EMBED_TPM", "500")
    monkeypatch.setenv("GPT_RESEARCHER_EMBED_ENCODING", "cl100k_base")

    instances = []

    def _make(*args, **kwargs):
        lim = _FakeTokenLimiter(*args, **kwargs)
        instances.append(lim)
        return lim

    monkeypatch.setattr(rl_mod, "TokenRateLimiter", _make)

    from gpt_researcher.memory.embeddings import Memory

    mem = Memory("openai", "text-embedding-3-small")
    emb = mem.get_embeddings()

    assert isinstance(emb, RateLimitedEmbedder)
    assert instances and instances[0].max_tokens_per_minute == 500
    assert instances[0].encoding_name == "cl100k_base"


def test_memory_uses_shared_rpm_when_enabled(monkeypatch):
    monkeypatch.setenv("GPT_RESEARCHER_EMBED_RPM", "1")
    monkeypatch.setenv("GEMINI_EMBED_RPM", "30")
    # Force the global limiter on and reset its cached singleton.
    import Ingestion_Pipline.infra.embeddings as emb_mod

    emb_mod._global_limiter = None

    req_instances = []

    class _FakeReqLimiter:
        def __init__(self, max_requests_per_minute):
            self.max_requests_per_minute = max_requests_per_minute
            self.acquire_calls = 0

        def acquire(self):
            self.acquire_calls += 1

    def _make(*args, **kwargs):
        rpm_val = kwargs.get("max_requests_per_minute", args[0] if args else None)
        lim = _FakeReqLimiter(rpm_val)
        req_instances.append(lim)
        return lim

    monkeypatch.setattr(rl_mod, "RequestRateLimiter", _make)

    from gpt_researcher.memory.embeddings import Memory

    mem = Memory("openai", "text-embedding-3-small")
    emb = mem.get_embeddings()

    assert isinstance(emb, RateLimitedEmbedder)
    assert req_instances and req_instances[0].max_requests_per_minute == 30


def test_memory_unwrapped_when_disabled(monkeypatch):
    monkeypatch.setenv("GPT_RESEARCHER_EMBED_TPM", "0")
    monkeypatch.setenv("GPT_RESEARCHER_EMBED_RPM", "0")

    from gpt_researcher.memory.embeddings import Memory

    mem = Memory("openai", "text-embedding-3-small")
    emb = mem.get_embeddings()

    assert not isinstance(emb, RateLimitedEmbedder)
