from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import tiktoken
import random
import re
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from rich.console import Console

from Ingestion_Pipline.config.settings import DEFAULT_EMBED_BATCH_SIZE, DEFAULT_EMBED_SEMAPHORE_LIMIT, DEFAULT_MAX_TOKENS_PER_MINUTE, DEFAULT_RATE_LIMIT_ENCODING
from Ingestion_Pipline.infra.rate_limiter import TokenRateLimiter
from Ingestion_Pipline.infra.vector_store import add_documents_with_retry
from utils.logger import log_error

# embedding registry to coordinate with orchestrator barrier
from gpt_researcher.utils.embedding_registry import register as embedding_register

console = Console()


@dataclass
class EmbeddingRequest:
    docs: list[Document]
    vector_store: QdrantVectorStore
    request_id: str
    retry_count: int = 0
    created_at: float = field(default_factory=time.time)
    status: str = "pending"
    error: Optional[str] = None
    result: Optional[bool] = None


class ResilientEmbeddingPipeline:
    def __init__(
        self,
        batch_size: int = DEFAULT_EMBED_BATCH_SIZE,
        semaphore_limit: int = DEFAULT_EMBED_SEMAPHORE_LIMIT,
        token_rate_limiter: Optional[TokenRateLimiter] = None,
        max_tokens_per_minute: int = DEFAULT_MAX_TOKENS_PER_MINUTE,
        encoding_name: str = DEFAULT_RATE_LIMIT_ENCODING,
        max_retries: int = 3,
    ):
        self.batch_size = batch_size
        self.semaphore = asyncio.Semaphore(semaphore_limit)
        self.limiter = token_rate_limiter or TokenRateLimiter(
            max_tokens_per_minute=max_tokens_per_minute,
            encoding_name=encoding_name,
        )
        self.encoding = tiktoken.get_encoding(self.limiter.encoding.name)
        self.max_retries = max_retries

        self.request_queue: asyncio.Queue[EmbeddingRequest] = asyncio.Queue()
        self.request_history: dict[str, EmbeddingRequest] = {}
        self._lock = asyncio.Lock()
        self._worker_task: Optional[asyncio.Task] = None

    def _batch_token_limit(self) -> int:
        provider_cap = int(os.environ.get("PROVIDER_MAX_TOKENS_PER_MINUTE", "100000"))
        safe_target = int(provider_cap * 0.95)
        batch_token_limit = min(self.limiter.max_tokens_per_minute, safe_target)
        if batch_token_limit < 1000:
            batch_token_limit = max(1000, int(self.limiter.max_tokens_per_minute // 10))
        return batch_token_limit

    def _split_doc_into_sized_chunks(self, doc: Document, token_limit: int) -> list[Document]:
        tokens = self.encoding.encode(doc.page_content)
        total_tokens = len(tokens)
        console.print(f"[magenta]Splitting doc (tokens={total_tokens}) into token-limited chunks of {token_limit} tokens[/magenta]")
        if total_tokens <= token_limit:
            console.print(f"[magenta]No split needed: doc tokens {total_tokens} <= token_limit {token_limit}[/magenta]")
            return [doc]

        chunks: list[Document] = []
        metadata = getattr(doc, "metadata", None)

        for i in range(0, len(tokens), token_limit):
            chunk_tokens = tokens[i : i + token_limit]
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append(
                Document(
                    page_content=chunk_text,
                    metadata=metadata,
                )
            )
        console.print(f"[magenta]Created {len(chunks)} chunks from doc (original tokens={total_tokens})[/magenta]")
        return chunks

    def _partition_into_batches(self, docs: list[Document], batch_size: int) -> list[list[Document]]:
        """Partition documents into batches primarily by token count.

        The pipeline prefers token-based batching (batch_token_limit) over a fixed
        document-count batch_size. batch_size is kept as a safety cap on the
        number of docs per batch but token limits drive splitting.
        """
        batch_token_limit = self._batch_token_limit()

        batches: list[list[Document]] = []
        current_batch: list[Document] = []
        current_tokens = 0

        console.print(f"[cyan]Partitioning {len(docs)} docs using token-based batch limit {batch_token_limit} tokens[/cyan]")

        for idx, doc in enumerate(docs, start=1):
            doc_tokens = len(self.encoding.encode(doc.page_content))
            console.print(f"[cyan]Doc {idx}/{len(docs)}: {doc_tokens} tokens[/cyan]")

            subdocs = (
                self._split_doc_into_sized_chunks(doc, batch_token_limit)
                if doc_tokens > batch_token_limit
                else [doc]
            )

            for subdoc in subdocs:
                subdoc_tokens = len(self.encoding.encode(subdoc.page_content))

                # If adding this subdoc would exceed the token limit, flush current batch
                if current_batch and (current_tokens + subdoc_tokens) > batch_token_limit:
                    console.print(f"[cyan]Flushing batch with {len(current_batch)} docs ({current_tokens} tokens) due to token limit[/cyan]")
                    batches.append(current_batch)
                    current_batch = []
                    current_tokens = 0

                # Append subdoc
                current_batch.append(subdoc)
                current_tokens += subdoc_tokens
                console.print(f"[cyan]Added subdoc ({subdoc_tokens} tokens). Current batch tokens={current_tokens}. Docs in batch={len(current_batch)}[/cyan]")

                # Safety: if the batch grows too large by document count, flush it
                if len(current_batch) >= max(1, batch_size * 10):
                    # allow batch_size to act as a soft cap but only after a generous multiplier
                    console.print(f"[yellow]Safety flush: batch reached doc-count cap {len(current_batch)} (soft cap {batch_size * 10})[/yellow]")
                    batches.append(current_batch)
                    current_batch = []
                    current_tokens = 0

        if current_batch:
            console.print(f"[cyan]Final flush: appending last batch with {len(current_batch)} docs ({current_tokens} tokens)[/cyan]")
            batches.append(current_batch)

        console.print(f"[green]Partitioned into {len(batches)} batches[/green]")
        return batches

    async def start_worker(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop_worker(self) -> None:
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def _worker_loop(self) -> None:
        console.print("[bold cyan]🚀 Embedding worker started[/bold cyan]")
        while True:
            try:
                request = await self.request_queue.get()
                await self._process_request(request)
            except asyncio.CancelledError:
                console.print("[yellow]⛔ Embedding worker stopped[/yellow]")
                break
            except Exception as e:
                console.print(f"[red]Worker error: {e}[/red]")
                await asyncio.sleep(1)

    async def _process_request(self, request: EmbeddingRequest) -> EmbeddingRequest:
        request.status = "processing"
        # Start with a conservative initial backoff (seconds)
        backoff = 4.0

        while request.retry_count < self.max_retries:
            try:
                batch_tokens = self.limiter.count_tokens(request.docs)
                console.print(f"[blue]Attempting to acquire tokens for request {request.request_id} ({batch_tokens} tokens)[/blue]")
                await self.limiter.acquire(request.docs)
                console.print(f"[blue]Acquired tokens for request {request.request_id} ({batch_tokens} tokens). Calling add_documents_with_retry()[/blue]")

                # Log vector store target and doc summaries
                try:
                    store_name = getattr(request.vector_store, 'collection_name', repr(request.vector_store))
                except Exception:
                    store_name = repr(request.vector_store)

                console.print(f"[blue]→ Processing request {request.request_id} -> store={store_name} docs={len(request.docs)} tokens={batch_tokens}[/blue]")

                await add_documents_with_retry(request.vector_store, request.docs)

                request.result = True
                request.status = "completed"
                console.print(
                    f"[green]✓ Request {request.request_id} completed "
                    f"({len(request.docs)} docs, {batch_tokens} tokens)[/green]"
                )
                self.request_history[request.request_id] = request
                return request

            except Exception as e:
                request.retry_count += 1
                request.error = str(e)

                # If we've exhausted retries, mark failed and return
                if request.retry_count >= self.max_retries:
                    request.status = "failed"
                    self.request_history[request.request_id] = request
                    console.print(
                        f"[red]✗ Request {request.request_id} FAILED after {self.max_retries} retries: {e}[/red]"
                    )
                    return request

                # Exponential backoff with jitter and an upper cap
                base_wait = backoff * (2 ** (request.retry_count - 1))
                # jitter +/-25%
                jittered = base_wait * random.uniform(0.75, 1.25)
                wait_time = min(60.0, jittered)

                # If exception message contains rate-limit headers, try to parse remaining calls
                try:
                    msg = str(e)
                    m = re.search(r"x[-_]trial[-_]endpoint[-_]call[-_]remaining\W*[:'=\"]\s*(\d+)", msg, re.IGNORECASE)
                    if not m:
                        m = re.search(r"x[-_]endpoint[-_]call[-_]remaining\W*[:'=\"]\s*(\d+)", msg, re.IGNORECASE)
                    if m:
                        remaining = int(m.group(1))
                        console.print(f"[yellow]Rate-limit header remaining: {remaining}[/yellow]")
                        # If very low remaining quota, wait longer before retrying
                        if remaining < 20:
                            wait_time = max(wait_time, 30.0)
                except Exception:
                    # Any parsing errors shouldn't break retry logic
                    pass

                console.print(
                    f"[yellow]↻ Request {request.request_id} retry {request.retry_count}/{self.max_retries} "
                    f"in {wait_time:.1f}s (Error: {e})[/yellow]"
                )
                await asyncio.sleep(wait_time)

        return request

    async def _wait_for_completion(self, request_id: str, timeout: float = 600.0) -> dict[str, Optional[object]]:
        start = time.time()
        while time.time() - start < timeout:
            if request_id in self.request_history:
                req = self.request_history[request_id]
                if req.status in ("completed", "failed"):
                    return {
                        "request_id": request_id,
                        "status": req.status,
                        "result": req.result,
                        "error": req.error,
                        "retry_count": req.retry_count,
                    }
            await asyncio.sleep(0.5)
        return {
            "request_id": request_id,
            "status": "timeout",
            "error": f"Request did not complete within {timeout}s",
        }

    async def _wait_for_all_batches(self, batch_requests: list[EmbeddingRequest], timeout: float = 600.0) -> dict[str, object]:
        results = []
        errors = []
        start = time.time()

        while time.time() - start < timeout:
            all_done = True
            for batch_req in batch_requests:
                if batch_req.request_id not in self.request_history:
                    all_done = False
                    continue
                req = self.request_history[batch_req.request_id]
                if req.status == "completed":
                    results.extend([req.request_id])
                elif req.status == "failed":
                    errors.append({"batch_id": req.request_id, "error": req.error})
                else:
                    all_done = False
            if all_done:
                return {
                    "status": "completed" if not errors else "partial_failure",
                    "total_batches": len(batch_requests),
                    "batch_ids": [r.request_id for r in batch_requests],
                    "errors": errors if errors else None,
                }
            await asyncio.sleep(0.5)

        return {
            "status": "timeout",
            "error": f"Batches did not complete within {timeout}s",
            "batch_ids": [r.request_id for r in batch_requests],
            "errors": errors,
        }

    def get_status(self) -> dict[str, object]:
        completed = sum(1 for r in self.request_history.values() if r.status == "completed")
        failed = sum(1 for r in self.request_history.values() if r.status == "failed")
        processing = sum(1 for r in self.request_history.values() if r.status == "processing")

        return {
            "queued": self.request_queue.qsize(),
            "processing": processing,
            "completed": completed,
            "failed": failed,
            "total_requests": len(self.request_history),
            "tokens_used": self.limiter.tokens_used,
            "tokens_limit": self.limiter.max_tokens_per_minute,
            "worker_running": self._worker_task is not None and not self._worker_task.done(),
        }

    async def embed_documents(
        self,
        vector_store: QdrantVectorStore,
        docs: list[Document],
        request_id: str = "",
        batch_size: int | None = None,
        wait_for_result: bool = True,
    ) -> dict[str, object]:
        if not request_id:
            request_id = f"embed_{int(time.time() * 1000)}"

        if batch_size is not None:
            self.batch_size = batch_size

        batches = self._partition_into_batches(docs, self.batch_size)

        if len(batches) == 1:
            request = EmbeddingRequest(
                docs=batches[0],
                vector_store=vector_store,
                request_id=request_id,
            )
            await self.request_queue.put(request)
            console.print(
                f"[blue]📝 Queued request {request_id} ({len(batches[0])} docs)[/blue]"
            )

            if wait_for_result:
                return await self._wait_for_completion(request_id)

            try:
                asyncio.create_task(
                    embedding_register(request_id, self._wait_for_completion(request_id))
                )
            except Exception:
                pass

            return {
                "request_id": request_id,
                "status": "queued",
                "batch_count": 1,
                "batch_ids": [request_id],
            }

        batch_requests: list[EmbeddingRequest] = []
        for idx, batch in enumerate(batches):
            batch_id = f"{request_id}_batch_{idx + 1}"
            request = EmbeddingRequest(
                docs=batch,
                vector_store=vector_store,
                request_id=batch_id,
            )
            batch_requests.append(request)
            await self.request_queue.put(request)

        console.print(
            f"[blue]📝 Split & queued {len(batch_requests)} batches ({len(docs)} docs total)[/blue]"
        )

        if wait_for_result:
            return await self._wait_for_all_batches(batch_requests)

        try:
            for request in batch_requests:
                asyncio.create_task(
                    embedding_register(request.request_id, self._wait_for_completion(request.request_id))
                )
        except Exception:
            pass

        return {
            "request_id": request_id,
            "status": "queued",
            "batch_count": len(batch_requests),
            "batch_ids": [r.request_id for r in batch_requests],
        }


_pipeline: Optional[ResilientEmbeddingPipeline] = None


def get_embedding_pipeline() -> ResilientEmbeddingPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = ResilientEmbeddingPipeline()
    return _pipeline


async def embed_documents_in_batches(
    vector_store: QdrantVectorStore,
    docs: list[Document],
    batch_size: int = DEFAULT_EMBED_BATCH_SIZE,
    semaphore: asyncio.Semaphore | None = None,
    limiter: TokenRateLimiter | None = None,
) -> dict[str, object]:
    pipeline = get_embedding_pipeline()
    if batch_size is not None:
        pipeline.batch_size = batch_size
    if limiter is not None:
        pipeline.limiter = limiter
    await pipeline.start_worker()
    return await pipeline.embed_documents(vector_store, docs, batch_size=batch_size)
