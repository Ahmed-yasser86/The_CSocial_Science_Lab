import pytest
from gpt_researcher.context.compression import ContextCompressor


class DummyEmbeddings:
    def embed_query(self, text):
        return [0.1, 0.2, 0.3]

    def embed_documents(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


@pytest.mark.asyncio
async def test_context_compressor_filters_empty_documents():
    compressor = ContextCompressor(
        documents=[
            {"raw_content": "", "url": "https://example.com/empty"},
            {"raw_content": None, "url": "https://example.com/none"},
            {"page_content": "Short", "url": "https://example.com/short"},
            {"raw_content": "A valid content paragraph for testing."},
        ],
        embeddings=DummyEmbeddings(),
        similarity_threshold=0.0,
    )

    result = await compressor.async_get_context("query", max_results=2)

    assert "valid content" in result.lower()
    assert "https://example.com/empty" not in result
    assert "https://example.com/none" not in result
