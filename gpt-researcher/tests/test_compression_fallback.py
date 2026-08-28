"""
Regression tests for the "out of index -> full document" fallback bug.

Previously, when a corpus exceeded COMPRESSION_THRESHOLD (8000 chars) the
SafeEmbeddingsFilter ran at the (often too-strict) similarity threshold. With
multilingual embeddings, borderline-relevant chunks routinely scored below the
threshold, so the filter returned an EMPTY list -> the caller in
ContextCompressor.async_get_context fell back to dumping the raw documents
(truncated to 1500 chars each / 8000 total) into the prompt.

The fix makes SafeEmbeddingsFilter return the top-k chunks by similarity instead
of an empty list, so the raw-document fallback is never triggered.
"""

import asyncio
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from gpt_researcher.context.compression import ContextCompressor, SafeEmbeddingsFilter


class _FakeEmbeddings(Embeddings):
    """Deterministic embeddings: chunk i embeds to a unit vector at angle i*0.6 rad.

    Query embeds to [1, 0] (angle 0), so similarity(chunk i) = cos(i * 0.6),
    giving distinct, monotonically varying scores (idx0 highest, idx2 below 0.42).
    """

    def embed_documents(self, texts):
        import math
        return [[math.cos(i * 0.6), math.sin(i * 0.6)] for i in range(len(texts))]

    def embed_query(self, text):
        return [1.0, 0.0]


def _make_doc_docs(n, size=1000):
    docs = []
    for i in range(n):
        content = f"DOCUMENT_{i} " + ("x" * (size - len(f"DOCUMENT_{i} ") - 1))
        docs.append(Document(page_content=content, metadata={"idx": i}))
    return docs


def _make_dict_docs(n, size=1000):
    docs = []
    for i in range(n):
        content = f"DOCUMENT_{i} " + ("x" * (size - len(f"DOCUMENT_{i} ") - 1))
        docs.append({"title": f"DOCUMENT_{i}", "raw_content": content, "url": f"http://x/{i}"})
    return docs


def test_safe_filter_returns_topk_when_threshold_too_high():
    docs = _make_doc_docs(4)
    # Threshold 2.0 is impossible for cosine -> threshold filter yields nothing,
    # so the filter must return the top-k by similarity, NOT an empty list.
    flt = SafeEmbeddingsFilter(embeddings=_FakeEmbeddings(), similarity_threshold=2.0, min_return=10)
    out = flt.compress_documents(docs, "query")
    assert out, "filter must not return an empty list"
    scores = [d.metadata["query_similarity_score"] for d in out]
    assert scores == sorted(scores, reverse=True), "results must be sorted by similarity desc"
    # Most similar doc is index 0 (angle 0 == query).
    assert out[0].metadata["idx"] == 0


def test_safe_filter_respects_min_return_cap():
    docs = _make_doc_docs(15)
    flt = SafeEmbeddingsFilter(embeddings=_FakeEmbeddings(), similarity_threshold=2.0, min_return=10)
    out = flt.compress_documents(docs, "query")
    assert len(out) == 10


def test_safe_filter_returns_threshold_passers_when_present():
    docs = _make_doc_docs(4)
    # cos(0)=1.0 (idx0) and cos(0.6)=0.825 (idx1) clear 0.42; cos(1.2)=0.362 (idx2) does not.
    flt = SafeEmbeddingsFilter(embeddings=_FakeEmbeddings(), similarity_threshold=0.42, min_return=10)
    out = flt.compress_documents(docs, "query")
    idxs = sorted(d.metadata["idx"] for d in out)
    assert idxs == [0, 1]


def test_large_corpus_does_not_fall_back_to_full_document():
    # 12 docs x 1000 chars = 12000 chars -> exceeds COMPRESSION_THRESHOLD (8000),
    # so the embedding path runs. A too-strict threshold (2.0) used to produce an
    # empty filter result -> raw-document dump. Assert that no longer happens.
    # ContextCompressor receives dicts in production (scraped page records).
    docs = _make_dict_docs(12, size=1000)
    compressor = ContextCompressor(
        documents=docs,
        embeddings=_FakeEmbeddings(),
        similarity_threshold=2.0,
        max_results=10,
    )

    calls = {"fallback": 0}

    def spy(*args, **kwargs):
        calls["fallback"] += 1
        raise AssertionError("raw-document fallback should not be triggered")

    compressor._to_fallback_docs = spy

    context = asyncio.run(compressor.async_get_context("query", max_results=10))
    assert calls["fallback"] == 0, "raw-document fallback was triggered"
    assert "DOCUMENT_3" in context, "most-similar document should be present in context"
    # The context should be focused (ranked), not the entire ~12000-char corpus.
    assert len(context) < 12000


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
