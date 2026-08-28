"""Context compression utilities for GPT Researcher.

This module provides classes for compressing and retrieving relevant
context from documents using embeddings and similarity filtering.

The compression pipeline:
1. Filters out invalid/empty documents
2. Splits documents into chunks
3. Filters chunks by embedding similarity to the query
4. Returns the most relevant chunks as context

Classes:
    VectorstoreCompressor: Retrieves context from a vector store.
    ContextCompressor: Compresses raw documents using embedding similarity.
    WrittenContentCompressor: Compresses previously written content sections.
    ValidContentFilter: Custom filter to remove empty/trivial documents.
"""

import asyncio
import os
from typing import Optional, List

from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import (
    DocumentCompressorPipeline,
    EmbeddingsFilter,
)
from langchain_core.callbacks import Callbacks
from langchain_core.documents import Document
from langchain_core.documents.compressor import BaseDocumentCompressor
from sklearn.metrics.pairwise import cosine_similarity
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..memory.embeddings import OPENAI_EMBEDDING_MODEL
from ..memory.resilient_embeddings import ResilientEmbeddingsAdapter
from ..prompts import PromptFamily
from ..utils.costs import estimate_embedding_cost
from ..utils.logger import get_formatted_logger
from ..vector_store import VectorStoreWrapper
from .retriever import SearchAPIRetriever, SectionRetriever

logger = get_formatted_logger()


class ValidContentFilter(BaseDocumentCompressor):
    """Custom filter that removes documents with empty or trivial content.

    This filter prevents IndexError in EmbeddingsFilter by ensuring only
    documents with valid content reach the embedding stage. Documents with
    empty, None, or content shorter than min_chars are filtered out.

    Attributes:
        min_chars: Minimum character length for content to be considered valid.
    """

    def __init__(self, min_chars: int = 10):
        """Initialize ValidContentFilter.

        Args:
            min_chars: Minimum character length for valid content. Default 10.
        """
        super().__init__()
        # Bypass Pydantic validation for this attribute
        object.__setattr__(self, 'min_chars', min_chars)

    def _is_valid_content(self, doc: Document) -> bool:
        """Check if document has valid content.

        Args:
            doc: Document to validate.

        Returns:
            True if document has valid content, False otherwise.
        """
        content = doc.page_content or ""
        return len(content.strip()) >= self.min_chars

    def compress_documents(
        self,
        documents: list[Document],
        query: str,
        callbacks: Callbacks | None = None,
    ) -> list[Document]:
        """Filter documents to only those with valid content.

        Args:
            documents: List of documents to filter.
            query: Query string (unused, but required by interface).
            callbacks: Optional callbacks.

        Returns:
            List of documents with valid content.
        """
        original_count = len(documents)
        valid_docs = [doc for doc in documents if self._is_valid_content(doc)]

        if len(valid_docs) < original_count:
            logger.debug(
                "ValidContentFilter: filtered %d/%d documents with content < %d chars",
                original_count - len(valid_docs),
                original_count,
                self.min_chars,
            )

        return valid_docs

    async def acompress_documents(
        self,
        documents: list[Document],
        query: str,
        callbacks: Callbacks | None = None,
    ) -> list[Document]:
        """Async version of compress_documents."""
        return self.compress_documents(documents, query, callbacks)


