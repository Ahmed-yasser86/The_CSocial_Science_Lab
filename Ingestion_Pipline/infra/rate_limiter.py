from __future__ import annotations

import asyncio
import logging
import threading
import time

import tiktoken
from langchain_core.documents import Document

from Ingestion_Pipline.config.settings import DEFAULT_MAX_TOKENS_PER_MINUTE, DEFAULT_RATE_LIMIT_ENCODING

logger = logging.getLogger(__name__)

_WINDOW_SECONDS = 70


class TokenRateLimiter:
    def __init__(
        self,
        max_tokens_per_minute: int = DEFAULT_MAX_TOKENS_PER_MINUTE,
        encoding_name: str = DEFAULT_RATE_LIMIT_ENCODING,
        window_seconds: int = _WINDOW_SECONDS,
    ):
        self.max_tokens_per_minute = max_tokens_per_minute
        self.encoding = tiktoken.get_encoding(encoding_name)
        self.window_seconds = window_seconds

        self.tokens_used = 0
        self.window_start = time.monotonic()

        self._lock = asyncio.Lock()
        # Synchronous gate for non-async callers (e.g. the SocialScienceResearch
        # content-homophily embedder, which embeds from a worker thread).
        self._sync_lock = threading.Lock()

    def count_tokens(self, docs: list[Document]) -> int:
        return sum(len(self.encoding.encode(doc.page_content)) for doc in docs)

    def _split_doc_into_sized_chunks(self, doc: Document) -> list[Document]:
        tokens = self.encoding.encode(doc.page_content)
        if len(tokens) <= self.max_tokens_per_minute:
            return [doc]

        chunks: list[Document] = []
        metadata = getattr(doc, "metadata", None)
        for i in range(0, len(tokens), self.max_tokens_per_minute):
            chunk_tokens = tokens[i : i + self.max_tokens_per_minute]
            chunks.append(
                Document(
                    page_content=self.encoding.decode(chunk_tokens),
                    metadata=metadata,
                )
            )

        return chunks

    def _partition_docs_by_limit(self, docs: list[Document]) -> list[list[Document]]:
        batches: list[list[Document]] = []
        current_batch: list[Document] = []
        current_tokens = 0

        for doc in docs:
            doc_tokens = len(self.encoding.encode(doc.page_content))
            if doc_tokens > self.max_tokens_per_minute:
                # Split oversized documents into token-sized chunks.
                for subdoc in self._split_doc_into_sized_chunks(doc):
                    subdoc_tokens = len(self.encoding.encode(subdoc.page_content))
                    if current_batch and current_tokens + subdoc_tokens > self.max_tokens_per_minute:
                        batches.append(current_batch)
                        current_batch = []
                        current_tokens = 0
                    current_batch.append(subdoc)
                    current_tokens += subdoc_tokens
            else:
                if current_batch and current_tokens + doc_tokens > self.max_tokens_per_minute:
                    batches.append(current_batch)
                    current_batch = []
                    current_tokens = 0
                current_batch.append(doc)
                current_tokens += doc_tokens

        if current_batch:
            batches.append(current_batch)

        return batches

    async def acquire(self, docs: list[Document]):
        batches = self._partition_docs_by_limit(docs)
        if len(batches) > 1:
            logger.info(
                "Split request into %d sub-batches to respect TPM limit %d.",
                len(batches), self.max_tokens_per_minute,
            )

        async with self._lock:
            for batch in batches:
                batch_tokens = self.count_tokens(batch)

                while True:
                    now = time.monotonic()
                    elapsed = now - self.window_start

                    if elapsed >= _WINDOW_SECONDS:
                        self.tokens_used = 0
                        self.window_start = now

                    if self.tokens_used + batch_tokens <= self.max_tokens_per_minute:
                        self.tokens_used += batch_tokens
                        logger.info(
                            "TPM: %d/%d", self.tokens_used, self.max_tokens_per_minute,
                        )
                        break

                    wait_time = _WINDOW_SECONDS - elapsed
                    if wait_time <= 0:
                        wait_time = _WINDOW_SECONDS

                    logger.info(
                        "TPM limit reached. Waiting %.1fs...", wait_time,
                    )
                    await asyncio.sleep(wait_time)

    def throttle(self, token_count: int) -> None:
        """Synchronous TPM gate for non-async callers (worker-thread embedders).

        Blocks the calling thread until ``token_count`` tokens can be spent
        within the rolling window. Used by the SocialScienceResearch content-
        homophily analysis to keep its Gemini embedding traffic under a
        project-specific TPM budget while the ingestion pipeline keeps its own
        (separate) ``TokenRateLimiter`` instance.

        Nothing is ever dropped: an oversized request drains its tokens across
        as many rolling windows as needed (queued, not lost), so a large
        transcript is embedded completely rather than skipped.

        All waits are logged in real time (``logging``, line-buffered to the
        backend log) so a throttled embedding is visibly "queued", never silent.
        """
        if token_count <= 0:
            return
        remaining = token_count
        with self._sync_lock:
            while remaining > 0:
                now = time.monotonic()
                elapsed = now - self.window_start
                if elapsed >= self.window_seconds:
                    self.tokens_used = 0
                    self.window_start = now
                available = self.max_tokens_per_minute - self.tokens_used
                if available <= 0:
                    wait_time = self.window_seconds - elapsed
                    if wait_time <= 0:
                        wait_time = self.window_seconds
                    logger.info(
                        "CSS embedding TPM: budget exhausted (%d/%d). "
                        "Queued; waiting %.1fs for next window.",
                        self.tokens_used, self.max_tokens_per_minute, wait_time,
                    )
                    time.sleep(wait_time)
                    continue
                take = available if available < remaining else remaining
                self.tokens_used += take
                remaining -= take
                if remaining > 0:
                    # More tokens queued than fit in this window: wait for the
                    # next window to keep draining (never drop the remainder).
                    wait_time = self.window_seconds - (
                        time.monotonic() - self.window_start
                    )
                    if wait_time > 0:
                        logger.info(
                            "CSS embedding TPM: %d/%d spent; %d token(s) "
                            "queued for next window (%.1fs).",
                            self.tokens_used, self.max_tokens_per_minute,
                            remaining, wait_time,
                        )
                        time.sleep(wait_time)

    def count_tokens_text(self, texts: list[str]) -> int:
        """Token count for a list of raw strings (no Document wrapping needed)."""
        return sum(len(self.encoding.encode(t)) for t in texts)


