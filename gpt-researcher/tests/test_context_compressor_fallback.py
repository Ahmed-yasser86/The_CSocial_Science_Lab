import asyncio
from unittest.mock import patch

import pytest
from langchain_core.documents import Document

from gpt_researcher.context.compression import ContextCompressor
from gpt_researcher.memory.resilient_embeddings import ResilientEmbeddingPipeline


class FlakyEmbeddings:
    def __init__(self):
        self.calls = 0

    def embed_query(self, text):
        return self.embed_documents([text])[0]

    def embed_documents(self, texts):
        self.calls += 1
        if self.calls < 3:
            raise RuntimeError("TooManyRequestsError: trial token rate limit exceeded")
        return [[0.1, 0.2, 0.3] for _ in texts]


def test_retry_delay_uses_cohere_headers():
    pipeline = ResilientEmbeddingPipeline(embeddings_instance=FlakyEmbeddings(), retry_forever=True)

    class FakeCohereError(Exception):
        def __init__(self):
            super().__init__("rate limit")
            self.headers = {
                "x-trial-endpoint-call-limit": "100",
                "x-trial-endpoint-call-remaining": "36",
            }

    wait_time = pipeline._get_retry_delay(FakeCohereError(), default_wait=4.0)

    assert wait_time >= 20.0
    assert wait_time <= 25.0


def test_worker_wake_event_can_be_triggered():
    async def run_test():
        pipeline = ResilientEmbeddingPipeline(embeddings_instance=FlakyEmbeddings(), retry_forever=True)
        pipeline.start_worker()

        assert pipeline._worker_wake_event is not None
        pipeline._wake_worker()
        assert pipeline._worker_wake_event.is_set()

        await pipeline.stop_worker()

    asyncio.run(run_test())


@pytest.mark.asyncio
async def test_context_compressor_retries_through_resilient_adapter(monkeypatch):
    monkeypatch.setenv("COMPRESSION_THRESHOLD", "1")

    compressor = ContextCompressor(
        documents=[
            {"raw_content": "Alpha content for fallback", "source": "https://example.com/a"},
            {"raw_content": "Beta content for fallback", "source": "https://example.com/b"},
        ],
        embeddings=FlakyEmbeddings(),
        similarity_threshold=0.0,
    )

    result = await compressor.async_get_context("find relevant content", max_results=2)

    assert "Alpha content for fallback" in result
    assert "Beta content for fallback" in result


@pytest.mark.asyncio
async def test_context_compressor_falls_back_when_retriever_returns_non_documents(monkeypatch):
    monkeypatch.setenv("COMPRESSION_THRESHOLD", "1")

    compressor = ContextCompressor(
        documents=[
            {"raw_content": "Alpha content for fallback", "source": "https://example.com/a"},
            {"raw_content": "Beta content for fallback", "source": "https://example.com/b"},
        ],
        embeddings=FlakyEmbeddings(),
        similarity_threshold=0.0,
    )

    class FakeRetriever:
        def invoke(self, query, **kwargs):
            return ["not-a-document"]

    with patch("gpt_researcher.context.compression.ContextualCompressionRetriever") as retriever_cls:
        retriever_cls.return_value = FakeRetriever()
        result = await compressor.async_get_context("find relevant content", max_results=2)

    assert "Alpha content for fallback" in result
    assert "Beta content for fallback" in result


@pytest.mark.asyncio
async def test_context_compressor_falls_back_when_embedding_filter_index_error(monkeypatch):
    monkeypatch.setenv("COMPRESSION_THRESHOLD", "1")

    compressor = ContextCompressor(
        documents=[
            {"raw_content": "Alpha content for fallback", "source": "https://example.com/a"},
            {"raw_content": "Beta content for fallback", "source": "https://example.com/b"},
        ],
        embeddings=FlakyEmbeddings(),
        similarity_threshold=0.0,
    )

    class FakeRetriever:
        def invoke(self, query, **kwargs):
            raise IndexError("list index out of range")

    with patch("gpt_researcher.context.compression.ContextualCompressionRetriever") as retriever_cls:
        retriever_cls.return_value = FakeRetriever()
        result = await compressor.async_get_context("find relevant content", max_results=2)

    assert "Alpha content for fallback" in result
    assert "Beta content for fallback" in result


@pytest.mark.asyncio
async def test_context_compressor_falls_back_when_embedding_filter_index_error(monkeypatch):
    monkeypatch.setenv("COMPRESSION_THRESHOLD", "1")

    compressor = ContextCompressor(
        documents=[
            {"raw_content": "Alpha content for fallback", "source": "https://example.com/a"},
            {"raw_content": "Beta content for fallback", "source": "https://example.com/b"},
        ],
        embeddings=FlakyEmbeddings(),
        similarity_threshold=0.0,
    )

    class FakeRetriever:
        def invoke(self, query, **kwargs):
            raise IndexError("list index out of range")

    with patch("gpt_researcher.context.compression.ContextualCompressionRetriever") as retriever_cls:
        retriever_cls.return_value = FakeRetriever()
        result = await compressor.async_get_context("find relevant content", max_results=2)

    assert "Alpha content for fallback" in result
    assert "Beta content for fallback" in result