class SafeEmbeddingsFilter(EmbeddingsFilter):
    """
    A wrapper around EmbeddingsFilter that handles mismatched document/embedding lists.

    Key behaviour: it NEVER returns an empty list. When nothing clears the
    similarity threshold (or the doc/score lists are mismatched), it returns the
    top-``min_return`` chunks ranked by similarity instead. This prevents the
    caller from falling back to dumping the raw, un-ranked documents into the
    prompt ("out of index -> full document").
    """

    def __init__(self, embeddings=None, similarity_threshold=None, min_return: int = 10, **kwargs):
        super().__init__(embeddings=embeddings, similarity_threshold=similarity_threshold)
        # Bypass Pydantic validation for this attribute (same pattern as ValidContentFilter).
        object.__setattr__(self, "min_return", int(min_return))

    def _top_k_by_similarity(self, documents, similarity_scores, k: int) -> List[Document]:
        """Return the top-``k`` documents by descending similarity score."""
        if not documents:
            return []
        k = min(k, len(documents))
        paired = sorted(
            zip(documents, similarity_scores),
            key=lambda pair: pair[1],
            reverse=True,
        )
        result = []
        for doc, score in paired[:k]:
            doc_copy = Document(
                page_content=doc.page_content,
                metadata=doc.metadata.copy() if doc.metadata else {},
            )
            doc_copy.metadata["query_similarity_score"] = score
            result.append(doc_copy)
        return result

    def compress_documents(
        self,
        documents: List[Document],
        query: str,
        callbacks: Callbacks | None = None,
    ) -> List[Document]:
        """
        Compress documents by embedding similarity, with safety checks.

        Returns the most relevant chunks. Unlike the base filter, this never
        returns an empty list: if the threshold filters everything out (common
        with strict thresholds like 0.42 on multilingual embeddings), it returns
        the top-``min_return`` chunks by similarity so the caller keeps focused,
        relevant context instead of falling back to the full raw documents.
        """
        try:
            # Get embeddings for the documents and query
            doc_embeddings = self.embeddings.embed_documents([d.page_content for d in documents])
            query_embedding = self.embeddings.embed_query(query)

            # Calculate similarity scores
            similarity_scores = cosine_similarity([query_embedding], doc_embeddings)[0]

            # Safety check: Ensure similarity_scores length matches documents.
            # If they don't, we cannot safely rank, so return the leading chunks
            # rather than an empty list (which would trigger a raw-doc dump).
            if len(similarity_scores) != len(documents):
                logger.warning(
                    "Mismatch between documents (%d) and similarity scores (%d). "
                    "Returning leading %d chunks instead of skipping the filter.",
                    len(documents), len(similarity_scores), self.min_return
                )
                return [d for d in documents[: self.min_return]]

            # Assign similarity scores to documents
            stateful_documents = []
            for i, doc in enumerate(documents):
                # Create a copy of the document to avoid modifying the original
                doc_copy = Document(
                    page_content=doc.page_content,
                    metadata=doc.metadata.copy() if doc.metadata else {}
                )
                doc_copy.metadata["query_similarity_score"] = similarity_scores[i]
                stateful_documents.append(doc_copy)

            # Filter documents by similarity threshold
            filtered_documents = [
                doc for doc in stateful_documents
                if doc.metadata.get("query_similarity_score", 0) >= self.similarity_threshold
            ]

            if filtered_documents:
                return filtered_documents

            # Nothing cleared the threshold: return the top-k most similar chunks
            # instead of an empty list. This is the fix for the "out of index ->
            # full document" fallback path.
            logger.info(
                "No chunks cleared similarity_threshold=%.2f; returning top-%d chunks by "
                "similarity instead of an empty result (avoids raw-document fallback).",
                self.similarity_threshold, self.min_return
            )
            return self._top_k_by_similarity(stateful_documents, similarity_scores, self.min_return)

        except Exception as e:
            logger.warning(
                "EmbeddingsFilter failed with %s; returning leading chunks as fallback.",
                str(e),
                exc_info=True,
            )
            # Avoid the empty-list -> raw-document-dump path when embedding fails.
            return [d for d in documents[: self.min_return]]

    async def acompress_documents(
        self,
        documents: List[Document],
        query: str,
        callbacks: Callbacks | None = None,
    ) -> List[Document]:
        """Async version of compress_documents."""
        return self.compress_documents(documents, query, callbacks)


class VectorstoreCompressor:
    """Retrieves and compresses context from a vector store.

    Uses similarity search on an existing vector store to find
    relevant documents for a given query.

    Attributes:
        vector_store: The vector store wrapper to search.
        max_results: Maximum number of results to return.
        filter: Optional filter for vector store queries.
    """

    def __init__(
        self,
        vector_store: VectorStoreWrapper,
        max_results: int = 7,
        filter: Optional[dict] = None,
        prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
        **kwargs,
    ):
        """Initialize the VectorstoreCompressor.

        Args:
            vector_store: The vector store to search.
            max_results: Maximum number of results to return.
            filter: Optional filter dictionary for queries.
            prompt_family: Prompt family for formatting output.
            **kwargs: Additional keyword arguments.
        """
        self.vector_store = vector_store
        self.max_results = max_results
        self.filter = filter
        self.kwargs = kwargs
        self.prompt_family = prompt_family

    async def async_get_context(self, query: str, max_results: int = 5) -> str:
        """Get relevant context from the vector store.

        Args:
            query: The search query.
            max_results: Maximum number of results to return.

        Returns:
            Formatted string of relevant document content.
        """
        results = await self.vector_store.asimilarity_search(query=query, k=max_results, filter=self.filter)
        return self.prompt_family.pretty_print_docs(results)