class RequestRateLimiter:
    """Synchronous cap on the NUMBER of embedding *requests* per minute.

    The Gemini free tier is bounded by ``embed_content_free_tier_requests``
    (100/min), which is a *request* limit, not a token limit. This limiter is
    the real guard against the ``429 RESOURCE_EXHAUSTED`` the CSS analysis hit:
    it paces one ``embed_documents`` call per N seconds. A single oversized
    call still counts as one request, so it is never dropped.

    Used by the SocialScienceResearch content-homophily embedder (worker thread).
    """

    def __init__(self, max_requests_per_minute: int = 90, window_seconds: int = 60):
        self.max_requests_per_minute = max_requests_per_minute
        self.window_seconds = window_seconds
        self._timestamps: list[float] = []
        self._lock = threading.Lock()

    def acquire(self) -> None:
        if self.max_requests_per_minute <= 0:
            return
        with self._lock:
            while True:
                now = time.monotonic()
                cutoff = now - self.window_seconds
                self._timestamps = [t for t in self._timestamps if t > cutoff]
                if len(self._timestamps) < self.max_requests_per_minute:
                    self._timestamps.append(now)
                    return
                wait_time = self.window_seconds - (now - self._timestamps[0]) + 0.05
                logger.info(
                    "CSS embedding RPM: %d/%d requests this minute. Queued; "
                    "waiting %.1fs before next embedding call.",
                    len(self._timestamps), self.max_requests_per_minute, wait_time,
                )
                time.sleep(max(wait_time, 0.0))