class ContextCompressor:
    """Compresses raw documents to extract relevant context.

    Uses embedding similarity to filter document chunks and return
    only the most relevant content for a given query.

    Attributes:
        documents: List of documents to compress.
        embeddings: Embedding model for similarity calculation.
        max_results: Maximum number of results to return.
        similarity_threshold: Minimum similarity score for inclusion.
    """

    def __init__(
        self,
        documents,
        embeddings,
        max_results: int = 5,
        similarity_threshold: float | None = None,
        prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
        **kwargs,
    ):
        """Initialize the ContextCompressor.

        Args:
            documents: List of documents to compress.
            embeddings: Embedding model instance.
            max_results: Maximum number of results to return.
            similarity_threshold: Minimum similarity score for inclusion.
                Falls back to the SIMILARITY_THRESHOLD env var when not given.
            prompt_family: Prompt family for formatting output.
            **kwargs: Additional keyword arguments.
        """
        self.max_results = max_results
        self.documents = documents
        self.kwargs = kwargs
        self.embeddings = embeddings if isinstance(embeddings, ResilientEmbeddingsAdapter) else ResilientEmbeddingsAdapter(embeddings)
        if similarity_threshold is None:
            similarity_threshold = float(os.environ.get("SIMILARITY_THRESHOLD", 0.35))
        self.similarity_threshold = similarity_threshold
        self.prompt_family = prompt_family

    def _to_documents(
        self,
        docs,
        max_results: Optional[int] = None,
        max_chars_per_doc: int = 1500,
        max_total_chars: int = 8000
    ) -> list[Document]:
        """Convert raw documents into LangChain Document objects for fallback formatting safely without context explosion."""
        selected_docs = docs if max_results is None else docs[:max_results]
        direct_docs = []
        accumulated_chars = 0

        for doc in selected_docs:
            if accumulated_chars >= max_total_chars:
                break
            if isinstance(doc, Document):
                page_content = doc.page_content or ""
                metadata = dict(getattr(doc, "metadata", {}) or {})
            elif isinstance(doc, dict):
                page_content = doc.get("raw_content", "") or doc.get("page_content", "") or ""
                metadata = {
                    "title": doc.get("title", "") or "",
                    "source": doc.get("source") or doc.get("url") or "",
                }
            else:
                page_content = getattr(doc, "page_content", "") or getattr(doc, "raw_content", "") or str(doc)
                metadata = getattr(doc, "metadata", {}) or {}

            # Truncate each fallback document safely to max_chars_per_doc
            if len(page_content) > max_chars_per_doc:
                page_content = page_content[:max_chars_per_doc].strip() + "... [Content Truncated]"

            if accumulated_chars + len(page_content) > max_total_chars:
                allowed_len = max(100, max_total_chars - accumulated_chars)
                page_content = page_content[:allowed_len].strip() + "... [Content Truncated]"

            accumulated_chars += len(page_content)
            direct_docs.append(Document(page_content=page_content, metadata=metadata))

        return direct_docs

    def __get_contextual_retriever(self, pages=None):
        """Build the contextual compression retriever pipeline.

        Returns:
            A ContextualCompressionRetriever configured with:
            1. ValidContentFilter - removes empty/trivial documents
            2. RecursiveCharacterTextSplitter - splits into chunks
            3. EmbeddingsFilter - filters by embedding similarity
        """
        if pages is None:
            pages = self.documents

        # Custom filter to prevent EmbeddingsFilter IndexError by removing
        # documents with empty or trivial content before embedding
        valid_content_filter = ValidContentFilter(min_chars=10)
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        relevance_filter = SafeEmbeddingsFilter(
            embeddings=self.embeddings,
            similarity_threshold=self.similarity_threshold
        )
        pipeline_compressor = DocumentCompressorPipeline(
            transformers=[valid_content_filter, splitter, relevance_filter]
        )
        base_retriever = SearchAPIRetriever(
            pages=pages
        )
        contextual_retriever = ContextualCompressionRetriever(
            base_compressor=pipeline_compressor, base_retriever=base_retriever
        )
        return contextual_retriever

    def _filter_documents(self) -> list:
        """Filter documents to remove empty or trivial content before compression."""
        filtered = []
        for doc in self.documents:
            content = ""
            if isinstance(doc, dict):
                content = (doc.get("raw_content") or doc.get("page_content") or "").strip()
            elif isinstance(doc, Document):
                content = (doc.page_content or "").strip()
            else:
                content = str(getattr(doc, "page_content", "") or getattr(doc, "raw_content", "") or "").strip()

            if len(content) >= 20:
                filtered.append(doc)

        return filtered

    def _to_fallback_docs(self, docs, max_results: Optional[int] = None) -> list[Document]:
        """Convert input documents to a safe fallback document list without raising."""
        selected = docs if max_results is None else docs[:max_results]
        return self._to_documents(selected, max_results=max_results)

    async def async_get_context(self, query: str, max_results: int = 5, cost_callback=None) -> str:
        """Get relevant context from documents asynchronously via strict vector embedding filtering.

        STRICT EMBEDDING POLICY: 100% of context delivered to the LLM must pass through 
        vector embeddings similarity filtering. Zero un-embedded raw documents are permitted.

        Args:
            query: The search query.
            max_results: Maximum number of vector-filtered results to return.
            cost_callback: Optional callback for tracking embedding costs.

        Returns:
            Formatted string of relevant vector-filtered document content.
        """
        if not self.documents:
            return ""

        total_chars = 0
        for doc in self.documents:
            if isinstance(doc, Document):
                total_chars += len(doc.page_content or "")
            elif isinstance(doc, dict):
                total_chars += len((doc.get("raw_content") or doc.get("page_content") or ""))
            else:
                total_chars += len(str(getattr(doc, "page_content", "") or getattr(doc, "raw_content", "") or ""))

        chunk_threshold = int(os.environ.get("COMPRESSION_THRESHOLD", "8000"))
        if total_chars < chunk_threshold and len(self.documents) <= max_results:
            direct_docs = []
            for doc in self.documents[:max_results]:
                if isinstance(doc, Document):
                    page_content = doc.page_content or ""
                    metadata = dict(getattr(doc, "metadata", {}) or {})
                elif isinstance(doc, dict):
                    page_content = doc.get("raw_content", "") or doc.get("page_content", "") or ""
                    metadata = {
                        "title": doc.get("title", "") or "",
                        "source": doc.get("source") or doc.get("url") or "",
                    }
                else:
                    page_content = str(getattr(doc, "page_content", "") or getattr(doc, "raw_content", "") or "")
                    metadata = getattr(doc, "metadata", {}) or {}

                direct_docs.append(Document(page_content=page_content, metadata=metadata))
            return self.prompt_family.pretty_print_docs(direct_docs, max_results)

        filtered_documents = self._filter_documents()
        if not filtered_documents:
            logger.warning("No valid documents available for contextual compression retriever.")
            return ""

        compressed_docs = self.__get_contextual_retriever(filtered_documents)
        if cost_callback:
            cost_callback(estimate_embedding_cost(model=OPENAI_EMBEDDING_MODEL, docs=filtered_documents))

        try:
            relevant_docs = await asyncio.to_thread(compressed_docs.invoke, query, **self.kwargs)
        except (IndexError, ValueError, TypeError, RuntimeError) as e:
            logger.warning(
                "Contextual compression retriever failed with %s; falling back to raw document content.",
                type(e).__name__,
            )
            relevant_docs = []
        except Exception as e:
            logger.error(f"Error in contextual compression retriever: {e}")
            relevant_docs = []

        # Guard against malformed or inconsistent retrieval results.
        if not relevant_docs:
            if filtered_documents:
                logger.warning(
                    "Contextual compression retriever failed or returned no results; falling back to raw document content."
                )
                fallback_docs = self._to_fallback_docs(filtered_documents, max_results=max_results)
                return self.prompt_family.pretty_print_docs(fallback_docs, max_results)
            return ""

        if not all(isinstance(doc, Document) for doc in relevant_docs):
            logger.warning("Contextual compression retriever returned non-Document results; falling back to raw content.")
            fallback_docs = self._to_fallback_docs(filtered_documents, max_results=max_results)
            return self.prompt_family.pretty_print_docs(fallback_docs, max_results)

        return self.prompt_family.pretty_print_docs(relevant_docs, max_results)

    def get_context(self, query: str, max_results: int = 5, max_chars: int = 15000) -> str:
        """Get compressed context for a query with robust fallback handling.

        Args:
            query: Query string.
            max_results: Maximum number of results to return.
            max_chars: Maximum number of characters in the context.

        Returns:
            Compressed context string.
        """
        try:
            # First try contextual compression
            contextual_retriever = self.__get_contextual_retriever()
            compressed_docs = contextual_retriever.get_relevant_documents(query)
            if compressed_docs:
                formatted_context = self.prompt_family.pretty_print_docs(compressed_docs)
                logger.debug("Successfully retrieved compressed context.")
                return formatted_context
        except IndexError as e:
            logger.warning(
                "IndexError in contextual compression (likely mismatched document/similarity lists): %s; falling back to raw document content.",
                str(e),
                exc_info=True,
            )
        except Exception as e:
            logger.warning(
                "Contextual compression retriever failed with %s; falling back to raw document content.",
                str(e),
                exc_info=True,
            )

        # Fallback: use raw documents if compression fails
        logger.info("Using raw document content as fallback.")
        fallback_docs = self._to_documents(self.documents, max_results=max_results)
        return self.prompt_family.pretty_print_docs(fallback_docs[:max_results])


class WrittenContentCompressor:
    """Compresses previously written content sections.

    Specialized compressor for finding relevant sections from
    previously written report content, preserving section titles
    and structure.

    Attributes:
        documents: List of written content sections.
        embeddings: Embedding model for similarity calculation.
        similarity_threshold: Minimum similarity score for inclusion.
    """

    def __init__(self, documents, embeddings, similarity_threshold: float, **kwargs):
        """Initialize the WrittenContentCompressor.

        Args:
            documents: List of written content sections.
            embeddings: Embedding model instance.
            similarity_threshold: Minimum similarity score for inclusion.
            **kwargs: Additional keyword arguments.
        """
        self.documents = documents or []
        self.kwargs = kwargs
        self.embeddings = embeddings if isinstance(embeddings, ResilientEmbeddingsAdapter) else ResilientEmbeddingsAdapter(embeddings)
        self.similarity_threshold = similarity_threshold

    def __get_contextual_retriever(self):
        """Build the contextual compression retriever for sections.

        Returns:
            A ContextualCompressionRetriever configured for section retrieval.
        """
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        relevance_filter = EmbeddingsFilter(embeddings=self.embeddings,
                                            similarity_threshold=self.similarity_threshold)
        pipeline_compressor = DocumentCompressorPipeline(
            transformers=[splitter, relevance_filter]
        )
        base_retriever = SectionRetriever(
            sections=self.documents
        )
        contextual_retriever = ContextualCompressionRetriever(
            base_compressor=pipeline_compressor, base_retriever=base_retriever
        )
        return contextual_retriever

    def __pretty_docs_list(self, docs, top_n: int) -> list[str]:
        """Format documents as a list of title/content strings.

        Args:
            docs: List of documents to format.
            top_n: Maximum number of documents to include.

        Returns:
            List of formatted document strings.
        """
        return [f"Title: {d.metadata.get('section_title')}\nContent: {d.page_content}\n" for i, d in enumerate(docs) if i < top_n]

    async def async_get_context(self, query: str, max_results: int = 5, cost_callback=None) -> list[str]:
        """Get relevant written content sections asynchronously.

        Args:
            query: The search query.
            max_results: Maximum number of results to return.
            cost_callback: Optional callback for tracking embedding costs.

        Returns:
            List of formatted section strings.
        """
        if not self.documents:
            return []

        compressed_docs = self.__get_contextual_retriever()
        if cost_callback:
            cost_callback(estimate_embedding_cost(model=OPENAI_EMBEDDING_MODEL, docs=self.documents))
        
        try:
            relevant_docs = await asyncio.to_thread(compressed_docs.invoke, query, **self.kwargs)
        except Exception:
            relevant_docs = []

        return self.__pretty_docs_list(relevant_docs, max_results)
